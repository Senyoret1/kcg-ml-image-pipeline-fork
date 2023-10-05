from fastapi import Request, HTTPException, APIRouter, Response

from orchestration.api.schemas import Selection
import json
import os
from datetime import datetime
from utility.minio import cmd
from utility.path import separate_bucket_and_file_path, file_exists
from PIL import Image
from io import BytesIO
import base64

router = APIRouter()


@router.get("/get-datasets")
def get_datasets(request: Request):
    objects = cmd.get_list_of_objects(request.app.minio_client, "datasets")

    return objects

@router.post("/add-selection-datapoint/{dataset}")
def add_selection_datapoint(request: Request, dataset: str, selection: Selection):
    time = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    selection.datetime = time

    # prepare path
    file_name = "{}-{}.json".format(time, selection.username)
    path = "data/ranking/aggregate"
    full_path = os.path.join(dataset, path, file_name)

    # convert to bytes
    dict_data = selection.to_dict()
    json_data = json.dumps(dict_data, indent=4).encode('utf-8')
    data = BytesIO(json_data)

    # upload
    cmd.upload_data(request.app.minio_client, "datasets", full_path, data)

    return True
