import sys
sys.path.append('.')

import argparse
import torch
import random
import transformers
import io
import os
import tqdm
import time
import traceback
import contextlib
import msgpack

import pandas as pd

from training_worker.ab_ranking.model.ab_ranking_linear import ABRankingModel
from utility.minio import cmd
from transformers import CLIPTokenizer, CLIPTextModel
from stable_diffusion.model.clip_text_embedder import CLIPTextEmbedder
from worker.prompt_generation.prompt_generator import load_base_prompts, generate_image_generation_jobs

transformers.logging.set_verbosity_error()

GENERATION_POLICY = 'quincy-greedy-prompt-search-v1'
if torch.cuda.is_available():
    DEVICE = 'cuda'
else:
    DEVICE = 'cpu'

class Profile(contextlib.ContextDecorator):
    def __init__(self, t=0.0):
        self.t = t

    def __enter__(self):
        self.start = self.time()
        return self

    def __exit__(self, type, value, traceback):
        self.dt = self.time() - self.start  # delta-time
        self.t += self.dt  # accumulate dt

    def time(self):
        return time.time()

class PromptMutatorDatasetGenerator:
    def __init__(
        self,
        minio_access_key,
        minio_secret_key,
        minio_ip_addr,
        csv_base_prompts,
        csv_phrase
    ):
        self.minio_client = cmd.get_minio_client(
            minio_access_key=minio_access_key,
            minio_secret_key=minio_secret_key,
            minio_ip_addr=minio_ip_addr
        )
        self.csv_base_prompts = csv_base_prompts
        self.df_phrase = pd.read_csv(csv_phrase)
        self.scorer = self.load_model(768, device=DEVICE)
        self.clip_model, self.tokenizer = self.load_clip()


    def load_clip(self):
        text_embedder = CLIPTextEmbedder()
        text_embedder.load_submodels()

        return text_embedder, text_embedder.tokenizer

    def load_model(self, input_size, device=DEVICE):
        input_path = "environmental/models/ranking/"

        embedding_model = ABRankingModel(input_size)

        model_files = cmd.get_list_of_objects_with_prefix(self.minio_client, 'datasets', input_path)
        most_recent_model = None

        for model_file in model_files:
            if model_file.endswith("score-linear-embedding-positive.pth"):
                most_recent_model = model_file

        if most_recent_model:
            model_file_data =cmd.get_file_from_minio(self.minio_client, 'datasets', most_recent_model)
        else:
            print("No .pth files found in the list.")
            return

        # Create a BytesIO object and write the downloaded content into it
        byte_buffer = io.BytesIO()
        for data in model_file_data.stream(amt=8192):
            byte_buffer.write(data)
        # Reset the buffer's position to the beginning
        byte_buffer.seek(0)

        embedding_model.load(byte_buffer)
        embedding_model.model=embedding_model.model.to(device)

        return embedding_model

    def embed(self, prompt):
        # given a prompt string, this function converts it into text embedding
        with torch.no_grad():
            embedding, _, attention_mask = self.clip_model.forward_return_all(prompt)

        # return without the batch dimension
        return embedding[0]

    def score_prompt(self, prompt):
        # given a prompt string, embed it into text embedding and score it using linear model
        # only considers positive prompt
        embedding = self.embed(prompt)
        # reshape it such that the sequence dimension is at the end
        # this is necessary for the linear model
        embedding = embedding.unsqueeze(0).permute(0, 2, 1)
        score = self.scorer.predict_positive_or_negative_only(embedding).item()

        return score

    def get_token_length(self, prompt):
        # returns token length of a given prompt
        # token length include start and end tokens
        token_encoding = self.tokenizer(prompt, return_length=True, return_tensors='pt')

        return token_encoding['length'].item()
    
    def get_tokens(self, prompt):
        # return token ids of input prompt
        token_encoding = self.tokenizer(prompt, return_length=True, return_tensors='pt')

        return token_encoding['input_ids'].cpu().numpy()[0].tolist()

    def create_remove_datapoint(self, prompt):
        # perform removal operation on prompt

        original_score = self.score_prompt(prompt)
        original_length = self.get_token_length(prompt)
        original_embedding = self.embed(prompt).cpu().numpy().tolist()

        # remove random phrase
        # removed_embedding is the embedding of the removed phrase
        prompt_phrase = prompt.split(', ')
        random_index = random.randrange(len(prompt_phrase))
        removed_phrase = prompt_phrase.pop(random_index)
        removed_prompt = ', '.join((prompt_phrase))
        removed_length = self.get_token_length(removed_prompt)
        removed_score = self.score_prompt(removed_prompt)
        removed_embedding = self.embed(removed_phrase).cpu().numpy().tolist()

        return {
            'original_prompt': prompt,
            'original_length': original_length,
            'original_score': original_score,
            'original_embedding': original_embedding,
            'removed_prompt': removed_prompt,
            'removed_phrase': removed_phrase,
            'removed_length': removed_length,
            'removed_score': removed_score,
            'removed_embedding': removed_embedding
        }

    def create_add_datapoint(self, prompt, df_phrase):
        # perform addition operation on prompt

        original_length = self.get_token_length(prompt)

        # truncate prompt by removing last phrase 
        # if prompt length is longer than 60
        # while original_length > 60:
        #     prompt_phrase = prompt.split(', ')
        #     prompt = ', '.join(prompt_phrase[:-1])
        #     original_length = self.get_token_length(prompt)
        
        # use smaller number (65) instead of 77 to get available length
        # the phrase list uses tiktoken and it is not accurate
        # it may exceed length
        avail_length = 75 - original_length
        original_score = self.score_prompt(prompt)
        original_embedding = self.embed(prompt).cpu().numpy().tolist()
        
        # sample a phrase to add
        # add_embedding is the embedding of the phrase to add
        df_sample = df_phrase[df_phrase['token size'] <= avail_length].sample().iloc[0]
        add_phrase = df_sample['phrase str']
        add_prompt = f'{add_phrase}, {prompt}'
        add_length = self.get_token_length(add_prompt)
        add_score = self.score_prompt(add_prompt)
        add_embedding = self.embed(add_phrase).cpu().numpy().tolist()

        return {
            'original_prompt': prompt,
            'original_length': original_length,
            'original_score': original_score,
            'original_embedding': original_embedding,
            'add_prompt': add_prompt,
            'add_phrase': add_phrase,
            'add_length': add_length,
            'add_score': add_score,
            'add_embedding': add_embedding
        }
    
    def generate_seed_prompt(self):
        # generate a seed prompt to mutate
        # seed prompt is generated by sampling the environmental base prompt list
        # it samples up to 60 tokens.
        base_prompt_population = load_base_prompts(self.csv_base_prompts)
        random.shuffle(base_prompt_population)

        seed_prompt = ''
        for phrase in base_prompt_population:
            seed_prompt += f'{phrase},'
            seed_length = self.get_token_length(seed_prompt)
            if seed_length >= 60:
                break
        
        # exclude last character which is the last comma
        return seed_prompt[:-1]
    
    def mutate_prompt(self, seed_prompt=None, n_mutation=1000):
        # this function samples a seed prompt or use a provided seed prompt
        # then applies add / remove n_mutation times
        if seed_prompt is None:
            seed_prompt = self.generate_seed_prompt()
        seed_score = self.score_prompt(seed_prompt)

        modified_prompt = seed_prompt
        scores_over_time = [seed_score]
        print(f'Mutating prompt for {n_mutation} iterations')
        for i in tqdm.tqdm(range(n_mutation)):
            # prevention for generating empty prompt
            # if prompt only has 1 phrase, don't run removal op
            if len(modified_prompt.split(', ')) > 1:
                remove_data = self.create_remove_datapoint(modified_prompt)
                # keep prompt with higher score
                modified_prompt = remove_data['original_prompt'] \
                    if remove_data['original_score'] > remove_data['removed_score'] else remove_data['removed_prompt']

            add_data = self.create_add_datapoint(modified_prompt, self.df_phrase)
            # keep prompt with higher score
            modified_prompt = add_data['original_prompt'] \
                if add_data['original_score'] > add_data['add_score'] else add_data['add_prompt']
            
            modified_score = add_data['original_score'] \
                if add_data['original_score'] > add_data['add_score'] else add_data['add_score']
            
            scores_over_time.append(modified_score)


        print(f'Prompt: {modified_prompt}  Score: {modified_score:.3f}  Base Score: {seed_score:.3f}')
            
        return modified_prompt, modified_score, seed_prompt, seed_score, scores_over_time
    
    def upload_msgpack_to_minio(self, data, upload_path):
        buffer = io.BytesIO()
        encoder = msgpack.Packer()
        encoded_data = encoder.pack(data)
        buffer.write(encoded_data)
        buffer.seek(0)
        cmd.upload_data(self.minio_client, 'users', upload_path, buffer)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--minio-addr', required=False, help='Minio server address', default='192.168.3.5:9000')
    parser.add_argument('--minio-access-key', required=False, help='Minio access key')
    parser.add_argument('--minio-secret-key', required=False, help='Minio secret key')
    parser.add_argument('--csv_phrase', help='CSV containing phrases, must have "phrase str" column', default='input/civitai_phrases_database_v7_no_nsfw.csv')
    parser.add_argument('--n_data', type=int, help='Number of data samples to generate', default=20)
    parser.add_argument(
        '--csv_base_prompts', help='CSV containing base prompts', 
        default='input/dataset-config/environmental/base-prompts-environmental.csv'
    )
    parser.add_argument('--csv_save_path', help='CSV path to save job info', default='output/greedy-prompt-search-v1-output/')
    parser.add_argument('--send_job', action='store_true', default=True)
    parser.add_argument('--dataset_name', default='test-generations')
    parser.add_argument('--n_mutation', type=int, default=800)
    args = parser.parse_args()

    return args

def main(
    minio_access_key,
    minio_secret_key,
    minio_ip_addr,
    csv_phrase,
    n_data,
    csv_save_path,
    csv_base_prompts,
    send_job,
    dataset_name,
    n_mutation
):
    # initialize prompt mutator data generator
    dataset_generator = PromptMutatorDatasetGenerator(
        minio_access_key=minio_access_key,
        minio_secret_key=minio_secret_key,
        minio_ip_addr=minio_ip_addr,
        csv_base_prompts=csv_base_prompts,
        csv_phrase=csv_phrase
    )

    # create folder to save csv if it does not exist
    # create another folder to save scores over time
    os.makedirs(csv_save_path, exist_ok=True)
    os.makedirs(os.path.join(csv_save_path, 'scores_over_time'), exist_ok=True)

    # every 1000 files increment counter by 1
    # this counter is for creating csv file name
    save_name_counter = 0
    df_data = []
    df_scores_over_time = []
    for i in range(n_data):
        print(f'Generating prompt {i+1}')

        # generate prompt by mutation
        prompt, score, seed_prompt, seed_score, scores_over_time = dataset_generator.mutate_prompt(None, n_mutation)

        if send_job:
            try:
                response = generate_image_generation_jobs(
                    positive_prompt=prompt,
                    negative_prompt='',
                    prompt_scoring_model=dataset_generator.scorer.model_type,
                    prompt_score=score,
                    prompt_generation_policy=GENERATION_POLICY,
                    top_k='',
                    dataset_name=dataset_name
                )
                task_uuid = response['uuid']
                task_time = response['creation_time']
            except:
                print('Error occured:')
                print(traceback.format_exc())
                task_uuid = -1
                task_time = -1

        # data to include to output csv file
        # first 4 fields are standard
        # scores are computed using linear model
        # sigma score is relative to linear model
        df_data.append({
            'task_uuid': task_uuid,
            'generation_policy_string': GENERATION_POLICY,
            'time': task_time,
            'prompt': prompt,
            'score': score,
            'seed_prompt': seed_prompt,
            'seed_score': seed_score,
        })
        df_scores_over_time.append(scores_over_time)

        # create csv filename for saving
        if ((i + 1) % 1000) == 0:
            save_name_counter +=  1

        csv_save_filename = os.path.join(csv_save_path, f'{str(save_name_counter).zfill(5)}.csv')
        scores_over_time_filename = os.path.join(csv_save_path, f'{str(save_name_counter).zfill(5)}_scores_over_time.csv')

        # save csv at every iteration just in case script crashes while running
        pd.DataFrame(df_data).to_csv(csv_save_filename, index=False)
        pd.DataFrame(df_scores_over_time).to_csv(scores_over_time_filename, index=False)

        # reset df_data such that it only save 1000 samples in every csv
        if ((i + 1) % 1000) == 0:
            df_data = []
            df_scores_over_time = []


if __name__ == '__main__':
    args = parse_args()
    start = time.time()
    main(
        minio_access_key=args.minio_access_key,
        minio_secret_key=args.minio_secret_key,
        minio_ip_addr=args.minio_addr,
        csv_phrase=args.csv_phrase,
        n_data=args.n_data,
        csv_save_path=args.csv_save_path,
        csv_base_prompts=args.csv_base_prompts,
        send_job=args.send_job,
        dataset_name=args.dataset_name,
        n_mutation=args.n_mutation
    )
    end = time.time()

    print(f'Time taken: {end - start:.2f} seconds')