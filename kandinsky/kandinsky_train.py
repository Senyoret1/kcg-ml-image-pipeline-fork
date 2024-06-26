import io
import os
import sys
from matplotlib import pyplot as plt
import torch
import datasets
import torch.nn.functional as F
from diffusers.optimization import get_scheduler
from diffusers import DDPMScheduler, UNet2DConditionModel, VQModel
from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection
from torch.cuda.amp import GradScaler, autocast
scaler = GradScaler()
from PIL import Image
import numpy as np
from tqdm.auto import tqdm
import torch.autograd.profiler as profiler

base_dir = "./"
sys.path.insert(0, base_dir)
sys.path.insert(0, os.getcwd())
from kandinsky.model_paths import PRIOR_MODEL_PATH, DECODER_MODEL_PATH
from utility.minio import cmd

# Set up file for logging
log_file_path= "memory_usage_log.txt"
log_file = open(log_file_path, "w")
total_memory=0

# Function to log memory usage
def log_memory_usage(description, current_memory_usage):
    total_memory= torch.cuda.memory_allocated(device) / (1024 * 1024 * 1024)
    memory_used_at_step= total_memory - current_memory_usage 
    max_memory= torch.cuda.max_memory_allocated(device) / (1024 * 1024 * 1024)

    log_file.write(f"{description}-----------------------\n")
    log_file.write(f"Memory allocated at this step: {memory_used_at_step} GB\n")
    log_file.write(f"Total allocated memory: {total_memory} GB\n")
    log_file.write(f"Max allocated memory: {max_memory} GB\n\n")

    print(f"{description}-----------------------")
    print(f"Memory allocated at this step: {memory_used_at_step} GB")
    print(f"Total allocated memory: {total_memory} GB")
    print(f"Max allocated memory: {max_memory} GB")

    return total_memory

weight_dtype = torch.float32

device = torch.device(0)

optimizer_cls = torch.optim.SGD

learning_rate = 1e-4

adam_beta1 = 0.9
adam_beta2 = 0.999
adam_weight_decay = 0.0
adam_epsilon = 1e-8

snr_gamma = None

max_train_steps = 10000
gradient_accumulation_steps = 1
checkpointing_steps = 100

lr_scheduler = 'constant'
lr_warmup_steps = 500

train_batch_size = 1
dataloader_num_workers = 1

image_column = 'image'
resolution = 512

local_files_only = False
pretrained_prior_model_name_or_path = PRIOR_MODEL_PATH
pretrained_decoder_model_name_or_path = DECODER_MODEL_PATH
noise_scheduler = DDPMScheduler.from_pretrained(
    pretrained_decoder_model_name_or_path, subfolder="scheduler",
    local_files_only=local_files_only
)
image_processor = CLIPImageProcessor.from_pretrained(
    pretrained_prior_model_name_or_path, subfolder="image_processor",
    local_files_only=local_files_only
)
vae = VQModel.from_pretrained(
    pretrained_decoder_model_name_or_path, subfolder="movq", torch_dtype=weight_dtype,
    local_files_only=local_files_only
).eval()
image_encoder = CLIPVisionModelWithProjection.from_pretrained(
    pretrained_prior_model_name_or_path, subfolder="image_encoder", torch_dtype=weight_dtype,
    local_files_only=local_files_only
).eval()
unet = UNet2DConditionModel.from_pretrained(
    pretrained_decoder_model_name_or_path, subfolder="unet",
    local_files_only=local_files_only
)
# Freeze vae and image_encoder
vae.requires_grad_(False)
image_encoder.requires_grad_(False)

unet.enable_gradient_checkpointing()

# Move image_encode and vae to gpu and cast to weight_dtype
image_encoder.to(device, dtype=weight_dtype)
total_memory= log_memory_usage("Loading the image encoder", total_memory)
vae.to(device, dtype=weight_dtype)
total_memory= log_memory_usage("Loading the vae", total_memory)
unet.to(device, dtype=weight_dtype)
total_memory= log_memory_usage("Loading the Unet", total_memory)

optimizer = optimizer_cls(
    unet.parameters(),
    lr=learning_rate,
    weight_decay=adam_weight_decay
)

def center_crop(image):
    width, height = image.size
    new_size = min(width, height)
    left = (width - new_size) / 2
    top = (height - new_size) / 2
    right = (width + new_size) / 2
    bottom = (height + new_size) / 2
    return image.crop((left, top, right, bottom))

def train_transforms(img):
    img = center_crop(img)
    img = img.resize((resolution, resolution), resample=Image.BICUBIC, reducing_gap=1)
    img = np.array(img).astype(np.float32) / 127.5 - 1
    img = torch.from_numpy(np.transpose(img, [2, 0, 1]))
    return img

def preprocess_train(examples):
    images = [image.convert("RGB") for image in examples[image_column]]
    examples["pixel_values"] = [train_transforms(image) for image in images]
    examples["clip_pixel_values"] = image_processor(images, return_tensors="pt").pixel_values
    return examples

if not os.path.exists("input/pokemon-blip-captions"):
    dataset = datasets.load_dataset('reach-vb/pokemon-blip-captions')
    dataset.save_to_disk('input/pokemon-blip-captions')

dataset = datasets.load_dataset('arrow', data_files={'train': 'input/pokemon-blip-captions/train/data-00000-of-00001.arrow'})
train_dataset = dataset["train"].with_transform(preprocess_train)

def collate_fn(examples):
    pixel_values = torch.stack([example["pixel_values"] for example in examples])
    pixel_values = pixel_values.to(memory_format=torch.contiguous_format).float()
    clip_pixel_values = torch.stack([example["clip_pixel_values"] for example in examples])
    clip_pixel_values = clip_pixel_values.to(memory_format=torch.contiguous_format).float()

    return {"pixel_values": pixel_values, "clip_pixel_values": clip_pixel_values}

train_dataloader = torch.utils.data.DataLoader(
    train_dataset,
    shuffle=True,
    collate_fn=collate_fn,
    batch_size=train_batch_size,
    num_workers=dataloader_num_workers,
)

lr_scheduler = get_scheduler(
    lr_scheduler,
    optimizer=optimizer,
    num_warmup_steps=lr_warmup_steps * gradient_accumulation_steps,
    num_training_steps=max_train_steps * gradient_accumulation_steps,
)

# Preprocess dataset to calculate latents and image_embeds
latent_batches = []
image_embeds_batches = []
for batch in tqdm(train_dataloader):
    with torch.no_grad():
        images = batch["pixel_values"].to(device, weight_dtype)
        clip_images = batch["clip_pixel_values"].to(device, weight_dtype)
        latents_batch = vae.encode(images).latents
        image_embeds_batch = image_encoder(clip_images).image_embeds
    latent_batches.append(latents_batch)
    image_embeds_batches.append(image_embeds_batch)

total_memory= log_memory_usage("Pre-processing the dataset", total_memory)

# Convert the lists to tensors
latent_batches = torch.cat(latent_batches)
image_embeds_batches = torch.cat(image_embeds_batches)

# Move vae and image_encoder to CPU
vae.to('cpu')
image_encoder.to('cpu')

# Delete vae and image_encoder
del vae
del image_encoder

total_memory= log_memory_usage("Unloading vae and Image Encoder", total_memory)

epoch = 1
step = 0
batch_iter = 0
data_iter = iter(train_dataloader)

loss_per_epoch=[]
losses = list()

def compute_snr():
    pass

torch.autograd.set_detect_anomaly(True)

while step < max_train_steps:
    try:
        batch = next(data_iter)
    except StopIteration:
        batch_iter = 0
        epoch += 1
        data_iter = iter(train_dataloader)
        batch = next(data_iter)
        avg_loss= np.mean(losses)
        loss_per_epoch.append(avg_loss)
        print(f"Epoch: {epoch}, Step: {step}, Loss: {avg_loss}")
        losses = list()

    # Set unet to trainable.
    unet.train()

    # Get latents and image_embeds for the current batch
    latents = latent_batches[batch_iter * train_batch_size: (batch_iter + 1) * train_batch_size]
    image_embeds = image_embeds_batches[batch_iter * train_batch_size: (batch_iter + 1) * train_batch_size]

    print("latent shape:", latents.shape)
    print("clip shape:", image_embeds.shape)

    # Sample noise that we'll add to the latents
    noise = torch.randn_like(latents)
    bsz = latents.shape[0]
    # Sample a random timestep for each image
    timesteps = torch.randint(0, noise_scheduler.config.num_train_timesteps, (bsz,), device=latents.device)
    timesteps = timesteps.long()

    noisy_latents = noise_scheduler.add_noise(latents, noise, timesteps)
    target = noise

    with autocast():
        added_cond_kwargs = {"image_embeds": image_embeds}
        model_pred = unet(noisy_latents, timesteps, None, added_cond_kwargs=added_cond_kwargs).sample[:, :4]
        
        if(epoch==1 and step==0):
            total_memory= log_memory_usage("Forward Pass", total_memory)

        if snr_gamma is None:
            loss = F.mse_loss(model_pred.float(), target.float(), reduction="mean")
        else:
            snr = compute_snr(noise_scheduler, timesteps)
            mse_loss_weights = torch.stack([snr, snr_gamma * torch.ones_like(timesteps)], dim=1).min(dim=1)[0]
            if noise_scheduler.config.prediction_type == "epsilon":
                mse_loss_weights = mse_loss_weights / snr
            elif noise_scheduler.config.prediction_type == "v_prediction":
                mse_loss_weights = mse_loss_weights / (snr + 1)
            loss = F.mse_loss(model_pred.float(), target.float(), reduction="none")
            loss = loss.mean(dim=list(range(1, len(loss.shape)))) * mse_loss_weights
            loss = loss.mean()
        
        loss = loss / gradient_accumulation_steps  # Adjust loss for gradient accumulation

    # Backward pass profiling
    loss.backward()
    if(epoch==1 and step==0):
        total_memory= log_memory_usage("Backward Pass", total_memory)
    step+=1 
    batch_iter+= 1
    # Optimizer step profiling
    if step % gradient_accumulation_steps == 0:
        # Context manager to enable autograd profiler
        if(epoch==1 and step==1):
            with profiler.profile(use_cuda=True, profile_memory=True) as prof:
                optimizer.step()
            total_memory= log_memory_usage("Optimizer Step", total_memory)
        else:
            optimizer.step()
        lr_scheduler.step()
        optimizer.zero_grad()

    losses.append(loss.detach().cpu().numpy())

    # Save model periodically or based on conditions
    if step % checkpointing_steps == 0:
        print(f"Epoch: {epoch}, Step: {step}, Loss: {np.mean(losses)}")
        losses = list()
        # torch.save(unet.state_dict(), f"unet.pth")

# Print the profiler results
log_file.write(f"Optimizer profiler: \n\n {prof.key_averages().table(sort_by='self_cuda_memory_usage')}")

log_file.close()  # Close the log file

# get minio client
minio_client = cmd.get_minio_client(minio_access_key="v048BpXpWrsVIHUfdAix",
                                    minio_secret_key="4TFS20qkxVuX2HaC8ezAgG7GaDlVI1TqSPs0BKyu")

# Save log file and get its data buffer with BytesIO
with open(log_file_path, 'rb') as file:
    buffer = io.BytesIO(file.read())
    buffer.seek(0)

cmd.upload_data(minio_client, 'datasets', "environmental/output/kandinsky_train_report/kandinsky_train_report.txt" , buffer)

# graph loss curve
plt.plot(range(1, len(loss_per_epoch) + 1), loss_per_epoch,'b', label='Loss')
plt.title('Loss per Epoch')
plt.ylabel('Loss')
plt.xlabel('Epochs')
plt.legend(['Loss curve'])

# Save the figure to a file
buf = io.BytesIO()
plt.savefig(buf, format='png')
buf.seek(0)

cmd.upload_data(minio_client, 'datasets', "environmental/output/kandinsky_train_report/loss_curve.png" , buf)

# Remove the temporary file
os.remove(log_file_path)
plt.clf()