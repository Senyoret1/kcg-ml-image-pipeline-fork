from minio import Minio
import json
import io
from tqdm import tqdm

# MinIO setup
minio_client = Minio(
    '192.168.3.5:9000',  
    access_key='v048BpXpWrsVIHUfdAix',  
    secret_key='4TFS20qkxVuX2HaC8ezAgG7GaDlVI1TqSPs0BKyu', 
    secure=False  # Set to True if using HTTPS
)

rank_model_id = 10
source_bucket_name = 'datasets'  
destination_bucket_name = 'datasets'  
source_path = 'test-generations/data/ranking/aggregate'  
destination_path = f'ranks/{rank_model_id}/data/ranking/aggregate'  

# Ensure the destination bucket exists
if not minio_client.bucket_exists(destination_bucket_name):
    minio_client.make_bucket(destination_bucket_name)

# List all objects in the source bucket with the given source path
objects = minio_client.list_objects(source_bucket_name, prefix=source_path, recursive=True)
objects = list(objects)  # Convert generator to list for tqdm

total_objects = len(objects)
print(f"Total JSON files to migrate: {total_objects}")

# Iterate over objects and copy them to the destination bucket
for obj in tqdm(objects, desc="Migrating JSON files"):
    if obj.object_name.endswith('.json'):
        # Get the object from the source bucket
        response = minio_client.get_object(source_bucket_name, obj.object_name)
        
        # Read JSON data from the object
        json_data = json.loads(response.data)
        response.close()
        response.release_conn()

        # Add rank_model_id as the first field in the JSON data
        json_data = {"rank_model_id": rank_model_id, **json_data}

        # Convert the modified JSON data back to a JSON string with indentation
        json_data_str = json.dumps(json_data, indent=4)

        # Define the object name in the destination bucket
        destination_object_name = obj.object_name.replace(source_path, destination_path)

        # Upload the JSON data to the destination bucket
        minio_client.put_object(
            destination_bucket_name,
            destination_object_name,
            data=io.BytesIO(json_data_str.encode('utf-8')),
            length=len(json_data_str),
            content_type='application/json'
        )

print("Migration of JSON files to MinIO completed successfully!")