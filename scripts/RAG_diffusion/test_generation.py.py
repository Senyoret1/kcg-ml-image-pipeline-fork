import sys
import msgpack
import torch
import argparse
import csv
from datetime import datetime
from tqdm import tqdm
from PIL import Image
import random
import time

base_dir = './'
sys.path.insert(0, base_dir)

from data_loader.utils import get_object
from kandinsky_worker.image_generation.img2img_generator import generate_img2img_generation_jobs_with_kandinsky
from kandinsky.models.clip_image_encoder.clip_image_encoder import KandinskyCLIPImageEncoder
from utility.minio import cmd


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--minio-access-key', type=str, help='Minio access key')
    parser.add_argument('--minio-secret-key', type=str, help='Minio secret key')
    parser.add_argument('--dataset', type=str, default='environmental')
    parser.add_argument('--image-path', type=str, default=None)

    return parser.parse_args()

def get_clip_distribution(minio_client, dataset):
    

    data = get_object(minio_client, f"{dataset}/output/stats/clip_stats.msgpack")
    data_dict = msgpack.unpackb(data)

    # Convert to PyTorch tensors
    mean_vector = torch.tensor(data_dict["mean"], dtype=torch.float32)
    std_vector = torch.tensor(data_dict["std"], dtype=torch.float32)
    max_vector = torch.tensor(data_dict["max"], dtype=torch.float32)
    min_vector = torch.tensor(data_dict["min"], dtype=torch.float32)

    return mean_vector, std_vector, max_vector, min_vector

def get_clip_vector_from_image(path):
    image = Image.open(path)
    image = image.resize((512, 512))
    image = image.convert("RGB")
    encoder = KandinskyCLIPImageEncoder(device= 'cuda' if torch.cuda.is_available() else 'cpu')
    encoder.load_submodels()
    clip_vector = encoder.get_image_features(image)
    return clip_vector

def get_fname():
    return f"output/{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}_result_on_diff_cfg_scale.csv"

def main():

    args = parse_args()
    minio_client = cmd.get_minio_client(minio_access_key=args.minio_access_key, 
                                        minio_secret_key=args.minio_secret_key)
    if args.image_path is None:
        clip_vector, _, _, _ = get_clip_distribution(minio_client=minio_client, dataset=args.dataset)
    else:
        clip_vector = get_clip_vector_from_image(args.image_path)

    with open(get_fname(), 'w', newline='') as f:
        csv_writer = csv.DictWriter(f, ['task_uuid', 'task_cfg_scale', 'task_seed','task_creation_time'])
        csv_writer.writeheader()

        for _ in range(20):

            random.seed(time.time())
            seed = random.randint(0, 2 ** 24 - 1)

            for task_cfg_scale in tqdm(range(20), total=20):
                try:
                    response= generate_img2img_generation_jobs_with_kandinsky(
                        image_embedding=clip_vector.unsqueeze(0),
                        negative_image_embedding=None,
                        dataset_name="test-generations",
                        seed=seed,
                        prompt_generation_policy='test-equality-on-different-cfg-scales',
                        decoder_guidance_scale=task_cfg_scale,
                        self_training=True
                    )
                    task_uuid = response['uuid']
                    task_creation_time = response['creation_time']
                except Exception as e:
                    print("An error occured at {} cfg scale".format(task_cfg_scale))
                    task_uuid = -1
                    task_creation_time = -1

                csv_writer.writerow({'task_uuid': task_uuid, 
                                    'task_seed': seed,
                                    'task_cfg_scale': task_cfg_scale, 
                                    'task_creation_time': task_creation_time})

    print('Successfully generated jobs')

if __name__ == '__main__':
    main()