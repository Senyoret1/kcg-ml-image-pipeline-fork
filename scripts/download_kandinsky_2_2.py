import os
from pathlib import Path
import torch
from diffusers import AutoPipelineForInpainting

TARGET_DIR = Path('hub_folder')
TARGET_DIR.mkdir(exist_ok=True)

# Step 1: download weights & export folders

pipe = AutoPipelineForInpainting.from_pretrained(
    "kandinsky-community/kandinsky-2-2-decoder", 
    torch_dtype=torch.float16,
    resume_download=True
)

prior_folder = TARGET_DIR / 'kandinsky-2-2-prior'
decoder_folder = TARGET_DIR / 'kandinsky-2-2-decoder'
decoder_inpaint_folder = TARGET_DIR /'kandinsky-2-2-decoder-inpaint'

pipe.prior_scheduler.save_pretrained(prior_folder / 'scheduler')
pipe.prior_prior.save_pretrained(prior_folder / 'prior')
pipe.prior_image_processor.save_pretrained(prior_folder / 'image_processor')
pipe.prior_image_encoder.save_pretrained(prior_folder / 'image_encoder')
pipe.prior_tokenizer.save_pretrained(prior_folder / 'tokenizer')
pipe.prior_text_encoder.save_pretrained(prior_folder / 'text_encoder')

pipe.scheduler.save_pretrained(decoder_folder / 'scheduler')
pipe.unet.save_pretrained(decoder_folder / 'unet')
pipe.movq.save_pretrained(decoder_folder / 'movq')

pipe = AutoPipelineForInpainting.from_pretrained(
    "kandinsky-community/kandinsky-2-2-decoder-inpaint", 
    torch_dtype=torch.float16,
    resume_download=True
)

pipe.scheduler.save_pretrained(decoder_inpaint_folder / 'scheduler')
pipe.unet.save_pretrained(decoder_inpaint_folder / 'unet')
pipe.movq.save_pretrained(decoder_inpaint_folder / 'movq')

# Step 2: pack folders

os.system(f'cd {TARGET_DIR} && zip -r kandinsky-2-2.zip kandinsky-2-2-prior kandinsky-2-2-decoder kandinsky-2-2-decoder-inpaint')

# Step 3: load from folders

from diffusers import DDPMScheduler, UNet2DConditionModel, VQModel, PriorTransformer, UnCLIPScheduler
from diffusers import KandinskyV22CombinedPipeline, KandinskyV22InpaintCombinedPipeline
from transformers import CLIPVisionModelWithProjection, CLIPTextModelWithProjection, CLIPTokenizer, CLIPImageProcessor

prior_scheduler = UnCLIPScheduler.from_pretrained(prior_folder / 'scheduler')
prior_prior = PriorTransformer.from_pretrained(prior_folder / 'prior')
prior_image_encoder = CLIPVisionModelWithProjection.from_pretrained(prior_folder / 'image_encoder')
prior_text_encoder = CLIPTextModelWithProjection.from_pretrained(prior_folder / 'text_encoder')
prior_tokenizer = CLIPTokenizer.from_pretrained(prior_folder / 'tokenizer')
prior_image_processor = CLIPImageProcessor.from_pretrained(prior_folder / 'image_processor')

scheduler = DDPMScheduler.from_pretrained(decoder_folder / 'scheduler')
unet = UNet2DConditionModel.from_pretrained(decoder_folder / 'unet')
movq = VQModel.from_pretrained(decoder_folder / 'movq')

pipe = KandinskyV22CombinedPipeline(
    prior_scheduler=prior_scheduler,
    prior_prior=prior_prior,
    prior_image_encoder=prior_image_encoder,
    prior_text_encoder=prior_text_encoder,
    prior_tokenizer=prior_tokenizer,
    prior_image_processor=prior_image_processor,
    scheduler=scheduler,
    unet=unet,
    movq=movq,
)

scheduler = DDPMScheduler.from_pretrained(decoder_inpaint_folder / 'scheduler')
unet = UNet2DConditionModel.from_pretrained(decoder_inpaint_folder / 'unet')
movq = VQModel.from_pretrained(decoder_inpaint_folder / 'movq')

pipe = KandinskyV22InpaintCombinedPipeline(
    prior_scheduler=prior_scheduler,
    prior_prior=prior_prior,
    prior_image_encoder=prior_image_encoder,
    prior_text_encoder=prior_text_encoder,
    prior_tokenizer=prior_tokenizer,
    prior_image_processor=prior_image_processor,
    scheduler=scheduler,
    unet=unet,
    movq=movq,
)