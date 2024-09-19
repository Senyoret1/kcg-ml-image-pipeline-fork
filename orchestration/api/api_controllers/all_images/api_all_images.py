from datetime import datetime, timedelta
from fastapi import HTTPException, Request, APIRouter, Query
from typing import Optional
from orchestration.api.api_controllers.all_images.all_images_api_schemas import AllImagesApiSchemas
from orchestration.api.api_controllers.all_images.all_images_db_controller import AllImagesDbController
from orchestration.api.api_controllers.all_images.all_images_db_schemas import AllImagesDbSchemas
from orchestration.api.utils.api_operations_utils import ApiUtils
from orchestration.api.utils.date_filter_objects import ApiDateFilterCreationError, ElapsedTimeUnit, create_date_filter_from_api_values
from orchestration.api.utils.uuid64 import Uuid64
from ...api_utils import StandardSuccessResponseV1, ApiResponseHandlerV1, ErrorCode, api_date_to_unix_int32
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

    date_filter = create_date_filter_from_api_values(start_date, end_date, time_interval, time_unit)
    if isinstance(date_filter, ApiDateFilterCreationError):
        return request.state.response_handler.create_error_response_v1(
            error_code=ErrorCode.INVALID_PARAMS,
            error_string=str(date_filter.error_msg),
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
    db_response = AllImagesDbController.get_instance().find_single_image(image_hash, bucket_id)
    
    if db_response.response_content is None:
        return request.state.response_handler.create_error_response_v1(
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
    db_response = AllImagesDbController.get_instance().find_images_with_invalid_schema()

    db_response.response_content = {"entries": db_response.response_content}
    return request.state.response_handler.process_normal_database_response(
        db_response
    )

# TODO: this must be updated to the new coding format
@router.get("/all-images/list-images-with-random-sampling",
            description="list images according to dataset_name and bucket_name",
            tags=["all-images"],
            response_model=StandardSuccessResponseV1[AllImagesApiSchemas.ListAllImagesResponse],
            responses=ApiResponseHandlerV1.listErrors([422, 500]))
async def list_all_images(
    request: Request,
    bucket_name: str = Query(..., description="Bucket Name"),
    dataset_name: str = Query(..., description="Dataset Name"),
    limit: int = Query(20, description="Limit on the number of results returned"),
    start_date: Optional[str] = Query(None, description="Start date for filtering results, Must be in the format 'YYYY-MM-DDTHH:MM:SS'"),
    end_date: Optional[str] = Query(None, description="End date for filtering results, Must be in the format 'YYYY-MM-DDTHH:MM:SS'"),
    time_interval: Optional[int] = Query(None, description="Time interval in minutes or hours"),
    time_unit: str = Query("minutes", description="Time unit, either 'minutes' or 'hours'"),
    random_sampling: bool = Query(True, description="If True, apply random sampling to the results")
):
    response_handler = await ApiResponseHandlerV1.createInstance(request)
    try:
        bucket = request.app.buckets_collection.find_one({"bucket_name": bucket_name}, {"bucket_id": 1})
        if not bucket:
            return response_handler.create_error_response_v1(
                error_code=ErrorCode.ELEMENT_NOT_FOUND,
                error_string="Bucket not found",
                http_status_code=422
            )
        bucket_id = bucket["bucket_id"]

        dataset = request.app.datasets_collection.find_one({"dataset_name": dataset_name, "bucket_id": bucket_id}, {"dataset_id": 1})
        if not dataset:
            return response_handler.create_error_response_v1(
                error_code=ErrorCode.ELEMENT_NOT_FOUND,
                error_string="Dataset not found",
                http_status_code=422
            )
        dataset_id = dataset["dataset_id"]

        # Step 3: Build the query for all_images_collection using bucket_id and dataset_id
        query = {
            "bucket_id": bucket_id,
            "dataset_id": dataset_id
        }

        # Add date filters to the query
        date_query = {}
        if start_date:
            start_date_unix = api_date_to_unix_int32(start_date)
            if start_date_unix is None:
                return response_handler.create_error_response_v1(
                    error_code=ErrorCode.OTHER_ERROR,
                    error_string="Invalid start_date format. Expected format: YYYY-MM-DDTHH:MM:SS",
                    http_status_code=422
                )
            date_query['$gte'] = start_date_unix
        if end_date:
            end_date_unix = api_date_to_unix_int32(end_date)
            if end_date_unix is None:
                return response_handler.create_error_response_v1(
                    error_code=ErrorCode.OTHER_ERROR,
                    error_string="Invalid end_date format. Expected format: YYYY-MM-DDTHH:MM:SS",
                    http_status_code=422
                )
            date_query['$lte'] = end_date_unix

        print(f"Date query after adding start_date and end_date: {date_query}")

        # Calculate the time threshold based on the current time and the specified interval
        if time_interval is not None:
            current_time = datetime.utcnow()
            if time_unit == "minutes":
                threshold_time = current_time - timedelta(minutes=time_interval)
            elif time_unit == "hours":
                threshold_time = current_time - timedelta(hours=time_interval)
            else:
                raise HTTPException(status_code=400, detail="Invalid time unit. Use 'minutes' or 'hours'.")
            date_query['$gte'] = int(threshold_time.timestamp())

        if date_query:
            query['date'] = date_query

        print(f"Final query: {query}")

        if random_sampling:
            cursor = request.app.all_image_collection.aggregate([
                {"$match": query},
                {"$sample": {"size": limit}}
            ])
        else:
            cursor = request.app.all_image_collection.find(query).limit(limit)

        images = list(cursor)

        print(f"Number of images found: {len(images)}")

        #AllImagesHelpers.clean_image_list_for_api_response(images)
        for data in images:
            data.pop('_id', None)

            if "uuid" in data:
                if isinstance(data['uuid'], int):
                    uuid64 = Uuid64.from_mongo_value(data['uuid'])
                    data['uuid'] = uuid64.to_formatted_str()
                if isinstance(data['uuid'], Uuid64):
                    data['uuid'] = data['uuid'].to_formatted_str()

        return response_handler.create_success_response_v1(
            response_data={"images": images},
            http_status_code=200
        )

    except Exception as e:
        print(f"Exception: {e}")
        return response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR,
            error_string=str(e),
            http_status_code=500
        )
