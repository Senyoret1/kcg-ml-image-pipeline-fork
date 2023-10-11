import sys
import threading
import io
import random

base_directory = "./"
sys.path.insert(0, base_directory)

from configs.model_config import ModelPathConfig
from stable_diffusion.model_paths import (SDconfigs, CLIPconfigs)
from stable_diffusion import CLIPTextEmbedder
from utility.minio import cmd
from training_worker.ab_ranking.model.ab_ranking_efficient_net import ABRankingEfficientNetModel
from worker.prompt_generation.prompt_generator import (initialize_prompt_list_from_csv)
from prompt_generation_prompt_queue import PromptGenerationPromptQueue

class PromptJobGeneratorState:
    def __init__(self, device):
        # keep the dataset_rate in this dictionary
        # should update using orchestration api
        self.dataset_rate = {}
        self.total_rate = 0
        self.dataset_rate_lock = threading.Lock()
        # keep the dataset_job_queue_size in this dictionary
        # should update using orchestration api
        self.dataset_job_queue_size = {}
        self.dataset_job_queue_target = {}
        self.dataset_job_queue_size_lock = threading.Lock()
        # each dataset will have a list of masks
        # only relevent if its an inpainting job
        self.dataset_masks = {}
        # each dataset will have one callback to spawn the jobs
        self.dataset_callbacks = {}
        # efficient net model we use for scoring prompts
        # each dataset will have its own  model
        # input : prompts
        # output : prompt_score
        self.prompt_efficient_net_model_dictionary = {}

        # minio connection
        self.minio_client = None

        self.prompt_queue = PromptGenerationPromptQueue(16)

        self.phrases = None
        self.phrases_token_size = None
        self.positive_count_list = None
        self.negative_count_list = None
        self.device = device
        self.config = ModelPathConfig()
        self.clip_text_embedder = CLIPTextEmbedder(device=self.device)

    def configure_minio(self, minio_access_key, minio_secret_key):
        self.minio_client = cmd.get_minio_client(minio_access_key, minio_secret_key)

    def load_clip_model(self):
        # Load the clip model
        self.clip_text_embedder.load_submodels(
            tokenizer_path=self.config.get_model_folder_path(CLIPconfigs.TXT_EMB_TOKENIZER),
            transformer_path=self.config.get_model_folder_path(CLIPconfigs.TXT_EMB_TEXT_MODEL)
        )

    def load_efficient_net_model(self, dataset, dataset_bucket, model_path):

        efficient_net_model = ABRankingEfficientNetModel(in_channels=2)

        model_file_data = cmd.get_file_from_minio(self.minio_client, dataset_bucket, model_path)

        if model_file_data is None:
            return

        # Create a BytesIO object and write the downloaded content into it
        byte_buffer = io.BytesIO()
        for data in model_file_data.stream(amt=8192):
            byte_buffer.write(data)
        # Reset the buffer's position to the beginning
        byte_buffer.seek(0)

        efficient_net_model.load(byte_buffer)

        self.prompt_efficient_net_model_dictionary[dataset] = efficient_net_model

    def get_efficient_net_model(self, dataset):
        # try to get the efficient net model
        # if the efficient net model is not found
        # for the dataset return None
        if dataset in self.prompt_efficient_net_model_dictionary:
            return self.prompt_efficient_net_model_dictionary[dataset]

        return None

    def load_prompt_list_from_csv(self, csv_dataset_path, csv_phrase_limit):
        phrases, phrases_token_size, positive_count_list, negative_count_list = initialize_prompt_list_from_csv(csv_dataset_path, csv_phrase_limit)

        self.phrases = phrases
        self.phrases_token_size = phrases_token_size
        self.positive_count_list = positive_count_list
        self.negative_count_list = negative_count_list

    def register_callback(self, dataset, callback):
        self.dataset_callbacks[dataset] = callback

    def get_callback(self, dataset):
        if dataset in self.dataset_callbacks:
            return self.dataset_callbacks[dataset]
        else:
            return None

    def set_dataset_rate(self, dataset, rate):
        with self.dataset_rate_lock:
            self.dataset_rate[dataset] = rate

    def set_total_rate(self, total_rate):
        with self.dataset_rate_lock:
            self.total_rate = total_rate

    def get_dataset_rate(self, dataset):
        with self.dataset_rate_lock:
            if dataset in self.dataset_rate:
                return self.dataset_rate[dataset]
            else:
                return None

    def set_dataset_job_queue_size(self, dataset, job_queue_size):
        with self.dataset_job_queue_size_lock:
            self.dataset_job_queue_size[dataset] = job_queue_size

    def set_dataset_job_queue_target(self, dataset, job_queue_target):
        with self.dataset_job_queue_size_lock:
            self.dataset_job_queue_target[dataset] = job_queue_target

    def get_dataset_job_queue_size(self, dataset):
        with self.dataset_job_queue_size_lock:
            if dataset in self.dataset_job_queue_size:
                return self.dataset_job_queue_size[dataset]

            return None

    def get_dataset_job_queue_target(self, dataset):
        with self.dataset_job_queue_size_lock:
            if dataset in self.dataset_job_queue_target:
                return self.dataset_job_queue_target[dataset]

            return None

    def add_dataset_mask(self, dataset, init_image_path, mask_path):
        if dataset not in self.dataset_masks:
            self.dataset_masks[dataset] = []

        self.dataset_masks[dataset].append({
            'init_image' : init_image_path,
            'mask' : mask_path
        })

    def get_random_dataset_mask(self, dataset):
        if dataset in self.dataset_masks:
            mask_list = self.dataset_masks[dataset]
        else:
            mask_list = None

        if mask_list is None:
            return None
        random_index = random.randint(0, len(mask_list) - 1)
        return mask_list[random_index]
