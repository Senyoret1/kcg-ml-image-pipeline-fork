import json
from pymongo import MongoClient
from minio import Minio
from io import BytesIO
from minio.error import S3Error
import sys
import io
base_directory = "./"
sys.path.insert(0, base_directory)
from utility.minio import cmd

mongo_client = MongoClient('mongodb://192.168.3.1:32017/')
db = mongo_client['orchestration-job-db']  
collection = db['image_tags']  

minio_client = Minio(
    "192.168.3.5:9000",  
    access_key="v048BpXpWrsVIHUfdAix", 
    secret_key="4TFS20qkxVuX2HaC8ezAgG7GaDlVI1TqSPs0BKyu", 
    secure=False  
)

bucket_name = "tags"  

# Ensure bucket exists
if not cmd.check_if_bucket_exists(minio_client, bucket_name):
    cmd.create_bucket(minio_client, bucket_name)

# Fetch all documents from MongoDB 
documents = collection.find()

# Iterate over each document
for doc in documents:
    try:
        # Define file name based on 'tag_id', 'tag_type', and 'image_hash'
        file_name = f"{doc['tag_id']}-{doc['tag_type']}-{doc['image_hash']}.json"

        # Check if the file already exists in the Minio bucket
        try:
            minio_client.stat_object(bucket_name, file_name)
            print(f"File {file_name} already exists in the bucket, skipping upload.")
            continue  # Skip this file since it already exists
        except S3Error as stat_error:
            if stat_error.code != 'NoSuchKey':
                print(f"Error while checking if file exists: {stat_error}")
                continue  # Skip this iteration if there's an error other than 'NoSuchKey'

        # Remove the '_id' field before uploading the document
        doc.pop('_id', None)

        # Convert the MongoDB document to JSON format
        json_data = json.dumps(doc, default=str)

        # Upload the JSON file to Minio
        minio_client.put_object(
            bucket_name=bucket_name,
            object_name=file_name,
            data=io.BytesIO(json_data.encode('utf-8')),
            length=len(json_data),
            content_type='application/json'
        )

        print(f"Uploaded {file_name} to Minio.")

    except S3Error as e:
        print(f"Failed to upload {file_name}: {str(e)}")
