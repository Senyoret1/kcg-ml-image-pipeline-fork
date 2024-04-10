import argparse
from datetime import datetime
import io
import os
import sys
import pandas as pd
import torch
import msgpack
from tqdm import tqdm

base_dir = "./"
sys.path.insert(0, base_dir)
sys.path.insert(0, os.getcwd())
from data_loader.utils import get_object
from training_worker.sampling.models.directional_uniform_sampling_regression_fc import DirectionalSamplingFCRegressionNetwork
from kandinsky_worker.image_generation.img2img_generator import generate_img2img_generation_jobs_with_kandinsky
from utility.minio import cmd

def parse_args():
        parser = argparse.ArgumentParser()

        parser.add_argument('--minio-access-key', type=str, help='Minio access key')
        parser.add_argument('--minio-secret-key', type=str, help='Minio secret key')
        parser.add_argument('--dataset', type=str, help='Name of the dataset', default="environmental")
        parser.add_argument('--num-images', type=int, help='Number of images to generate', default=100)
        parser.add_argument('--nodes-per-iteration', type=int, help='Number of nodes to evaluate each iteration', default=1000)
        parser.add_argument('--top-k', type=int, help='Number of nodes to expand on each iteration', default=10)
        parser.add_argument('--max-nodes', type=int, help='Number of maximum nodes', default=1e+7)
        parser.add_argument('--send-job', action='store_true', default=False)
        parser.add_argument('--save-csv', action='store_true', default=False)
        parser.add_argument('--sampling-policy', type=str, default="rapidly_exploring_tree_search")

        return parser.parse_args()

class RapidlyExploringTreeSearch:
    def __init__(self,
                 minio_access_key,
                 minio_secret_key,
                 dataset,
                 sampling_policy,
                 send_job,
                 save_csv):
        
        # parameters
        self.dataset= dataset  
        self.sampling_policy= sampling_policy  
        self.send_job= send_job
        self.save_csv= save_csv
        # get minio client
        self.minio_client = cmd.get_minio_client(minio_access_key=minio_access_key,
                                                minio_secret_key=minio_secret_key)
        
        # get device
        if torch.cuda.is_available():
            device = 'cuda'
        else:
            device = 'cpu'
        self.device = torch.device(device)

        self.sphere_scoring_model= DirectionalSamplingFCRegressionNetwork(minio_client=self.minio_client, dataset=dataset)
        self.sphere_scoring_model.load_model()

        # get distribution of clip vectors for the dataset
        self.clip_mean , self.clip_std, self.clip_max, self.clip_min= self.get_clip_distribution()
        self.min_radius= torch.tensor(self.sphere_scoring_model.max_scaling_factors).to(device=self.device)
        self.max_radius= torch.tensor(self.sphere_scoring_model.min_scaling_factors).to(device=self.device)
    
    def get_clip_distribution(self):
        data = get_object(self.minio_client, f"{self.dataset}/output/stats/clip_stats.msgpack")
        data_dict = msgpack.unpackb(data)

        # Convert to PyTorch tensors
        mean_vector = torch.tensor(data_dict["mean"], device=self.device, dtype=torch.float32)
        std_vector = torch.tensor(data_dict["std"], device=self.device, dtype=torch.float32)
        max_vector = torch.tensor(data_dict["max"], device=self.device, dtype=torch.float32)
        min_vector = torch.tensor(data_dict["min"], device=self.device, dtype=torch.float32)

        return mean_vector, std_vector, max_vector, min_vector

    def find_nearest_points(self, sphere, num_samples):
        dim= sphere.size(1)//2
        point = sphere[:,:dim]
        clip_vectors = torch.empty((0, dim), device=self.device)

        # Direction adjustment based on z-scores
        z_scores = (point - self.clip_mean) / self.clip_std
        adjustment_factor = torch.clamp(torch.abs(z_scores), 0, 1)
        direction_adjustment = -torch.sign(z_scores) * adjustment_factor

        for _ in range(num_samples):
            # Generate points within the sphere
            random_direction = torch.randn(dim, device=self.device)
            direction = direction_adjustment + random_direction
            direction /= torch.norm(direction)

            # Magnitude for uniform sampling within volume
            magnitude = torch.rand(1, device=self.device).pow(1/3) * 10

            point = point + direction * magnitude
            point = torch.clamp(point, self.clip_min, self.clip_max)

            # Collect generated vectors
            clip_vectors = torch.cat((clip_vectors, point), dim=0)
        
        # sample random scaling factors
        radii= torch.rand(num_samples, len(self.max_radius), device=self.device) * (self.max_radius - self.min_radius) + self.min_radius
        sphere_centers= torch.cat([clip_vectors, radii], dim=1)
        
        return sphere_centers

    def score_points(self, points):
        scores= self.sphere_scoring_model.predict(points, batch_size=1000)
        return scores

    def expand_tree(self, nodes_per_iteration, max_nodes, top_k, num_images):
        radius= torch.rand(1, len(self.max_radius), device=self.device) * (self.max_radius - self.min_radius) + self.min_radius
        sphere= torch.cat([self.clip_mean, radius], dim=1)
        current_generation = [sphere.squeeze()]
        all_nodes = []
        all_scores = torch.tensor([], dtype=torch.float32, device=self.device)
        
        # Initialize tqdm
        # pbar = tqdm(total=max_nodes)
        nodes=0
        while(nodes < max_nodes):
            print(f"{nodes} nodes generated")
            next_generation = []
            
            for point in current_generation:
                point= point.unsqueeze(0)
                # Find nearest k points to the current point
                nearest_points = self.find_nearest_points(point, nodes_per_iteration)
                
                # Score these points
                nearest_scores = self.score_points(nearest_points)
                
                # Select top n points based on scores
                _, sorted_indices = torch.sort(nearest_scores.squeeze(), descending=True)
                top_points = nearest_points[sorted_indices[:top_k]]
                top_scores = nearest_scores[sorted_indices[:top_k]]

                # Keep track of all nodes and their scores for selection later
                all_scores = torch.cat((all_scores, top_scores), dim=0)
                all_nodes.extend(top_points)

                next_generation.extend(top_points)
                nodes+= nodes_per_iteration
                # pbar.update(nodes_per_iteration)
            
            # Prepare for the next iteration
            current_generation = next_generation
        
        # Close the progress bar when done
        # pbar.close()
        
        # After the final iteration, choose the top n highest scoring points overall
        values, sorted_indices = torch.sort(all_scores.squeeze(1), descending=True)
        final_top_points = torch.stack(all_nodes, dim=0)[sorted_indices[:num_images]]

        print(f"average score: {torch.mean(values[sorted_indices[:num_images]])}")

        return final_top_points[:,:1280]
    
    def generate_images(self, nodes_per_iteration, max_nodes, top_k, num_images):
        clip_vectors= self.expand_tree(nodes_per_iteration, max_nodes, top_k, num_images)
        df_data=[]

        for clip_vector in clip_vectors:
            if self.send_job:
                try:
                    response= generate_img2img_generation_jobs_with_kandinsky(
                        image_embedding=clip_vector.unsqueeze(0),
                        negative_image_embedding=None,
                        dataset_name="test-generations",
                        prompt_generation_policy=self.sampling_policy
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
    generator= RapidlyExploringTreeSearch(minio_access_key=args.minio_access_key,
                                        minio_secret_key=args.minio_secret_key,
                                        dataset=args.dataset,
                                        sampling_policy= args.sampling_policy,
                                        send_job= args.send_job,
                                        save_csv= args.save_csv)

    generator.generate_images(nodes_per_iteration=args.nodes_per_iteration,
                          max_nodes= args.max_nodes,
                          top_k= args.top_k,
                          num_images= args.num_images)

if __name__ == "__main__":
    main()
