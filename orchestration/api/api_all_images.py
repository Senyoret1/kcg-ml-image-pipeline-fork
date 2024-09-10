from fastapi import Request, APIRouter, Query
from typing import Optional
from orchestration.api.api_controllers.all_images.all_images_api_schemas import AllImagesApiSchemas
from orchestration.api.api_controllers.all_images.all_images_db_controller import AllImagesDbController
from orchestration.api.api_controllers.all_images.all_images_db_schemas import AllImagesDbSchemas
from orchestration.api.utils.api_operations_utils import ApiUtils
from orchestration.api.utils.date_filter_objects import ElapsedTimeUnit, create_date_filter_from_api_values
from .api_utils import StandardSuccessResponseV1, ApiResponseHandlerV1, ErrorCode
from typing import List

router = APIRouter()

api_tag = 'all-images'

@router.get("/all-images/list-images",
            description="Gets images from the all images collection, with filtering and pagination.",
            tags=[api_tag],
            response_model=StandardSuccessResponseV1[AllImagesApiSchemas.EntriesListResponse],
            responses=ApiResponseHandlerV1.listErrors([422, 500]))
async def list_all_images(
    request: Request,
    bucket_ids: List[int] = Query(None, description="Return only images from these bucket IDs. Images from all datasets from the bucket will be retuened"),
    dataset_ids: List[int] = Query(None, description="Return only images from these dataset IDs"),
    limit: int = Query(20, description="Limit on the number of results returned. Use it for pagination", ge=1),
    offset: int = Query(0, description="How many entries will be skipped before returning results. Use it for pagination", ge=0),
    order: ApiUtils.SortOrder = Query(ApiUtils.SortOrder.desc, description="Order in which the data should be returned. 'asc' for oldest first, 'desc' for newest first"),
    start_date: Optional[str] = Query(None, description="Start date (inclusive) for filtering results, Must be in the format 'YYYY-MM-DDTHH:MM:SS "),
    end_date: Optional[str] = Query(None, description="End date (inclusive) for filtering results, Must be in the format 'YYYY-MM-DDTHH:MM:SS"),
    time_interval: Optional[int] = Query(None, description="If set, only entries this old or newer will be returned. Use time_unit to se the time unit"),
    time_unit: Optional[ElapsedTimeUnit] = Query(None, description="If the value of 'time_interval' is in minutes or seconds")
):

    date_filter = None
    try:
        date_filter = create_date_filter_from_api_values(start_date, end_date, time_interval, time_unit)
    except Exception as e:
        return request.state.response_handler.create_error_response_v1(
            error_code=ErrorCode.INVALID_PARAMS,
            error_string=str(e),
            http_status_code=422
        )

    db_response = AllImagesDbController.get_instance().list_images_with_filtering_and_pagination(
        bucket_ids, dataset_ids, limit, offset, order, date_filter
    )

    db_response.response_content = {"images": db_response.response_content}
    return request.state.response_handler.process_normal_database_response(
        db_response
    )
    

@router.get("/all-images/get-image-by-hash", 
            description="Retrieve an image from all-images collection by its hash",
            tags=[api_tag],
            response_model=StandardSuccessResponseV1[AllImagesDbSchemas.DatabaseSchema],
            responses=ApiResponseHandlerV1.listErrors([404, 422, 500]))
async def get_image_by_hash(
    request: Request,
    image_hash: str,
    bucket_id: int = Query(None, description="If set, only images from this bucket will be considered. This may be useful if the same image is in more than one bucket"),
):
    # Find the image in the all-images collection by its hash
    db_response = AllImagesDbController.get_instance().find_image_by_hash(image_hash, bucket_id)
    
    if db_response.response_content is None:
        return request.state.api_response_handler.create_error_response_v1(
            error_code=ErrorCode.ELEMENT_NOT_FOUND, 
            error_string="Image with this hash does not exist in the all-images collection",
            http_status_code=404
        )

    # Return the found image data
    return request.state.response_handler.process_normal_database_response(
        db_response
    )

@router.get("/all-images/get-invalid-database-entries", 
            description="Gets all the entries in the database that don't follow the expected schema",
            tags=[api_tag],
            response_model=StandardSuccessResponseV1[AllImagesApiSchemas.InvalidEntriesResponse],  
            responses=ApiResponseHandlerV1.listErrors([404, 422, 500]))
async def get_image_by_hash(request: Request):
    # Find the image in the all-images collection by its hash
    db_response = AllImagesDbController.get_instance().find_images_with_invalid_schema()

    db_response.response_content = {"entries": db_response.response_content}
    return request.state.response_handler.process_normal_database_response(
        db_response
    )
