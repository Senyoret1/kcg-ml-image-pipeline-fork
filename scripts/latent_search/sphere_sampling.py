import argparse
from datetime import datetime
import io
import math
import faiss
import os
import sys
import msgpack
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform
import torch
import torch.optim as optim

base_dir = "./"
sys.path.insert(0, base_dir)
sys.path.insert(0, os.getcwd())
from data_loader.utils import get_object
from training_worker.sampling.models.uniform_sampling_regression_fc import SamplingFCRegressionNetwork
from training_worker.sampling.models.directional_uniform_sampling_regression_fc import DirectionalSamplingFCRegressionNetwork
from training_worker.scoring.models.scoring_fc import ScoringFCNetwork
from kandinsky_worker.image_generation.img2img_generator import generate_img2img_generation_jobs_with_kandinsky
from utility.minio import cmd

def parse_args():
        parser = argparse.ArgumentParser()

        parser.add_argument('--minio-access-key', type=str, help='Minio access key')
        parser.add_argument('--minio-secret-key', type=str, help='Minio secret key')
        parser.add_argument('--dataset', type=str, help='Name of the dataset', default="environmental")
        parser.add_argument('--num-images', type=int, help='Number of images to generate', default=1000)
        parser.add_argument('--sphere-type', type=str, help='Type of spheres used', default="uniform")
        parser.add_argument('--top-k', type=float, help='Portion of spheres to select from', default=0.1)
        parser.add_argument('--total-spheres', type=int, help='Number of random spheres to rank', default=500000)
        parser.add_argument('--selected-spheres', type=int, help='Number of spheres to sample from', default=10)
        parser.add_argument('--batch-size', type=int, help='Inference batch size used by the scoring model', default=256)
        parser.add_argument('--steps', type=int, help='Optimization steps', default=200)
        parser.add_argument('--learning-rate', type=float, help='Optimization learning rate', default=0.001)
        parser.add_argument('--send-job', action='store_true', default=False)
        parser.add_argument('--save-csv', action='store_true', default=False)
        parser.add_argument('--sampling-policy', type=str, default="top-k-sphere-sampling")
        parser.add_argument('--optimize-spheres', action='store_true', default=False)
        parser.add_argument('--optimize-samples', action='store_true', default=False)

        return parser.parse_args()

class SphereSamplingGenerator:
    def __init__(self,
                minio_access_key,
                minio_secret_key,
                dataset,
                sphere_type,
                top_k,
                total_spheres,
                selected_spheres,
                batch_size,
                steps,
                learning_rate,
                sampling_policy,
                send_job=False,
                save_csv=False,
                optimize_spheres=False,
                optimize_samples=False,
                ):
            
            self.dataset= dataset
            self.sphere_type= sphere_type
            self.send_job= send_job
            self.save_csv= save_csv
            self.top_k= top_k
            self.total_spheres= total_spheres
            self.selected_spheres= selected_spheres
            self.selected_spheres= selected_spheres
            self.batch_size= batch_size
            self.steps= steps
            self.learning_rate= learning_rate
            self.sampling_policy= sampling_policy
            self.optimize_spheres= optimize_spheres
            self.optimize_samples= optimize_samples

            # get minio client
            self.minio_client = cmd.get_minio_client(minio_access_key=minio_access_key,
                                                    minio_secret_key=minio_secret_key)
            
            # get device
            if torch.cuda.is_available():
                device = 'cuda'
            else:
                device = 'cpu'
            self.device = torch.device(device)
            
            # get the signle point scoring model
            self.scoring_model= ScoringFCNetwork(minio_client=self.minio_client, dataset=dataset)
            self.scoring_model.load_model()

            # load the sphere average score model
            if self.sphere_type=="uniform":
                self.sphere_scoring_model= SamplingFCRegressionNetwork(minio_client=self.minio_client, dataset=dataset)
                self.sphere_scoring_model.load_model()
                # get min and max radius values
                self.min_radius= self.sphere_scoring_model.min_radius.item()
                self.max_radius= self.sphere_scoring_model.max_radius.item()

            elif self.sphere_type=="directional":
                self.sphere_scoring_model= DirectionalSamplingFCRegressionNetwork(minio_client=self.minio_client, dataset=dataset)
                self.sphere_scoring_model.load_model()
                # get min and max radius values
                self.min_radius= torch.tensor(self.sphere_scoring_model.max_scaling_factors).to(device=self.device)
                self.max_radius= torch.tensor(self.sphere_scoring_model.min_scaling_factors).to(device=self.device)

            # get distribution of clip vectors for the dataset
            self.clip_mean , self.clip_std, self.clip_max, self.clip_min= self.get_clip_distribution()
    
    def get_clip_distribution(self):
        data = get_object(self.minio_client, f"{self.dataset}/output/stats/clip_stats.msgpack")
        data_dict = msgpack.unpackb(data)

        # Convert to PyTorch tensors
        mean_vector = torch.tensor(data_dict["mean"][0], device=self.device, dtype=torch.float32)
        std_vector = torch.tensor(data_dict["std"][0], device=self.device, dtype=torch.float32)
        max_vector = torch.tensor(data_dict["max"][0], device=self.device, dtype=torch.float32)
        min_vector = torch.tensor(data_dict["min"][0], device=self.device, dtype=torch.float32)

        return mean_vector, std_vector, max_vector, min_vector

    def generate_spheres(self):
        num_spheres = self.total_spheres

        sphere_centers = torch.normal(mean=self.clip_mean.repeat(num_spheres, 1), 
                                      std=self.clip_std.repeat(num_spheres, 1))
        sphere_centers = torch.clip(sphere_centers, self.clip_min, self.clip_max)
       
        if self.sphere_type=="uniform":
            radii = torch.rand(num_spheres, device=self.device) * (self.max_radius - self.min_radius) + self.min_radius
            radii= radii.unsqueeze(1)
        elif self.sphere_type=="directional":
            radii = torch.rand(num_spheres, len(self.max_radius), device=self.device) * (self.max_radius - self.min_radius) + self.min_radius

        spheres = torch.cat([sphere_centers, radii], dim=1)
        return spheres
    
    def rank_and_optimize_spheres(self, num_images):
        generated_spheres = self.generate_spheres()
        
        # Predict average scores for each sphere
        batch_scores = self.sphere_scoring_model.predict(generated_spheres, batch_size=self.batch_size)
        scores = torch.tensor(batch_scores, device=self.device, dtype=torch.float32)

        # Sort scores and select top spheres
        sorted_indexes = torch.argsort(scores.squeeze(), descending=True)[:int(self.total_spheres * self.top_k)]
        top_spheres = generated_spheres[sorted_indexes]
        # select n random spheres from the top k spheres
        indices = torch.randperm(top_spheres.size(0))[:num_images]
        selected_spheres = top_spheres[indices]

        # Optimization step
        if(self.optimize_spheres):
            selected_spheres = self.optimize_datapoints(selected_spheres, self.sphere_scoring_model)
            selected_spheres= torch.stack(selected_spheres)

        return selected_spheres[:,:1280]
    
    def evaluate_distances(self, spheres):
        spheres = spheres.cpu().numpy()
        # Ensure vectors are in the right format
        spheres = spheres.astype('float32')

        # Get the number of vectors and their dimensionality
        num_vectors, dim = spheres.shape

        # Create a FAISS index for L2 distance
        index = faiss.IndexFlatL2(dim)
        
        # Add the vectors to the index
        index.add(spheres)

        # Retrieve and return the distances
        distance_matrix, _ = index.search(spheres, num_vectors)

        # Convert squared distances to actual distances (FAISS returns squared L2 distances)
        distance_matrix = np.sqrt(distance_matrix)

        # Calculate the lowest, highest, and mean distance, excluding self-comparisons
        lowest_distance = np.min(distance_matrix[distance_matrix != 0])
        highest_distance =  np.max(distance_matrix[distance_matrix != 0])
        mean_distance =  np.mean(distance_matrix[distance_matrix != 0])

        print(f"lowest distance: {lowest_distance}")
        print(f"highest distance: {highest_distance}")
        print(f"mean distance: {mean_distance}")
        
    def uniform_sampling(self, num_samples):
        spheres = self.rank_and_optimize_spheres()  
        dim = spheres.size(1) - 1  # Exclude radius from dimensions
        
        # Determine points to generate per sphere
        num_generated_samples = int(num_samples/self.top_k)
        points_per_sphere = max(int(num_generated_samples/self.selected_spheres), 100)
        
        clip_vectors = torch.empty((0, dim), device=self.device)  # Initialize an empty tensor for all clip vectors
        scores = []
        for sphere in spheres:
            center, radius = sphere[:-1], sphere[-1]

            # Direction adjustment based on z-scores
            z_scores = (center - self.clip_mean) / self.clip_std
            adjustment_factor = torch.clamp(torch.abs(z_scores), 0, 1)
            direction_adjustment = -torch.sign(z_scores) * adjustment_factor

            for _ in range(points_per_sphere):
                # Generate points within the sphere
                random_direction = torch.randn(dim, device=self.device)
                direction = direction_adjustment + random_direction
                direction /= torch.norm(direction)

                # Magnitude for uniform sampling within volume
                magnitude = torch.rand(1, device=self.device).pow(1/3) * radius

                point = center + direction * magnitude
                point = torch.clamp(point, self.clip_min, self.clip_max)

                # Collect generated vectors
                clip_vectors = torch.cat((clip_vectors, point.unsqueeze(0)), dim=0)
        
        # get sampled datapoint scores
        scores = self.scoring_model.predict(clip_vectors, batch_size= self.batch_size)
        # get top scoring datapoints
        _, sorted_indices = torch.sort(scores.squeeze(), descending=True)
        clip_vectors = clip_vectors[sorted_indices[:num_samples]]

        return clip_vectors
    
    def directional_uniform_sampling(self, num_samples):
        spheres = self.rank_and_optimize_spheres()  
        dim = int(spheres.size(1)/2)  # Exclude radius from dimensions
        
        # Determine points to generate per sphere
        num_generated_samples = int(num_samples/self.top_k)
        points_per_sphere = max(int(num_generated_samples/self.selected_spheres), 100)
        
        clip_vectors = torch.empty((0, dim), device=self.device)  # Initialize an empty tensor for all clip vectors
        scores = []
        for sphere in spheres:
            center, radius = sphere[:dim], sphere[dim:]

            for _ in range(points_per_sphere):
                # Generate points within the sphere
                direction = torch.randn(dim, device=self.device)
                direction /= torch.norm(direction)

                # Magnitude for uniform sampling within volume
                magnitude = torch.rand(dim, device=self.device).pow(1/3) * radius

                point = center + direction * magnitude
                point = torch.clamp(point, self.clip_min, self.clip_max)

                # Collect generated vectors
                clip_vectors = torch.cat((clip_vectors, point.unsqueeze(0)), dim=0)
        
        # get sampled datapoint scores
        scores = self.scoring_model.predict(clip_vectors, batch_size= self.batch_size)
        # get top scoring datapoints
        _, sorted_indices = torch.sort(scores.squeeze(), descending=True)
        clip_vectors = clip_vectors[sorted_indices[:num_samples]]

        return clip_vectors
    
    def optimize_datapoints(self, clip_vectors, scoring_model):
        # Calculate the total number of batches
        num_batches = len(clip_vectors) // self.batch_size + (0 if len(clip_vectors) % self.batch_size == 0 else 1)
        
        optimized_embeddings_list = []

        for batch_idx in range(num_batches):
            # Select a batch of embeddings
            start_idx = batch_idx * self.batch_size
            end_idx = min((batch_idx + 1) * self.batch_size, len(clip_vectors))
            batch_embeddings = clip_vectors[start_idx:end_idx].clone().detach().requires_grad_(True)
            
            # Setup the optimizer for the current batch
            optimizer = optim.Adam([batch_embeddings], lr=self.learning_rate)
            
            for step in range(self.steps):
                optimizer.zero_grad()

                # Compute scores for the current batch of embeddings
                scores = scoring_model.model(batch_embeddings)

                # Calculate the loss for each embedding in the batch
                score_losses = -scores.squeeze()

                # Calculate the total loss for the batch
                total_loss = score_losses.mean()

                # Backpropagate
                total_loss.backward()

                optimizer.step()

                print(f"Batch: {batch_idx + 1}/{num_batches}, Step: {step}, Mean Score: {scores.mean().item()}, Loss: {total_loss.item()}")

            # After optimization, detach and add the optimized batch embeddings to the list
            optimized_batch_embeddings = batch_embeddings.detach()
            optimized_embeddings_list.extend([emb for emb in optimized_batch_embeddings])

        return optimized_embeddings_list
    
    def generate_images(self, num_images):
        # generate clip vectors
        # if self.sphere_type=="uniform":
        #     clip_vectors= self.uniform_sampling(num_samples=num_images)
        # elif self.sphere_type=="directional":
        #     clip_vectors= self.directional_uniform_sampling(num_samples=num_images)

        clip_vectors= self.rank_and_optimize_spheres(num_images=num_images)
        
        # Optimization step
        if(self.optimize_samples):
            clip_vectors = self.optimize_datapoints(clip_vectors, self.scoring_model)

        df_data=[]

        for clip_vector in clip_vectors:
            if self.send_job:
                try:
                    response= generate_img2img_generation_jobs_with_kandinsky(
                        image_embedding=clip_vector.unsqueeze(0),
                        negative_image_embedding=None,
                        dataset_name="test-generations",
                        prompt_generation_policy=self.sampling_policy,
                        self_training=True
                    )

                    task_uuid = response['uuid']
                    task_time = response['creation_time']
                except:
                    print("An error occured.")
                    task_uuid = -1
                    task_time = -1         

            if self.save_csv:
                df_data.append({
                    'task_uuid': task_uuid,
                    'generation_policy_string': self.sampling_policy,
                    'time': task_time
                })

        if self.save_csv:
            self.store_uuids_in_csv_file(df_data)
        
        print("Jobs were sent for generation.")

    # store list of initial prompts in a csv to use for prompt mutation
    def store_uuids_in_csv_file(self, data):
        minio_path=f"{self.dataset}/output/generated-images-csv"
        local_path="output/generated_images.csv"
        pd.DataFrame(data).to_csv(local_path, index=False)
        # Read the contents of the CSV file
        with open(local_path, 'rb') as file:
            csv_content = file.read()

        #Upload the CSV file to Minio
        buffer = io.BytesIO(csv_content)
        buffer.seek(0)

        current_date=datetime.now().strftime("%Y-%m-%d-%H:%M")
        minio_path= minio_path + f"/{current_date}-{self.sampling_policy}-{self.dataset}.csv"
        cmd.upload_data(self.minio_client, 'datasets', minio_path, buffer)
        # Remove the temporary file
        os.remove(local_path)

def main():
    args= parse_args()

    # initialize generator
    generator= SphereSamplingGenerator(minio_access_key=args.minio_access_key,
                                        minio_secret_key=args.minio_secret_key,
                                        dataset=args.dataset,
                                        sphere_type= args.sphere_type,
                                        top_k= args.top_k,
                                        total_spheres= args.total_spheres,
                                        selected_spheres= args.selected_spheres,
                                        batch_size= args.batch_size,
                                        steps= args.steps,
                                        learning_rate= args.learning_rate,
                                        sampling_policy= args.sampling_policy,
                                        send_job= args.send_job,
                                        save_csv= args.save_csv,
                                        optimize_spheres= args.optimize_spheres,
                                        optimize_samples= args.optimize_samples)

    generator.generate_images(num_images=args.num_images)

if __name__ == "__main__":
    main()