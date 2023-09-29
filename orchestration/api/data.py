from fastapi import Request, HTTPException, APIRouter
from orchestration.api.schemas import SequentialID
import json
from utility.path import separate_bucket_and_file_path
from PIL import Image
from io import BytesIO
router = APIRouter()


@router.get("/get-random-image/{dataset}")
def get_job(request: Request, dataset: str = None):
    # find
    documents = request.app.completed_jobs_collection.aggregate([
        {"$match": {"task_input_dict.dataset": dataset}},
        {"$sample": {"size": 1}}
    ])

    # convert curser type to list
    documents = list(documents)
    if len(documents) == 0:
        raise HTTPException(status_code=404)

    # get only the first index
    document = documents[0]

    # remove the auto generated field
    document.pop('_id', None)

    # get image from minio server
    # Get data of an object.
    output_file_path = document["task_output_file_dict"]["output_file_path"]
    bucket_name, file_path = separate_bucket_and_file_path(output_file_path)
    try:
        response = request.app.minio_client.get_object(bucket_name, file_path)
        image_data = BytesIO(response.data)
        img = Image.open(image_data)
        # add to document
        document["image-data"] = img
    finally:
        response.close()
        response.release_conn()

    return document