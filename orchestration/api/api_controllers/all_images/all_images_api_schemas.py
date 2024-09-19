from typing import List
from pydantic import BaseModel

from orchestration.api.api_controllers.all_images.all_images_db_schemas import AllImagesDbSchemas

# TODO: this is only for "/all-images/list-images-with-random-sampling". It must be removed after the endpoint is
# migrated to the new coding format.
class AllImagesResponse(BaseModel):
    uuid: str
    index: int
    bucket_id: int
    dataset_id: int
    image_hash: str
    image_path: str
    date: int    

class AllImagesApiSchemas():
    class InvalidEntriesResponse(BaseModel):
        entries: List[dict]

    class EntriesListResponse(BaseModel):
        images: List[AllImagesDbSchemas.DatabaseSchema]

    # TODO: this is only for "/all-images/list-images-with-random-sampling". It must be removed after the endpoint is
    # migrated to the new coding format.
    class ListAllImagesResponse(BaseModel):
        images: List[AllImagesResponse]
