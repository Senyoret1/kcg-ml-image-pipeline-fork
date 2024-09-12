from typing import List
from pydantic import BaseModel

from orchestration.api.api_controllers.buckets.buckets_db_schemas import BucketsDbSchemas

class BucketsApiSchemas():
    class InvalidEntriesResponse(BaseModel):
        entries: List[dict]

    class EntriesListResponse(BaseModel):
        images: List[BucketsDbSchemas.DatabaseSchema]
    
    class BucketCreationRequest(BaseModel):
        bucket_name: str
