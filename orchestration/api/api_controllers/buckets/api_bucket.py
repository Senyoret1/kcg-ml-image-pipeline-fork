from fastapi import APIRouter, Request, Query

from orchestration.api.api_controllers.buckets.buckets_api_schemas import BucketsApiSchemas
from orchestration.api.api_controllers.buckets.buckets_db_controller import BucketsDbController
from orchestration.api.api_controllers.buckets.buckets_db_schemas import BucketsDbSchemas
from ...api_utils import WasPresentResponse, StandardSuccessResponseV1, ApiResponseHandlerV1

router = APIRouter()


@router.post("/buckets/add-new-bucket",
          description="Add a new bucket in MongoDB",
          tags=["buckets"], 
          response_model=StandardSuccessResponseV1[BucketsDbSchemas.DatabaseSchema],  
          responses=ApiResponseHandlerV1.listErrors([400,422]))
async def add_new_bucket(request: Request, bucket: BucketsApiSchemas.BucketCreationRequest):
    db_response = BucketsDbController.get_instance().add_bucket(
        BucketsDbSchemas.AddDataSchema(bucket_name=bucket.bucket_name)
    )

    return request.state.response_handler.process_normal_database_response(
        db_response
    )

@router.get("/buckets/list-buckets", 
         status_code=200, 
         description="List all buckets",
         tags=["buckets"],
         response_model=StandardSuccessResponseV1[BucketsApiSchemas.EntriesListResponse])
async def list_buckets(request: Request):
    db_response = BucketsDbController.get_instance().list_all_buckets()
    db_response.response_content = {"buckets": db_response.response_content}

    return request.state.response_handler.process_normal_database_response(
        db_response
    )

@router.delete("/buckets/remove-bucket",
               description="Remove bucket in MongoDB",
               tags=["buckets"],
               response_model=StandardSuccessResponseV1[WasPresentResponse],  
               responses=ApiResponseHandlerV1.listErrors([422]))
async def remove_bucket(request: Request, bucket_id: int = Query(...)):
    db_response = BucketsDbController.get_instance().delete_bucket_by_id(bucket_id)

    return request.state.response_handler.process_deletion_database_response(
        db_response, True
    )

@router.get("/buckets/get-invalid-database-entries", 
            description="Gets all the entries in the database that don't follow the expected schema",
            tags=["buckets"],
            response_model=StandardSuccessResponseV1[BucketsApiSchemas.InvalidEntriesResponse],  
            responses=ApiResponseHandlerV1.listErrors([404, 422, 500]))
async def get_image_by_hash(request: Request):
    db_response = BucketsDbController.get_instance().find_buckets_with_invalid_schema()

    db_response.response_content = {"entries": db_response.response_content}
    return request.state.response_handler.process_normal_database_response(
        db_response
    )
