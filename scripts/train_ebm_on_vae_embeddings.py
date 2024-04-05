## Standard libraries
import os
import json
import math
import numpy as np
import random

## Imports for plotting
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import to_rgb
import matplotlib
from mpl_toolkits.mplot3d.axes3d import Axes3D
from mpl_toolkits.mplot3d import proj3d
from torch.utils.data import random_split, DataLoader

## PyTorch
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.utils.data as data
import torch.optim as optim
# Torchvision
import torchvision
from torchvision.datasets import MNIST
from torchvision import transforms

# PyTorch Lightning
try:
    import pytorch_lightning as pl
except ModuleNotFoundError: # Google Colab does not have PyTorch Lightning installed by default. Hence, we do it here if necessary
    #!pip install --quiet pytorch-lightning>=1.4
    import pytorch_lightning as pl
from pytorch_lightning.callbacks import LearningRateMonitor, ModelCheckpoint



# ADDED BY ME
from datetime import datetime
from pytz import timezone
from torch.utils.data import DataLoader
from torchvision.datasets import CIFAR10
from torchvision.datasets import SVHN
import torchvision.transforms as transforms
from io import BytesIO
import io
import os
import sys
base_directory = os.getcwd()
sys.path.insert(0, base_directory)
from data_loader.ab_ranking_dataset_loader import ABRankingDatasetLoader
from utility.minio import cmd
from utility.clip.clip_text_embedder import tensor_attention_pooling
import urllib.request
from urllib.error import HTTPError
from torchvision.datasets import SVHN
from torch.utils.data import random_split, DataLoader
from PIL import Image
import requests
import msgpack 
from kandinsky.models.clip_image_encoder.clip_image_encoder import KandinskyCLIPImageEncoder
import tempfile
import csv
import pandas as pd
from torch.utils.data import ConcatDataset


# ------------------------------------------------- Parameters -------------------------------------------------
matplotlib.rcParams['lines.linewidth'] = 2.0

# Path to the folder where the datasets are/should be downloaded (e.g. CIFAR10)
DATASET_PATH = "../data"
# Path to the folder where the pretrained models are saved
CHECKPOINT_PATH = "../savedmodels"

# Setting the seed
pl.seed_everything(42)

# Ensure that all operations are deterministic on GPU (if used) for reproducibility
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False



# ------------------------------------------------- Initialize the cuda device -------------------------------------------------
device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")
print("Device:", device)

# ------------------------------------------------- Initialize minio -------------------------------------------------

date_now = datetime.now(tz=timezone("Asia/Hong_Kong")).strftime('%d-%m-%Y %H:%M:%S')
print(date_now)


minio_client = cmd.get_minio_client("D6ybtPLyUrca5IdZfCIM",
            "2LZ6pqIGOiZGcjPTR6DZPlElWBkRTkaLkyLIBt4V",
            None)
minio_path="environmental/output/my_tests"


# ------------------------------------------------- Parameters BIS -------------------------------------------------
base_directory = "./"
sys.path.insert(0, base_directory)

from utility.path import separate_bucket_and_file_path
from data_loader.utils import get_object

API_URL = "http://192.168.3.1:8111"

batchsize_x = 16

# Transformations: # don't use greyscale ?
transform = transforms.Compose([
    transforms.Resize((512, 512)),
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,))  
])

total_losses = []
class_losses = []
cdiv_losses = []
reg_losses = []
real_scores_s = []
fake_scores_s = []

# ------------------------------------------------- Kandinsky Clip Manager -------------------------------------------------
image_embedder= KandinskyCLIPImageEncoder(device="cuda")
image_embedder.load_submodels()



from diffusers import VQModel

base_dir = "./"
sys.path.insert(0, base_dir)
sys.path.insert(0, os.getcwd())
from kandinsky.model_paths import DECODER_MODEL_PATH

decoder_path= DECODER_MODEL_PATH
local_files_only = True
weight_dtype =  torch.cuda.FloatTensor




# ---------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------- Define Functions --------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------


def get_image(file_path: str):
    # get image from minio server
    bucket_name, file_path = separate_bucket_and_file_path(file_path)
    try:
        response = minio_client.get_object(bucket_name, file_path)
        image_data = BytesIO(response.data)
        img = Image.open(image_data)
        img = img.convert("RGB")
    except Exception as e:
        raise e
    finally:
        response.close()
        response.release_conn()

    return img

import diffusers
from torchvision.transforms import ToTensor

def get_clip_and_image_from_path(image_path):
    image=get_image(image_path)
    # to_tensor = ToTensor()
    # tensor = to_tensor(image)

    # vae = VQModel.from_pretrained(
    #     decoder_path, subfolder="movq", torch_dtype=weight_dtype,
    #     local_files_only=local_files_only
    # ).eval().to(device, dtype=weight_dtype)


    # with torch.no_grad():
    #         latents = vae.encode(tensor).latents

    # clip_embedding = latents
    clip_embedding = get_clip_vectors_single(image_path)

    return image,clip_embedding


def get_tag_jobs(tag_id):
    response = requests.get(f'{API_URL}/tags/get-images-by-tag-id/?tag_id={tag_id}')
    
    # Check if the response is successful (status code 200)
    if response.status_code == 200:
        try:
            # Parse the JSON response
            response_data = json.loads(response.content)

            # Check if 'images' key is present in the JSON response
            if 'images' in response_data.get('response', {}):
                # Extract file paths from the 'images' key
                file_paths = [job['file_path'] for job in response_data['response']['images']]
                return file_paths
            else:
                print("Error: 'images' key not found in the JSON response.")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
    else:
        print(f"Error: HTTP request failed with status code {response.status_code}")

    # Return an empty list or appropriate value to indicate an error
    return []


def get_file_paths(dataset,num_samples):
        print('Loading image file paths')
        response = requests.get(f'{API_URL}/queue/image-generation/list-by-dataset?dataset={dataset}&size={num_samples}')
        
        jobs = json.loads(response.content)

        file_paths=[job['file_path'] for job in jobs]

        return file_paths

# Get latent

# # From multiples image paths
# def get_vae_vectors(file_paths):
#     clip_vectors = []

#     for path in file_paths:

#         try:
#             print("path : " , path)
#             clip_path = path.replace(".jpg", "_vae_latent.msgpack")
#             bucket, features_vector_path = separate_bucket_and_file_path(clip_path)

#             features_data = get_object(minio_client, features_vector_path)
#             features = msgpack.unpackb(features_data)["latent_vector"]
#             features = torch.tensor(features)
#             clip_vectors.append(features)
#         except Exception as e:
#             # Handle the specific exception (e.g., FileNotFoundError, ConnectionError) or a general exception.
#             print(f"Error processing clip at path {path}: {e}")
#             # You might want to log the error for further analysis or take alternative actions.

#     return clip_vectors


# From multiples image paths
def get_clip_vectors(file_paths):
    clip_vectors = []

    for path in file_paths:

        try:
            print("path : " , path)
            clip_path = path.replace(".jpg", "_vae_latent.msgpack")
            bucket, features_vector_path = separate_bucket_and_file_path(clip_path)

            features_data = get_object(minio_client, features_vector_path)
            features = msgpack.unpackb(features_data)["latent_vector"]
            features = torch.tensor(features)
            clip_vectors.append(features)
        except Exception as e:
            # Handle the specific exception (e.g., FileNotFoundError, ConnectionError) or a general exception.
            print(f"Error processing clip at path {path}: {e}")
            # You might want to log the error for further analysis or take alternative actions.

    return clip_vectors

# From multiples image paths
def get_clip_vectors_single(file_paths):
    features = None
    try:
        print("path : " , file_paths)
        clip_path = file_paths.replace(".jpg", "_vae_latent.msgpack")
        bucket, features_vector_path = separate_bucket_and_file_path(clip_path)

        features_data = get_object(minio_client, features_vector_path)
        features = msgpack.unpackb(features_data)["latent_vector"]
        features = torch.tensor(features)
        
    except Exception as e:
        # Handle the specific exception (e.g., FileNotFoundError, ConnectionError) or a general exception.
        print(f"Error processing clip at path {file_paths}: {e}")
        # You might want to log the error for further analysis or take alternative actions.


    return features

# From a single image 
def get_clip_from_image(image):
    return image_embedder.get_image_features(image)

def get_clip_embeddings_by_tag(id_classes,label_value):
    images_paths = get_tag_jobs(id_classes[0])
    i = 1
    for i in range(1,len(id_classes)):
        images_paths = images_paths + get_tag_jobs(id_classes[i])
       
 
    
    ocult_clips = get_clip_vectors(images_paths)


    # Create labels
    data_occcult_clips = [(clip, label_value) for clip in ocult_clips]
    print("Clip embeddings array lenght : ",len(data_occcult_clips))

    # Split

    num_samples = len(data_occcult_clips)
    train_size = int(0.8 * num_samples)
    val_size = num_samples - train_size
    train_set, val_set = random_split(data_occcult_clips, [train_size, val_size])

    train_loader_clip = data.DataLoader(train_set, batch_size=batchsize_x, shuffle=True, drop_last=True, num_workers=4, pin_memory=True)
    val_loader_clip = data.DataLoader(val_set, batch_size=batchsize_x, shuffle=False, drop_last=True, num_workers=4, pin_memory=True)

    return train_loader_clip, val_loader_clip

    

# Get train and validation loader from images paths and the label value
def get_clip_embeddings_by_path(images_paths,label_value):
    ocult_clips = []
    ocult_clips = get_clip_vectors(images_paths)


    # Create labels
    data_occcult_clips = [(clip, label_value) for clip in ocult_clips]
    print("Clip embeddings array lenght : ",len(data_occcult_clips))

    # Split

    num_samples = len(data_occcult_clips)
    train_size = int(0.8 * num_samples)
    val_size = num_samples - train_size
    train_set, val_set = random_split(data_occcult_clips, [train_size, val_size])

    train_loader_clip = data.DataLoader(train_set, batch_size=batchsize_x, shuffle=True, drop_last=True, num_workers=4, pin_memory=True)
    val_loader_clip = data.DataLoader(val_set, batch_size=batchsize_x, shuffle=False, drop_last=True, num_workers=4, pin_memory=True)

    return train_loader_clip, val_loader_clip





# ------------------------------------------------- DATA AUGMENTATION -------------------------------------------------
def data_augmentation(images_tensor, num_of_passes):
    # Define probabilities for each transformation
    prob_mirror = 0.9
    prob_zoom = 0.5
    prob_rotation = 0.2
    prob_contrast = 0.5
    prob_brightness = 0.5

    # Apply data augmentation to each image in the array
    augmented_images = []

    for img in images_tensor:
        for _ in range(num_of_passes):
            transformed_img = img.clone()

            # Apply mirror transformation
            random_mirror = random.random()
            if random_mirror < prob_mirror:
                transformed_img = transforms.RandomHorizontalFlip()(transformed_img)

            # Apply zoom transformation
            random_zoom = random.random()
            if random_zoom < prob_zoom:
                transformed_img = transforms.RandomResizedCrop(size=(512, 512), scale=(0.9, 1.1), ratio=(0.9, 1.1))(transformed_img)

            # Apply rotation transformation
            random_rotation = random.random()
            if random_rotation < prob_rotation:
                transformed_img = transforms.RandomRotation(degrees=(-20, 20))(transformed_img)


            # New Augments
                
            # Apply contrast transformation
            random_contrast = random.random()
            if random_contrast < prob_contrast:
                transformed_img = transforms.ColorJitter(contrast=(0.5, 1.5))(transformed_img)

            # Apply brightness transformation
            random_brightness = random.random()
            if random_brightness < prob_brightness:
                transformed_img = transforms.ColorJitter(brightness=(0.2, 2))(transformed_img)



            augmented_images.append(transformed_img)

    # Convert the list of augmented images to a PyTorch tensor
    augmented_images_tensor = torch.stack(augmented_images)

    # Concatenate original and augmented images
    combined_images = images_tensor + list(augmented_images_tensor)

    return combined_images



# ------------------------------------------------- GET DATASET  -------------------------------------------------
def get_dataset_from_id(id_class,data_augment_passes,label_value):

    images_paths = get_tag_jobs(id_class)
    ocult_images = []


    for path in images_paths:
        ocult_images.append(get_image(path))


    # Transforme into tansors
    ocult_images = [transform(img) for img in ocult_images]


    # Call your data_augmentation function
    ocult_images = data_augmentation(ocult_images, data_augment_passes)


    # Create labels
    label_value = label_value
    labels_occult = [label_value] * len(ocult_images)

    data_occcult = []
    for image in ocult_images:
        data_occcult.append((image, label_value))

    ocult_images = data_occcult
    num_samples_ocult = len(ocult_images)
    print("the number of samples in ocult ", num_samples_ocult)
    train_size_ocult = int(0.8 * num_samples_ocult)
    val_size_ocult = num_samples_ocult - train_size_ocult
    train_set_ocult, val_set_ocult = random_split(ocult_images, [train_size_ocult, val_size_ocult])
    return train_set_ocult,val_set_ocult



# ---------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------- Neural Network Architecture ---------------------------------------
# ---------------------------------------------------------------------------------------------------------------------



class Clip_NN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(Clip_NN, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        # Flatten the input tensor if it's not already flattened
        x = x.view(x.size(0), -1)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x
class DeepEnergyModel(pl.LightningModule):

    def __init__(self, img_shape, batch_size = batchsize_x, alpha=0.1, lr=1e-4, beta1=0.0, **CNN_args):
        super().__init__()
        self.save_hyperparameters()

        self.cnn = Clip_NN(input_size= 64 * 64 * 4, hidden_size = 512, output_size =1) 
        self.example_input_array = torch.zeros(1, *img_shape)

    def forward(self, x):
        z = self.cnn(x)
        return z

    def configure_optimizers(self):
        # Energy models can have issues with momentum as the loss surfaces changes with its parameters.
        # Hence, we set it to 0 by default.
        optimizer = optim.Adam(self.parameters(), lr=self.hparams.lr, betas=(self.hparams.beta1, 0.999))
        scheduler = optim.lr_scheduler.StepLR(optimizer, 1, gamma=0.97) # Exponential decay over epochs
        return [optimizer], [scheduler]

    def training_step(self, batch): #maybe add the adv loader
        # We add minimal noise to the original images to prevent the model from focusing on purely "clean" inputs
        real_imgs, _ = batch
        #print("the _ is ",_)
        small_noise = torch.randn_like(real_imgs) * 0.005
        real_imgs.add_(small_noise).clamp_(min=-1.0, max=1.0)

        # Obtain samples #Give more steps later
        fake_imgs, fake_labels = next(iter(adv_loader))
        fake_imgs = fake_imgs.to(device)
        fake_labels = fake_labels.to(device)

        _.to(device)
        all_imgs = torch.cat([real_imgs, fake_imgs], dim=0)
        all_scores = self.cnn(all_imgs)

        # Separate real and fake scores and probabilities
        real_scores, fake_scores = all_scores.chunk(2, dim=0)


        # Calculate CD loss
        cdiv_loss = fake_scores.mean() - real_scores.mean()

        # regression loss
        reg_loss =((real_scores + fake_scores )** 2) .mean()

        # Combine losses and backpropagate
        alphaW = 1  # Adjust weight for cdiv_loss
        alphaY = 0.01  # Adjust weight for reg_loss
        total_loss =  ((alphaW) * cdiv_loss) + (alphaY * reg_loss)


        # Logging
        self.log('total loss', total_loss)
        self.log('loss_contrastive_divergence', cdiv_loss)
        self.log('metrics_avg_real', 0)
        self.log('metrics_avg_fake', 0)


        total_losses.append(total_loss.item())
        cdiv_losses.append(cdiv_loss.item())
        reg_losses.append(reg_loss.item())

        real_scores_s.append(real_scores.mean().item())
        fake_scores_s.append(fake_scores.mean().item())
        return total_loss
    
    def validation_step(self, batch):

      # Validate with real images only (no noise/fakes)
      real_imgs, labels = batch

      # Pass through model to get scores and probabilities
      all_scores = self.cnn(real_imgs)

      # Calculate CD loss (optional, adjust if needed)
      cdiv = all_scores.mean()  # Modify based on scores or probabilities

      # Log metrics
      self.log('val_contrastive_divergence', cdiv)




# ------------------------------------------------- Train model --------------------------------------------------


def train_model(**kwargs):
    # Create a PyTorch Lightning trainer with the generation callback
    trainer = pl.Trainer(default_root_dir=os.path.join(CHECKPOINT_PATH, "MNIST"),
                         accelerator="gpu" if str(device).startswith("cuda") else "cpu",
                         devices=1,
                         max_epochs=20,
                         gradient_clip_val=0.1,
                         callbacks=[ModelCheckpoint(save_weights_only=True, mode="min", monitor='val_contrastive_divergence'),
                                    LearningRateMonitor("epoch")
                                   ])

    pl.seed_everything(42)
    model = DeepEnergyModel(**kwargs)
    trainer.fit(model, train_loader, val_loader)

    return model


# ------------------------------------------------- Save Model --------------------------------------------------
def save_model(model,name,local_path):
         # Save the model locally
        torch.save(model.state_dict(), local_path )
        
        #Read the contents of the saved model file
        with open(local_path, "rb") as model_file:
            model_bytes = model_file.read()

        # Upload the model to MinIO
        minio_client = cmd.get_minio_client("D6ybtPLyUrca5IdZfCIM", "2LZ6pqIGOiZGcjPTR6DZPlElWBkRTkaLkyLIBt4V",None)
        minio_path="environmental/output/my_tests"
        date_now = datetime.now(tz=timezone("Asia/Hong_Kong")).strftime('%d-%m-%Y %H:%M:%S')
        minio_path= minio_path + "/model-"+name+'_'+date_now+".pth"
        cmd.upload_data(minio_client, 'datasets', minio_path, BytesIO(model_bytes))
        print(f'Model saved to {minio_path}')



# ------------------------------------------------- Load Model--------------------------------------------------
def load_model(model,type):
        # get model file data from MinIO
        prefix= "environmental/output/my_tests/model-"+type
        suffix= ".pth"
        minio_client = cmd.get_minio_client("D6ybtPLyUrca5IdZfCIM", "2LZ6pqIGOiZGcjPTR6DZPlElWBkRTkaLkyLIBt4V",None)
        model_files=cmd.get_list_of_objects_with_prefix(minio_client, 'datasets', prefix)
        most_recent_model = None

        for model_file in model_files:
            if model_file.endswith(suffix):
                most_recent_model = model_file

        if most_recent_model:
            model_file_data =cmd.get_file_from_minio(minio_client, 'datasets', most_recent_model)
        else:
            print("No .pth files found in the list.")
            return None
        
        print(most_recent_model)

        # Create a temporary file and write the downloaded content into it
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            for data in model_file_data.stream(amt=8192):
                temp_file.write(data)

        # Load the model from the downloaded bytes
        model.load_state_dict(torch.load(temp_file.name))
        
        # Remove the temporary file
        os.remove(temp_file.name)
       



# ------------------------------------------------- Compare two clip embeddings and display their images (input: images & embeddings) --------------------------------------------------
@torch.no_grad()
def compare_clip_show(img_in, img_ood, clip_in,clip_ood,model):

    score1 = model.cnn(clip_in.unsqueeze(0).to(model.device)).cpu()

    # Pass the second image through the CNN model and get its score
    score2 = model.cnn(clip_ood.unsqueeze(0).to(model.device)).cpu()

        
    img_in = transform(img_in)
    img_ood = transform(img_ood)
    #class1, class2 = model.cnn(imgs)[1].cpu().chunk(2, dim=0)
    grid = torchvision.utils.make_grid([img_in, img_ood], nrow=2, normalize=True, pad_value=0.5, padding=2)
    grid = grid.permute(1, 2, 0)
    plt.figure(figsize=(4,4))
    plt.imshow(grid)
    plt.xticks([(img_in.shape[2]+2)*(0.5+j) for j in range(2)],
               labels=[f"ID: {score1.item():4.2f}", f"OOD: {score2.item():4.2f}"])
    plt.yticks([])
    plt.savefig("output/comparaison_1.png")

    # Save the figure to a file
    bufx = io.BytesIO()
    plt.savefig(bufx, format='png')
    bufx.seek(0)

    # upload the photo
    
    minio_client = cmd.get_minio_client("D6ybtPLyUrca5IdZfCIM",
                "2LZ6pqIGOiZGcjPTR6DZPlElWBkRTkaLkyLIBt4V",
                None)
    minio_path="environmental/output/my_tests"
    date_now = datetime.now(tz=timezone("Asia/Hong_Kong")).strftime('%d-%m-%Y %H:%M:%S')
    minio_path= minio_path + "/compare_id_vs_ood" +date_now+".png"
    cmd.upload_data(minio_client, 'datasets', minio_path, bufx)
    # Remove the temporary file
    os.remove("output/comparaison_1.png")
    # Clear the current figure
    plt.clf()
    return score1.item(), score2.item()


# ------------------------------------------------- Compare two clip embeddings and display their images (input: image paths) --------------------------------------------------
def energy_evaluation_with_pictures_clip(imgpath_id,imgpath_ood,model):
    

    image_in, clip_emb_in  = get_clip_and_image_from_path(imgpath_id)
    image_ood, clip_emb_ood  = get_clip_and_image_from_path(imgpath_ood)

    compare_clip_show(image_in,image_ood,clip_emb_in,clip_emb_ood,model)






    
# ---------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------- Run Binning Process -----------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------

def process_and_sort_dataset(images_paths, model):
    # Initialize an empty list to hold the structure for each image
    structure = []

    # Process each image path
    for image_path in images_paths:
        # Extract embedding and image tensor from the image path
        image, embedding = get_clip_and_image_from_path(image_path)
        if (image != None) and  (embedding != None):
            # Compute the score by passing the image tensor through the model
            # Ensure the tensor is in the correct shape, device, etc.
            score = model.cnn(embedding.to(model.device)).cpu()
            
            # Append the path, embedding, and score as a tuple to the structure list
            structure.append((image_path, embedding, score.item(),image))  # Assuming score is a tensor, use .item() to get the value

        # Sort the structure list by the score in descending order (for ascending, remove 'reverse=True')
    # The lambda function specifies that the sorting is based on the third element of each tuple (index 2)
    sorted_structure = sorted(structure, key=lambda x: x[2], reverse=True)

    return sorted_structure




def process_and_sort_dataset_combined(images_paths, model1,model2):
    # Initialize an empty list to hold the structure for each image
    structure = []

    # Process each image path
    for image_path in images_paths:
        # Extract embedding and image tensor from the image path
        image, embedding = get_clip_and_image_from_path(image_path)
        
        # Compute the score by passing the image tensor through the model
        # Ensure the tensor is in the correct shape, device, etc.
        score = model1.cnn(embedding.unsqueeze(0).to(model1.device)).cpu() + model2.cnn(embedding.unsqueeze(0).to(model2.device)).cpu()
        
        # Append the path, embedding, and score as a tuple to the structure list
        structure.append((image_path, embedding, score.item(),image))  # Assuming score is a tensor, use .item() to get the value

    # Sort the structure list by the score in descending order (for ascending, remove 'reverse=True')
    # The lambda function specifies that the sorting is based on the third element of each tuple (index 2)
    sorted_structure = sorted(structure, key=lambda x: x[2], reverse=True)

    return sorted_structure


# 
def process_and_sort_dataset_weighted_combinations(images_paths, models,weights):
    # Initialize an empty list to hold the structure for each image
    structure = []

    # Process each image path
    for image_path in images_paths:
        # Extract embedding and image tensor from the image path
        image, embedding = get_clip_and_image_from_path(image_path)
        
        # Compute the score by passing the image tensor through the model
        # Ensure the tensor is in the correct shape, device, etc.
        score = 0
        for i in range(len(models)):
            score += weights[i] *models[i].cnn(embedding.unsqueeze(0).to(models[i].device)).cpu() 
        
        # Append the path, embedding, and score as a tuple to the structure list
        structure.append((image_path, embedding, score.item(),image))  # Assuming score is a tensor, use .item() to get the value

    # Sort the structure list by the score in descending order (for ascending, remove 'reverse=True')
    # The lambda function specifies that the sorting is based on the third element of each tuple (index 2)
    sorted_structure = sorted(structure, key=lambda x: x[2], reverse=True)

    return sorted_structure

# ---------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------- Displayer images with scores --------------------------------------
# ---------------------------------------------------------------------------------------------------------------------


def plot_images_with_scores(sorted_dataset,name):
    minio_client = cmd.get_minio_client("D6ybtPLyUrca5IdZfCIM",
            "2LZ6pqIGOiZGcjPTR6DZPlElWBkRTkaLkyLIBt4V",
            None)
    # Number of images
    num_images = len(sorted_dataset)
    
    # Fixed columns to 4
    cols = 4
    # Calculate rows needed for 4 images per row
    rows = math.ceil(num_images / cols)

    # Create figure with subplots
    # Adjust figsize here: width, height in inches. Increase for larger images.
    fig, axes = plt.subplots(rows, cols, figsize=(4*cols, 4*rows))  # 4 inches per image in each dimension
    fig.tight_layout(pad=3.0)  # Adjust padding as needed
    # Flatten axes array for easy indexing
    axes = axes.flatten()

    # Loop over sorted dataset and plot each image with its score
    for i, (image_path, _, score, image_tensor) in enumerate(sorted_dataset):
        # Check if image_tensor is a PIL Image; no need to convert if already a numpy array
        if not isinstance(image_tensor, np.ndarray):
            # Convert PIL Image to a format suitable for matplotlib
            image = np.array(image_tensor)
        
        # Plot the image
        axes[i].imshow(image)
        axes[i].set_title(f"Score: {score:.2f}")
        axes[i].axis('off')  # Hide axis ticks and labels

    # Hide any unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].axis('off')

    plt.savefig("output/rank.png")

    # Save the figure to a file
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    # upload the graph report
    minio_path="environmental/output/my_tests"
    minio_path= minio_path + "/ranking_ds_"+ name + '_' +date_now+".png"
    cmd.upload_data(minio_client, 'datasets', minio_path, buf)
    # Remove the temporary file
    os.remove("output/rank.png")
    # Clear the current figure
    plt.clf()



# ---------------------------------------------------------------------------------------------------------------------
# ---------------------------- Save the list of the images processed, ordered and put in bins -------------------------
# ---------------------------------------------------------------------------------------------------------------------

def get_structure_csv_content(sorted_structure,name):
    # Calculate the percentile and assign bin numbers
    scores = [item[2] for item in sorted_structure]
    bin_numbers = pd.qcut(scores, q=100, labels=False) + 1

    # Combine image paths, scores, and bin numbers into a list of dictionaries
    data = [
        {
            'image_path': item[0],
            'score': item[2],
            'bin_number': bin_numbers[i]  # Adjust bin_number to start from 1
        }
        for i, item in enumerate(sorted_structure)
    ]

    # Write the list of dictionaries to an in-memory buffer
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=['image_path', 'score', 'bin_number'])
    writer.writeheader()
    writer.writerows(data)

    # Return the content of the buffer
    # Convert the content of csv_buffer to bytes
    csv_content_bytes = csv_buffer.getvalue().encode('utf-8')

    # Upload the model to MinIO
    minio_client = cmd.get_minio_client("D6ybtPLyUrca5IdZfCIM", "2LZ6pqIGOiZGcjPTR6DZPlElWBkRTkaLkyLIBt4V", None)
    minio_path = "environmental/output/my_tests"
    date_now = datetime.now(tz=timezone("Asia/Hong_Kong")).strftime('%d-%m-%Y %H:%M:%S')
    minio_path = minio_path + "/best_results_for" + name + '_' + date_now + ".csv"
    cmd.upload_data(minio_client, 'datasets', minio_path, BytesIO(csv_content_bytes))
    print(f'Model saved to {minio_path}')



# ---------------------------------------------------------------------------------------------------------------------
# -------------------------------------------------------- Evaluation Functions ---------------------------------------
# ---------------------------------------------------------------------------------------------------------------------
 

def getAccuracy_v2(cyber_sample_loader, model1, model2):
    preci = 0
    cpt = 0
    average_score = 0
    average_score_ood = 0

    # Set models to evaluation mode
    model1.eval()
    model2.eval()

    # Iterate through all batches in the DataLoader
    for batch in cyber_sample_loader:
        embeddings = batch[0]  # Assuming the embeddings are the first element in each batch

        # Move embeddings to the correct device
        embeddings = embeddings.to(model1.device)

        # Get scores from both models
        scores1 = model1.cnn(embeddings).cpu().detach().numpy()
        scores2 = model2.cnn(embeddings).cpu().detach().numpy()

        # Iterate through scores in the batch
        for score1, score2 in zip(scores1, scores2):
            print("Score 1:", score1.item())
            print("Score 2:", score2.item())

            if score1 > score2:
                preci += 1
            cpt += 1
            average_score += score1.item()
            average_score_ood += score2.item()

    # Calculate average scores
    average_score /= cpt
    average_score_ood /= cpt

    print(f"Score in distribution : {average_score:4.2f}")
    print(f"Score OOD : {average_score_ood:4.2f}")
    print(f"Accuracy : {preci} / {cpt}")






# ---------------------------------------------------------------------------------------------------------------------
# -------------------------------------------------------- Let's run some tests here ----------------------------------
# ---------------------------------------------------------------------------------------------------------------------
 


# # Load the environmental dataset     
# images_paths_ood = get_file_paths("environmental",30000)

# # Create a new Model    
# occult_model = DeepEnergyModel(img_shape=(1280,))
# # Load the last occult trained model
# load_model(occult_model,'occult')

# # Get sort the images by energy (from best to worst)
# sorted_images_for_occult = process_and_sort_dataset(images_paths_ood, occult_model)

# # Save the list on csv file
# get_structure_csv_content(sorted_images_for_occult,"occult_on_env_30000_sample")

# # Get top 50 images
# selected_best_50_for_occult = sorted_images_for_occult[:50]

# # Only keep the paths
# selected_best_50_for_occult = [item[0] for item in selected_best_50_for_occult]
# # Concat the paths of the best 50 with the tagged images
# new_combined_paths = selected_best_50_for_occult + get_tag_jobs(39)

# # Create dataloader of occult
# train_loader_automated, val_loader_automated = get_clip_embeddings_by_path(new_combined_paths,1)

# # Get adversarial dataset
# train_loader_clip_ood, val_loader_clip_ood = get_clip_embeddings_by_tag([7,8,9,15,20,21,22],0)

# # init the loader
# train_loader = train_loader_automated
# val_loader = val_loader_automated
# adv_loader = train_loader_clip_ood



# # Train new model with the new combined dataset

# # Train
# new_occult_model = train_model(img_shape=(1,1280),
#                     batch_size=train_loader.batch_size,
#                     lr=0.001,
#                     beta1=0.0)
# save_model(new_occult_model,'occult','temp_model.pth')


# # Plot

# ############### Plot graph
# epochs = range(1, len(total_losses) + 1)  

# # Create subplots grid (3 rows, 1 column)
# fig, axes = plt.subplots(4, 1, figsize=(10, 24))

# # Plot each loss on its own subplot
# axes[0].plot(epochs, total_losses, label='Total Loss')
# axes[0].set_xlabel('Steps')
# axes[0].set_ylabel('Loss')
# axes[0].set_title('Total Loss')
# axes[0].legend()
# axes[0].grid(True)

# axes[1].plot(epochs, cdiv_losses, label='Contrastive Divergence Loss')
# axes[1].set_xlabel('Steps')
# axes[1].set_ylabel('Loss')
# axes[1].set_title('Contrastive Divergence Loss')
# axes[1].legend()
# axes[1].grid(True)


# axes[2].plot(epochs, reg_losses , label='Regression Loss')
# axes[2].set_xlabel('Steps')
# axes[2].set_ylabel('Loss')
# axes[2].set_title('Regression Loss')
# axes[2].legend()
# axes[2].grid(True)

# # Plot real and fake scores on the fourth subplot
# axes[3].plot(epochs, real_scores_s, label='Real Scores')
# axes[3].plot(epochs, fake_scores_s, label='Fake Scores')
# axes[3].set_xlabel('Steps')
# axes[3].set_ylabel('Score')  # Adjust label if scores represent a different metric
# axes[3].set_title('Real vs. Fake Scores')
# axes[3].legend()
# axes[3].grid(True)

# # Adjust spacing between subplots for better visualization
# plt.tight_layout()

# plt.savefig("output/loss_tracking_per_step.png")

# # Save the figure to a file
# buf = io.BytesIO()
# plt.savefig(buf, format='png')
# buf.seek(0)

# # upload the graph report
# minio_path="environmental/output/my_tests"
# minio_path= minio_path + "/loss_tracking_per_step_1_cd_p2_regloss_cyber_training" +date_now+".png"
# cmd.upload_data(minio_client, 'datasets', minio_path, buf)
# # Remove the temporary file
# os.remove("output/loss_tracking_per_step.png")
# # Clear the current figure
# plt.clf()



# # Evaluate new model
# #automated model
# #toodoo
# #go create something
# print("yep it's here")
# new_sorted_images = process_and_sort_dataset(images_paths_ood, new_occult_model)


# get_structure_csv_content(new_sorted_images,"occult_on_env_30000_sample")
# selected_structure_first_52 = new_sorted_images[:52]
# selected_structure_second_52 = new_sorted_images[52:103]
# selected_structure_third_52 = new_sorted_images[103:154]

# plot_images_with_scores(selected_structure_first_52,"Top_first_52_occult_env_added_50")
# plot_images_with_scores(selected_structure_second_52,"Top_second_52_occult_env_added_50")
# plot_images_with_scores(selected_structure_third_52,"Top_third_52_occult_env_added_50")


# ---------------------------------------------------------------------------------------------------------------------
# -------------------------------------------------------- Run test on cimbined classes -------------------------------
# ---------------------------------------------------------------------------------------------------------------------
 

#  # Load the environmental dataset     
# images_paths_ood = get_file_paths("environmental",30000)

# # Create a new Model    
# occult_model = DeepEnergyModel(img_shape=(1280,))
# # Load the last occult trained model
# load_model(occult_model,'occult')


# # Create a new Model    
# cybernetics_model = DeepEnergyModel(img_shape=(1280,))
# # Load the last occult trained model
# load_model(cybernetics_model,'cyber')


# # Create a new Model    
# texture_model = DeepEnergyModel(img_shape=(1280,))
# # Load the last occult trained model
# load_model(texture_model,'defect-only')

# #sorted_combined_images = process_and_sort_dataset_combined(images_paths_ood,occult_model,cybernetics_model)
# sorted_combined_images = process_and_sort_dataset_weighted_combinations(images_paths_ood,[occult_model,cybernetics_model,texture_model],[0,1,-1])

# get_structure_csv_content(sorted_combined_images,"cyber_minus_textures_on_env_30000_sample")
# selected_structure_first_52 = sorted_combined_images[:52]
# selected_structure_second_52 = sorted_combined_images[52:103]
# selected_structure_third_52 = sorted_combined_images[103:154]

# plot_images_with_scores(selected_structure_first_52,"Top_first_52_cyber_minus_textures")
# plot_images_with_scores(selected_structure_second_52,"Top_second_52_cyber_minus_textures")
# plot_images_with_scores(selected_structure_third_52,"Top_third_52_cyber_minus_textures")





# ---------------------------------------------------------------------------------------------------------------------
# -------------------------------------------------------- Train for isometric veiw ----------------------------------
# ---------------------------------------------------------------------------------------------------------------------
 


def get_unique_tag_ids():
    response = requests.get(f'{API_URL}/tags/list-tag-definitions')
    if response.status_code == 200:
        try:
            json_data = response.json()
            tags = json_data.get('response', {}).get('tags', [])

            # Extract unique tag IDs
            unique_tag_ids = set(tag.get('tag_id') for tag in tags)
            
            # Convert the set of unique tag IDs to a list
            unique_tag_ids_list = list(unique_tag_ids)
            
            return unique_tag_ids_list
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
    else:
        print(f"Error: HTTP request failed with status code {response.status_code}")



def get_tag_id_by_name(tag_name):
    response = requests.get(f'{API_URL}/tags/get-tag-id-by-tag-name?tag_string={tag_name}')
    
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse the JSON response
        json_data = response.json()

        # Get the value of "response" from the JSON data
        response_value = json_data.get('response')
        tag_id = response_value.get('tag_id')
        # Print or use the response value
        #print("The tag id is:", response_value, " the tag id is : ",tag_id )
        return tag_id
    else:
        print("Error:", response.status_code)



def get_all_tag_jobs(class_ids,target_id):
    all_data = {}  # Dictionary to store data for all class IDs
    
    for class_id in class_ids:
        response = requests.get(f'{API_URL}/tags/get-images-by-tag-id/?tag_id={class_id}')
        
        # Check if the response is successful (status code 200)
        if response.status_code == 200:
            try:
                # Parse the JSON response
                response_data = json.loads(response.content)
                
                # Check if 'images' key is present in the JSON response
                if 'images' in response_data.get('response', {}):
                    # Extract file paths from the 'images' key
                    file_paths = [job['file_path'] for job in response_data['response']['images']]
                    all_data[class_id] = file_paths
                else:
                    print(f"Error: 'images' key not found in the JSON response for class ID {class_id}.")
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON for class ID {class_id}: {e}")
        else:
            print(f"Error: HTTP request failed with status code {response.status_code} for class ID {class_id}")
    

    # # Separate data for a specific class ID (e.g., class_id = X) from all the rest
    # target_class_data = all_data.get(target_id, [])
    # rest_of_data = {class_id: data for class_id, data in all_data.items() if class_id != target_id}
    # #return target_class_data , rest_of_data


    # Separate data for a specific class ID (e.g., class_id = X) from all the rest
    target_class_data = all_data.get(target_id, [])
    rest_of_data = [path for class_id, paths in all_data.items() if class_id != target_id for path in paths]

    return target_class_data, rest_of_data




classe_name = "topic-space"
print("class name ", classe_name)
all_tags = get_unique_tag_ids()
print("all tag : ",all_tags)
class_tag = get_tag_id_by_name(classe_name)
print("class tag : ",  class_tag)
target_paths, adv_paths = get_all_tag_jobs(class_ids = all_tags, target_id =class_tag)
print("target_paths lenght : ", len(target_paths))
print("adv_paths lenght : ", len(adv_paths))


new_combined_paths = get_tag_jobs(35)


# Create dataloader of occult
train_loader_automated, val_loader_automated = get_clip_embeddings_by_path(target_paths,1)

# Get adversarial dataset
train_loader_clip_ood, val_loader_clip_ood = get_clip_embeddings_by_tag(adv_paths,0)

print("target paths : ", target_paths)
print("ood paths : ", adv_paths)
print("Train loader  len : ", len(train_loader_automated) )
# # init the loader
# train_loader = train_loader_automated
# val_loader = val_loader_automated
# adv_loader = train_loader_clip_ood



# ############################


# # Train
# new_cyber_vae_model = train_model(img_shape=(64,64,4),
#                     batch_size=train_loader.batch_size,
#                     lr=0.001,
#                     beta1=0.0)
# save_model(new_cyber_vae_model,'cyber_vae','temp_model.pth')


# # up loader graphs

# # # Plot

# # ############### Plot graph
# epochs = range(1, len(total_losses) + 1)  

# # Create subplots grid (3 rows, 1 column)
# fig, axes = plt.subplots(4, 1, figsize=(10, 24))

# # Plot each loss on its own subplot
# axes[0].plot(epochs, total_losses, label='Total Loss')
# axes[0].set_xlabel('Steps')
# axes[0].set_ylabel('Loss')
# axes[0].set_title('Total Loss')
# axes[0].legend()
# axes[0].grid(True)

# axes[1].plot(epochs, cdiv_losses, label='Contrastive Divergence Loss')
# axes[1].set_xlabel('Steps')
# axes[1].set_ylabel('Loss')
# axes[1].set_title('Contrastive Divergence Loss')
# axes[1].legend()
# axes[1].grid(True)


# axes[2].plot(epochs, reg_losses , label='Regression Loss')
# axes[2].set_xlabel('Steps')
# axes[2].set_ylabel('Loss')
# axes[2].set_title('Regression Loss')
# axes[2].legend()
# axes[2].grid(True)

# # Plot real and fake scores on the fourth subplot
# axes[3].plot(epochs, real_scores_s, label='Real Scores')
# axes[3].plot(epochs, fake_scores_s, label='Fake Scores')
# axes[3].set_xlabel('Steps')
# axes[3].set_ylabel('Score')  # Adjust label if scores represent a different metric
# axes[3].set_title('Real vs. Fake Scores')
# axes[3].legend()
# axes[3].grid(True)

# # Adjust spacing between subplots for better visualization
# plt.tight_layout()

# plt.savefig("output/loss_tracking_per_step.png")

# # Save the figure to a file
# buf = io.BytesIO()
# plt.savefig(buf, format='png')
# buf.seek(0)

# # upload the graph report
# minio_path="environmental/output/my_tests"
# minio_path= minio_path + "/loss_tracking_per_step_1_cd_p2_regloss_isometric_training" +date_now+".png"
# cmd.upload_data(minio_client, 'datasets', minio_path, buf)
# # Remove the temporary file
# os.remove("output/loss_tracking_per_step.png")
# # Clear the current figure
# plt.clf()



# # Load the environmental dataset     
# images_paths_ood = get_file_paths("environmental",30000)

# # Evaluate new model
# #automated model
# #toodoo
# #go create something
# print("yep it's here")
# new_sorted_images = process_and_sort_dataset(images_paths_ood, new_cyber_vae_model)


# get_structure_csv_content(new_sorted_images,"cyber_vae_on_env_30000_sample")
# selected_structure_first_52 = new_sorted_images[:52]
# selected_structure_second_52 = new_sorted_images[52:103]
# selected_structure_third_52 = new_sorted_images[103:154]

# plot_images_with_scores(selected_structure_first_52,"Top_first_52_cyber_vae_env_added_50")
# plot_images_with_scores(selected_structure_second_52,"Top_second_52_cyber_vae_env_added_50")
# plot_images_with_scores(selected_structure_third_52,"Top_third_52_cyber_vae_env_added_50")
    



# ---------------------------------------------------------------------------------------------------------------------
# -------------------------------------------------------- Run test on cimbined classes iso cyber -------------------------------
# ---------------------------------------------------------------------------------------------------------------------
 

#  # Load the environmental dataset     
# images_paths_ood = get_file_paths("environmental",30000)

# # Create a new Model    
# occult_model = DeepEnergyModel(img_shape=(1280,))
# # Load the last occult trained model
# load_model(occult_model,'occult')


# # Create a new Model    
# cybernetics_model = DeepEnergyModel(img_shape=(1280,))
# # Load the last occult trained model
# load_model(cybernetics_model,'cyber')


# # Create a new Model    
# texture_model = DeepEnergyModel(img_shape=(1280,))
# # Load the last occult trained model
# load_model(texture_model,'defect-only')


# # Create a new Model    
# isometric_model = DeepEnergyModel(img_shape=(1280,))
# # Load the last occult trained model
# load_model(isometric_model,'isometric')




# #sorted_combined_images = process_and_sort_dataset_combined(images_paths_ood,occult_model,cybernetics_model)
# sorted_combined_images = process_and_sort_dataset_weighted_combinations(images_paths_ood,[occult_model,isometric_model,texture_model],[1,1,-1])

# get_structure_csv_content(sorted_combined_images,"Iso +  Occult - texture")
# selected_structure_first_52 = sorted_combined_images[:52]
# selected_structure_second_52 = sorted_combined_images[52:103]
# selected_structure_third_52 = sorted_combined_images[103:154]

# plot_images_with_scores(selected_structure_first_52,"Iso +  Occult - texture : Tier 1")
# plot_images_with_scores(selected_structure_second_52,"Iso +  Occult - texture : Tier 2")
# plot_images_with_scores(selected_structure_third_52,"Iso +  Occult - texture : Tier 3")


