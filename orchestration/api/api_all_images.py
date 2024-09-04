from fastapi import Request, HTTPException, APIRouter, Response, Query, status, File, UploadFile
from datetime import datetime, timedelta
from typing import Optional
import pymongo
from orchestration.api.api_controllers.all_images.all_images_db_controller import AllImagesDbController
from orchestration.api.utils.date_filter_objects import DateFilterParams, ElapsedTimeFilterParams, ElapsedTimeUnit
from orchestration.api.utils.datetime_utils import DatetimeUtils
from utility.minio import cmd
from utility.path import separate_bucket_and_file_path
from .mongo_schemas import Task, ImageMetadata, UUIDImageMetadata, ListTask
from .api_utils import PrettyJSONResponse, StandardSuccessResponseV1, ApiResponseHandlerV1, WasPresentResponse, ErrorCode, api_date_to_unix_int32
from .api_ranking import get_image_rank_use_count
import os
from .api_utils import find_or_create_next_folder_and_index
from orchestration.api.mongo_schema.all_images_schemas import AllImagesHelpers, AllImagesResponse, ListAllImagesResponse
import io
from typing import List
from PIL import Image
import time

router = APIRouter()

@router.get("/all-images/list-images",
            description="list images according dataset_id and bucket_id",
            tags=["all-images"],
            response_model=StandardSuccessResponseV1[ListAllImagesResponse],
            responses=ApiResponseHandlerV1.listErrors([422, 500]))
async def list_all_images(
    request: Request,
    bucket_ids: Optional[List[int]] = Query(None, description="Bucket IDs"),
    dataset_ids: Optional[List[int]] = Query(None, description="Dataset IDs"),
    limit: int = Query(20, description="Limit on the number of results returned"),
    offset: int = Query(0, description="Offset for the results to be returned"),
    order: str = Query("desc", description="Order in which the data should be returned. 'asc' for oldest first, 'desc' for newest first"),
    start_date: Optional[str] = Query(None, description="Start date for filtering results, Must be in the format 'YYYY-MM-DDTHH:MM:SS "),
    end_date: Optional[str] = Query(None, description="End date for filtering results, Must be in the format 'YYYY-MM-DDTHH:MM:SS"),
    time_interval: Optional[int] = Query(None, description="Time interval in minutes or hours"),
    time_unit: str = Query("minutes", description="Time unit, either 'minutes' or 'hours'")
):
    response_handler = await ApiResponseHandlerV1.createInstance(request)
    try:
        date_filter = None
        if time_interval != None:
            if (time_unit != 'minutes' and time_unit != 'hours'):
                return response_handler.create_error_response_v1(
                    error_code=ErrorCode.OTHER_ERROR,
                    error_string="Invalid time_unit value",
                    http_status_code=422
                )

            date_filter = ElapsedTimeFilterParams.create_instance(
                ElapsedTimeUnit.HOURS if time_unit == 'hours' else ElapsedTimeUnit.MINUTES,
                time_interval
            )
        elif start_date != None or end_date != None:
            date_filter = DateFilterParams.create_instance(
                DatetimeUtils.get_datetime_from_api_string(start_date) if start_date != None else None,
                DatetimeUtils.get_datetime_from_api_string(end_date) if end_date != None else None
            )

        images = AllImagesDbController.get_instance().list_images_with_filtering_and_pagination(
            bucket_ids, dataset_ids, limit, offset, order == 'asc', date_filter
        )

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
    

@router.get("/all-images/get-image-by-hash", 
            description="Retrieve an image from all-images collection by its hash",
            tags=["all-images"],  
            response_model=StandardSuccessResponseV1[AllImagesResponse],  
            responses=ApiResponseHandlerV1.listErrors([404, 422, 500]))
async def get_image_by_hash(request: Request, image_hash: str):
    api_response_handler = await ApiResponseHandlerV1.createInstance(request)
    
    try:
        # Find the image in the all-images collection by its hash
        image_data = AllImagesDbController.get_instance().find_image_by_hash(image_hash)
        
        if image_data is None:
            return api_response_handler.create_error_response_v1(
                error_code=ErrorCode.ELEMENT_NOT_FOUND, 
                error_string="Image with this hash does not exist in the all-images collection",
                http_status_code=404
            )

        # Return the found image data
        return api_response_handler.create_success_response_v1(
            response_data=image_data,
            http_status_code=200  
        )
    
    except Exception as e:
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR, 
            error_string=str(e),
            http_status_code=500
        )
