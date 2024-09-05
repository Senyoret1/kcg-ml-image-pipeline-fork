from typing import List
from pydantic import BaseModel

from orchestration.api.api_controllers.all_images.all_images_db_schemas import AllImagesDbSchemas

class AllImagesApiSchemas():
    class InvalidEntriesResponse(BaseModel):
        List[dict]

    class EntriesListResponse(BaseModel):
        images: List[AllImagesDbSchemas.DatabaseSchema]
