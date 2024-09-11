from fastapi import Request, APIRouter, Query
from .api_utils import PrettyJSONResponse, ErrorCode, WasPresentResponse, ApiResponseHandlerV1, StandardSuccessResponseV1, CountResponse
from orchestration.api.mongo_schemas import ClassifierScore, ListClassifierScore, ClassifierScoreRequest, ClassifierScoreV1, ListClassifierScore1, ListClassifierScore2, ListClassifierScore3, BatchClassifierScoreRequest, ListClassifierScore4
from fastapi.encoders import jsonable_encoder
import uuid
from typing import Optional
from datetime import datetime
from pymongo import UpdateOne
import time
from typing import List



router = APIRouter()


generated_image = "generated_image"


# Updated apis
  

@router.get("/pseudotag-classifier-scores/get-image-classifier-score-by-hash-and-classifier-id", 
            description="Get image classifier score by classifier_id and image_hash",
            status_code=200,
            tags=["pseudotag-classifier-scores"],  
            response_model=StandardSuccessResponseV1[ClassifierScoreV1],  
            responses=ApiResponseHandlerV1.listErrors([400, 422, 404]))
def get_image_classifier_score_by_hash(
    request: Request, 
    image_hash: str, 
    classifier_id: int, 
    image_source: Optional[str] = Query(..., regex="^(generated_image|extract_image|external_image)$")
):
    api_response_handler = ApiResponseHandlerV1(request)

    # Check if exists
    query = {"image_hash": image_hash, "classifier_id": classifier_id}
    if image_source:
        query["image_source"] = image_source

    item = request.app.image_classifier_scores_collection.find_one(query)

    if item is None:
        # Return a standardized error response if not found
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.INVALID_PARAMS,
            error_string="Score for specified classifier_id, image_hash, and image_source does not exist.",
            http_status_code=404
        )

    # Remove the auto-generated '_id' field before returning
    item.pop('_id', None)

    # Return a standardized success response
    return api_response_handler.create_success_response_v1(
        response_data=item,
        http_status_code=200
    )



@router.get("/pseudotag-classifier-scores/get-image-classifier-score-by-uuid-and-classifier-id", 
            description="Get image classifier score by uuid and classifier_id",
            status_code=200,
            tags=["pseudotag-classifier-scores"],  
            response_model=StandardSuccessResponseV1[ClassifierScoreV1],  
            responses=ApiResponseHandlerV1.listErrors([400,422]))
def get_image_classifier_score_by_uuid_and_classifier_id(request: Request, 
                                                         job_uuid: str = Query(..., description="The UUID of the job"), 
                                                         classifier_id: int = Query(..., description="The classifier ID")):
    api_response_handler = ApiResponseHandlerV1(request)

    # Adjust query to include classifier_id
    query = {
        "uuid": job_uuid,
        "classifier_id": classifier_id
    }

    item = request.app.image_classifier_scores_collection.find_one(query)

    if item is None:
        # Return a standardized error response if not found
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.INVALID_PARAMS,
            error_string="Score for specified uuid and classifier_id does not exist.",
            http_status_code=404
        )

    # Remove the auto generated '_id' field before returning
    item.pop('_id', None)

    # Return a standardized success response
    return api_response_handler.create_success_response_v1(
        response_data=item,
        http_status_code=200
    )



@router.post("/pseudotag-classifier-scores/set-image-classifier-score", 
             status_code=200,
             response_model=StandardSuccessResponseV1[ClassifierScoreV1],
             description="Set classifier image score",
             tags=["pseudotag-classifier-scores"], 
             responses=ApiResponseHandlerV1.listErrors([404, 422, 500]) 
             )
async def set_image_classifier_score(request: Request, classifier_score: ClassifierScoreRequest):
    api_response_handler = await ApiResponseHandlerV1.createInstance(request)

    try:
        # Fetch image_hash from completed_jobs_collection
        job_data = request.app.completed_jobs_collection.find_one({"uuid": classifier_score.job_uuid},  {"task_output_file_dict.output_file_hash": 1, "task_type": 1, "image_uuid": 1})

        if not job_data:
            return api_response_handler.create_error_response_v1(
                error_code=ErrorCode.INVALID_PARAMS,
                error_string="The provided UUID does not exist in completed_jobs_collection.",
                http_status_code=404
            )
        
        if 'task_output_file_dict' not in job_data or 'output_file_hash' not in job_data['task_output_file_dict']:
            return api_response_handler.create_error_response_v1(
                error_code=ErrorCode.INVALID_PARAMS,
                error_string="The provided UUID does not have an associated image hash.",
                http_status_code=404
            )

        image_hash = job_data['task_output_file_dict']['output_file_hash']
        task_type = job_data['task_type']
        image_uuid = job_data.get('image_uuid', None)

        if image_uuid is None:
            return api_response_handler.create_error_response_v1(
                error_code=ErrorCode.INVALID_PARAMS,
                error_string="No valid image UUID found in the job.",
                http_status_code=404
            )

        print(f"Image UUID: {image_uuid}")

        # Fetch tag_id from classifier_models_collection
        classifier_data = request.app.classifier_models_collection.find_one({"classifier_id": classifier_score.classifier_id}, {"tag_id": 1})

        if not classifier_data:
            return api_response_handler.create_error_response_v1(
                error_code=ErrorCode.INVALID_PARAMS,
                error_string="The provided classifier ID does not exist.",
                http_status_code=404
            )
        tag_id = classifier_data['tag_id']

        query = {
            "classifier_id": classifier_score.classifier_id,
            "uuid": classifier_score.job_uuid,
            "tag_id": tag_id
        }

        # Get current UTC time in ISO format
        current_utc_time = datetime.utcnow().isoformat()

        new_score_data = {
            "uuid": classifier_score.job_uuid,
            "task_type": task_type,
            "classifier_id": classifier_score.classifier_id,
            "tag_id": tag_id,
            "score": classifier_score.score,
            "image_hash": image_hash,
            "creation_time": current_utc_time,
            "image_source": "generated_image",
            "image_uuid": image_uuid
        }

        # Check for existing score and update or insert accordingly
        existing_score = request.app.image_classifier_scores_collection.find_one(query)
        if existing_score:
            # Update existing score
            request.app.image_classifier_scores_collection.update_one(
                query,
                {"$set": {
                    "score": classifier_score.score,
                    "image_hash": image_hash,
                    "creation_time": current_utc_time
                }}
            )
        else:
            # Insert new score
            insert_result = request.app.image_classifier_scores_collection.insert_one(new_score_data)
            new_score_data['_id'] = str(insert_result.inserted_id)
            new_score_data.pop('_id', None)

        return api_response_handler.create_success_response_v1(
            response_data=new_score_data,
            http_status_code=200  
        )
    
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR, 
            error_string=str(e),
            http_status_code=500
        )



@router.delete("/pseudotag-classifier-scores/delete-image-classifier-score-by-uuid-and-classifier-id", 
               description="Delete image classifier score by specific uuid and classifier id.",
               status_code=200,
               tags=["pseudotag-classifier-scores"],
               response_model=StandardSuccessResponseV1[WasPresentResponse],
               responses=ApiResponseHandlerV1.listErrors([422]))
async def delete_image_classifier_score_by_uuid_and_classifier_id(
    request: Request,
    job_uuid: str,
    classifier_id: int = Query(..., description="The classifier ID")):

    api_response_handler = await ApiResponseHandlerV1.createInstance(request)
    
    query = {
        "uuid": job_uuid,
        "classifier_id": classifier_id  
    }
    res = request.app.image_classifier_scores_collection.delete_one(query)
    # Return a standard response with wasPresent set to true if there was a deletion
    return api_response_handler.create_success_delete_response_v1(res.deleted_count != 0)


import logging


@router.get("/pseudotag-classifier-scores/count-all-saved-scores", 
            response_model=StandardSuccessResponseV1[CountResponse],
            status_code=200,
            tags=["pseudotag-classifier-scores"],
            description="Counts the number of documents in the image classifier scores collection",
            responses=ApiResponseHandlerV1.listErrors([500]))
async def count_classifier_scores(request: Request):
    api_response_handler = await ApiResponseHandlerV1.createInstance(request)
    try:
        # Count documents in the image_classifier_scores_collection
        count = request.app.image_classifier_scores_collection.count_documents({})

        return api_response_handler.create_success_response_v1(
            response_data={"count": count},
            http_status_code=200  
        )
    
    except Exception as e:
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR, 
            error_string=str(e),
            http_status_code=500
        )       


@router.post("/pseudotag-classifier-scores/set-image-classifier-score-list", 
             status_code=200,
             response_model=StandardSuccessResponseV1[ClassifierScoreV1],
             description="changed with /pseudotag-classifier-scores/set-image-classifier-score-list-v1 ",
             tags=["deprecated3"], 
             responses=ApiResponseHandlerV1.listErrors([404, 422, 500]) 
             )
async def set_image_classifier_score_list(request: Request, classifier_score_list: List[ClassifierScoreRequest]):
    api_response_handler = await ApiResponseHandlerV1.createInstance(request)
    new_score_data_list = []
    try:
        for classifier_score in classifier_score_list:
            # Fetch image_hash from completed_jobs_collection
            job_data = request.app.completed_jobs_collection.find_one({"uuid": classifier_score.job_uuid},  {"task_output_file_dict.output_file_hash": 1, "task_type": 1, "image_uuid": 1})
            if not job_data or 'task_output_file_dict' not in job_data or 'output_file_hash' not in job_data['task_output_file_dict']:
                return api_response_handler.create_error_response_v1(
                    error_code=ErrorCode.INVALID_PARAMS,
                    error_string="The provided UUID does not have an associated image hash.",
                    http_status_code=404
                )
            image_hash = job_data['task_output_file_dict']['output_file_hash']
            image_uuid = job_data.get('image_uuid', None)
            # Fetch tag_id from classifier_models_collection
            classifier_data = request.app.classifier_models_collection.find_one({"classifier_id": classifier_score.classifier_id}, {"tag_id": 1})
            if not classifier_data:
                return api_response_handler.create_error_response_v1(
                    error_code=ErrorCode.INVALID_PARAMS,
                    error_string="The provided classifier ID does not exist.",
                    http_status_code=404
                )
            tag_id = classifier_data['tag_id']
            
            query = {
                "classifier_id": classifier_score.classifier_id,
                "uuid": classifier_score.job_uuid,
                "tag_id": tag_id
            }
            # Get current UTC time in ISO format
            current_utc_time = datetime.utcnow().isoformat()
            # Initialize new_score_data outside of the if/else block
            new_score_data = {
                "uuid": classifier_score.job_uuid,
                "classifier_id": classifier_score.classifier_id,
                "tag_id": tag_id,
                "score": classifier_score.score,
                "image_hash": image_hash,
                "creation_time": current_utc_time,
                "image_source": generated_image,
                "image_uuid": image_uuid
            }
            # Check for existing score and update or insert accordingly
            existing_score = request.app.image_classifier_scores_collection.find_one(query)
            if existing_score:
                # Update existing score
                request.app.image_classifier_scores_collection.update_one(query, {"$set": {"score": classifier_score.score, "image_hash": image_hash, "creation_time": current_utc_time}})
            else:
                # Insert new score
                insert_result = request.app.image_classifier_scores_collection.insert_one(new_score_data)
                new_score_data['_id'] = str(insert_result.inserted_id)
                new_score_data_list.append(new_score_data)
        return api_response_handler.create_success_response_v1(
            response_data={
                "data":new_score_data_list
            },
            http_status_code=200  
        )
    
    except Exception as e:
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR, 
            error_string=str(e),
            http_status_code=500
        )


@router.get("/pseudotag-classifier-scores/list-images-by-scores-v3", 
            description="changed with /pseudotag-classifier-scores/list-images-by-scores-v5",
            tags=["deprecated3"],  
            response_model=StandardSuccessResponseV1[ListClassifierScore1],  
            responses=ApiResponseHandlerV1.listErrors([400, 422]))
async def list_image_scores_v3(
    request: Request,
    classifier_id: Optional[int] = Query(None, description="Filter by classifier ID"),
    task_type: Optional[str] = Query(None, description="Filter by task_type"),
    min_score: Optional[float] = Query(None, description="Minimum score"),
    max_score: Optional[float] = Query(None, description="Maximum score"),
    limit: int = Query(10, description="Limit on the number of results returned"),
    offset: int = Query(0, description="Offset for pagination"),
    order: str = Query("desc", description="Sort order: 'asc' for ascending, 'desc' for descending"),
    random_sampling: bool = Query(True, description="Enable random sampling"),
    image_source: Optional[str] = Query(None, regex="^(generated_image|extract_image|external_image)$", description="The source of the image")
):
    response_handler = await ApiResponseHandlerV1.createInstance(request)
    start_time = time.time()  # Start time tracking

    print("Building query...")
    # Build the query based on provided filters
    query = {}
    if image_source is not None:
        query["image_source"] = image_source
    if classifier_id is not None:
        query["classifier_id"] = classifier_id
    if task_type is not None:
        query["task_type"] = task_type
    if min_score is not None and max_score is not None:
        query["score"] = {"$gte": min_score, "$lte": max_score}
    elif min_score is not None:
        query["score"] = {"$gte": min_score}
    elif max_score is not None:
        query["score"] = {"$lte": max_score}

    print("Query built. Time taken:", time.time() - start_time)

    # Modify behavior based on random_sampling parameter
    if random_sampling:
        # Apply some filtering before sampling
        query_filter = {"$match": query}  
        sampling_stage = {"$sample": {"size": limit}}  # Random sampling with a limit
        
        # Build the optimized pipeline
        pipeline = [query_filter, sampling_stage]

        cursor = request.app.image_classifier_scores_collection.aggregate(pipeline)

    else:
        # Determine sort order and fetch sorted data when random_sampling is False
        sort_order = 1 if order == "asc" else -1
        cursor = request.app.image_classifier_scores_collection.find(query).sort([("score", sort_order)]).skip(offset).limit(limit)
    
    print("Data fetched. Time taken:", time.time() - start_time)

    scores_data = list(cursor)

    # Remove _id in response data
    for score in scores_data:
        score.pop('_id', None)

    print("Returning response. Total time:", time.time() - start_time)

    # Return the fetched data with a success response
    return response_handler.create_success_response_v1(
        response_data=scores_data,  # Directly return the fetched data
        http_status_code=200
    )


@router.get("/pseudotag-classifier-scores/list-images-by-scores-v5", 
            description="List image scores based on classifier",
            tags=["pseudotag-classifier-scores"],  
            response_model=StandardSuccessResponseV1[ListClassifierScore1],  
            responses=ApiResponseHandlerV1.listErrors([400, 422]))
async def list_image_scores_v5(
    request: Request,
    classifier_id: Optional[int] = Query(None, description="Filter by classifier ID"),
    task_type: Optional[str] = Query(None, description="Filter by task_type"),
    min_score: Optional[float] = Query(None, description="Minimum score"),
    max_score: Optional[float] = Query(None, description="Maximum score"),
    limit: int = Query(10, description="Limit on the number of results returned"),
    offset: int = Query(0, description="Offset for pagination"),
    order: str = Query("desc", description="Sort order: 'asc' for ascending, 'desc' for descending"),
    random_sampling: bool = Query(True, description="Enable random sampling"),
    image_sources: Optional[str] = Query(None, description="The source of the image (comma-separated values: generated_image,extract_image,external_image)")
):
    response_handler = await ApiResponseHandlerV1.createInstance(request)
    start_time = time.time()  # Start time tracking

    print("Building query...")

    # Validate image_sources
    valid_image_sources = {"generated_image", "extract_image", "external_image"}
    image_sources_list = []
    if image_sources:
        image_sources_list = image_sources.split(',')
        invalid_sources = [src for src in image_sources_list if src not in valid_image_sources]
        if invalid_sources:
            return response_handler.create_error_response_v1(
                error_code=ErrorCode.INVALID_PARAMS, 
                error_string=f"Invalid image_sources: {', '.join(invalid_sources)}",
                http_status_code=422
            )
        # Remove duplicates
        image_sources_list = list(set(image_sources_list))

    # Build the query based on provided filters
    query = {}
    if image_sources_list:
        query["image_source"] = {"$in": image_sources_list}
    if classifier_id is not None:
        query["classifier_id"] = classifier_id
    if task_type is not None:
        query["task_type"] = task_type
    if min_score is not None and max_score is not None:
        query["score"] = {"$gte": min_score, "$lte": max_score}
    elif min_score is not None:
        query["score"] = {"$gte": min_score}
    elif max_score is not None:
        query["score"] = {"$lte": max_score}

    print("Query built. Time taken:", time.time() - start_time)

    # Modify behavior based on random_sampling parameter
    if random_sampling:
        # Apply some filtering before sampling
        query_filter = {"$match": query}  
        sampling_stage = {"$sample": {"size": limit}}  # Random sampling with a limit
        
        # Build the optimized pipeline
        pipeline = [query_filter, sampling_stage]

        cursor = request.app.image_classifier_scores_collection.aggregate(pipeline)

    else:
        # Determine sort order and fetch sorted data when random_sampling is False
        sort_order = 1 if order == "asc" else -1
        cursor = request.app.image_classifier_scores_collection.find(query).sort([("score", sort_order)]).skip(offset).limit(limit)
    
    print("Data fetched. Time taken:", time.time() - start_time)

    scores_data = list(cursor)

    # Remove _id in response data
    for score in scores_data:
        score.pop('_id', None)

    print("Returning response. Total time:", time.time() - start_time)

    # Return the fetched data with a success response
    return response_handler.create_success_response_v1(
        response_data={"images": scores_data},  # Directly return the fetched data
        http_status_code=200
    )



@router.get("/pseudotag-classifier-scores/list-classifier-scores-for-image",
            description="Get all scores for a specific image hash",
            tags=["pseudotag-classifier-scores"],  
            response_model=StandardSuccessResponseV1[ListClassifierScore2],
            responses=ApiResponseHandlerV1.listErrors([404, 422]))
async def get_scores_by_image_hash(
    request: Request,
    image_hash: str = Query(..., description="The hash of the image to retrieve scores for"),
    image_source: str = Query(..., regex="^(generated_image|extract_image|external_image)$", description="The source of the image")
):
    response_handler = await ApiResponseHandlerV1.createInstance(request)

    # Build the query to fetch scores by image_hash and image_source
    query = {"image_hash": image_hash, "image_source": image_source}

    # Fetch data from the database
    cursor = request.app.image_classifier_scores_collection.find(query)

    scores_data = list(cursor)

    # Remove '_id' from the response data
    for score in scores_data:
        score.pop('_id', None)

    # Prepare and return the data for the response
    return response_handler.create_success_response_v1(
        response_data={"scores": scores_data},
        http_status_code=200
    )
   

@router.post("/pseudotag-classifier-scores/set-image-classifier-score-v1", 
             status_code=200,
             response_model=StandardSuccessResponseV1[ClassifierScoreV1],
             description="Set classifier image score",
             tags=["pseudotag-classifier-scores"], 
             responses=ApiResponseHandlerV1.listErrors([404, 422, 500]))
async def set_image_classifier_score_v1(
    request: Request, 
    classifier_score: ClassifierScoreRequest, 
    image_source: str = Query(..., regex="^(generated_image|extract_image|external_image)$")
):
    api_response_handler = await ApiResponseHandlerV1.createInstance(request)

    try:
        # Determine the appropriate collection based on image_source
        if image_source == "generated_image":
            collection = request.app.completed_jobs_collection
        elif image_source == "extract_image":
            collection = request.app.extracts_collection
        elif image_source == "external_image":
            collection = request.app.external_images_collection
        else:
            return api_response_handler.create_error_response_v1(
                error_code=ErrorCode.INVALID_PARAMS,
                error_string="Invalid image source provided.",
                http_status_code=422
            )
        
        image_query = {
            '$or': [
                {'uuid': classifier_score.job_uuid},
                {'uuid': uuid.UUID(classifier_score.job_uuid)}
            ]
        }

        # Fetch job data from the determined collection
        job_data = collection.find_one(image_query)
        if not job_data:
            return api_response_handler.create_error_response_v1(
                error_code=ErrorCode.INVALID_PARAMS,
                error_string="The image was not found.",
                http_status_code=404
            )

        if image_source == "generated_image":
            if 'task_output_file_dict' not in job_data or 'output_file_hash' not in job_data['task_output_file_dict']:
                return api_response_handler.create_error_response_v1(
                    error_code=ErrorCode.INVALID_PARAMS,
                    error_string="The provided UUID does not have an associated image hash.",
                    http_status_code=404
                )
            image_hash = job_data['task_output_file_dict']['output_file_hash']
            task_type = job_data.get('task_type', None)
        else:
            image_hash = job_data['image_hash']
            task_type = None

        # Fetch tag_id from classifier_models_collection
        classifier_data = request.app.classifier_models_collection.find_one(
            {"classifier_id": classifier_score.classifier_id}, 
            {"tag_id": 1}
        )
        if not classifier_data:
            return api_response_handler.create_error_response_v1(
                error_code=ErrorCode.INVALID_PARAMS,
                error_string="The provided classifier ID does not exist.",
                http_status_code=404
            )
        tag_id = classifier_data['tag_id']
        image_uuid = job_data.get('image_uuid', None)

        query = {
            "classifier_id": classifier_score.classifier_id,
            "uuid": classifier_score.job_uuid,
            "tag_id": tag_id,
            "image_source": image_source
        }

        # Get current UTC time in ISO format
        current_utc_time = datetime.utcnow().isoformat()

        # Initialize new_score_data
        new_score_data = {
            "uuid": classifier_score.job_uuid,
            "task_type": task_type,
            "classifier_id": classifier_score.classifier_id,
            "tag_id": tag_id,
            "score": classifier_score.score,
            "image_hash": image_hash,
            "creation_time": current_utc_time,
            "image_source": image_source,
            "image_uuid": image_uuid
        }

        # Check for existing score and update or insert accordingly
        existing_score = request.app.image_classifier_scores_collection.find_one(query)
        if existing_score:
            # Update existing score
            request.app.image_classifier_scores_collection.update_one(
                query, 
                {"$set": {
                    "score": classifier_score.score, 
                    "image_hash": image_hash, 
                    "creation_time": current_utc_time,
                    "image_source": image_source
                }}
            )
        else:
            # Insert new score
            insert_result = request.app.image_classifier_scores_collection.insert_one(new_score_data)
            new_score_data['_id'] = str(insert_result.inserted_id)

        return api_response_handler.create_success_response_v1(
            response_data=new_score_data,
            http_status_code=200  
        )
    
    except Exception as e:
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR, 
            error_string=str(e),
            http_status_code=500
        )
    

@router.post("/pseudotag-classifier-scores/set-image-classifier-score-v2", 
             status_code=200,
             response_model=StandardSuccessResponseV1[ListClassifierScore4],
             description="Set classifier image scores in batch",
             tags=["pseudotag-classifier-scores"], 
             responses=ApiResponseHandlerV1.listErrors([404, 422, 500]))
async def set_image_classifier_score_v2(
    request: Request, 
    batch_scores: BatchClassifierScoreRequest
):
    api_response_handler = await ApiResponseHandlerV1.createInstance(request)

    try:
        bulk_operations = []
        response_data = []

        for classifier_score in batch_scores.scores:
            query = {
                "classifier_id": classifier_score.classifier_id,
                "uuid": classifier_score.job_uuid,
                "image_source": classifier_score.image_source
            }

            new_score_data = {
                "uuid": classifier_score.job_uuid,
                "classifier_id": classifier_score.classifier_id,
                "tag_id": classifier_score.tag_id,
                "score": classifier_score.score,
                "image_hash": classifier_score.image_hash,
                "creation_time": datetime.utcnow().isoformat(),
                "image_source": classifier_score.image_source
            }

            update_operation = UpdateOne(
                query,
                {"$set": new_score_data},
                upsert=True
            )
            bulk_operations.append(update_operation)
            response_data.append(new_score_data)

        if bulk_operations:
            request.app.image_classifier_scores_collection.bulk_write(bulk_operations)

        return api_response_handler.create_success_response_v1(
            response_data=response_data,
            http_status_code=200  
        )
    
    except Exception as e:
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR, 
            error_string=str(e),
            http_status_code=500
        )
    

@router.post("/pseudotag-classifier-scores/set-image-classifier-scores-in-bulk", 
             status_code=200,
             response_model=StandardSuccessResponseV1[ListClassifierScore2],
             description="Set classifier image scores in batch",
             tags=["pseudotag-classifier-scores"], 
             responses=ApiResponseHandlerV1.listErrors([404, 422, 500]))
async def set_image_classifier_score_bulk(
    request: Request, 
    batch_scores: BatchClassifierScoreRequest
):
    api_response_handler = await ApiResponseHandlerV1.createInstance(request)

    try:
        bulk_operations = []
        response_data = []

        for classifier_score in batch_scores.scores:
            query = {
                "classifier_id": classifier_score.classifier_id,
                "uuid": classifier_score.job_uuid,
                "image_source": classifier_score.image_source
            }

            new_score_data = {
                "uuid": classifier_score.job_uuid,
                "classifier_id": classifier_score.classifier_id,
                "tag_id": classifier_score.tag_id,
                "score": classifier_score.score,
                "image_hash": classifier_score.image_hash,
                "creation_time": datetime.utcnow().isoformat(),
                "image_source": classifier_score.image_source
            }

            update_operation = UpdateOne(
                query,
                {"$set": new_score_data},
                upsert=True
            )
            bulk_operations.append(update_operation)
            response_data.append(new_score_data)

        if bulk_operations:
            request.app.image_classifier_scores_collection.bulk_write(bulk_operations)

        return api_response_handler.create_success_response_v1(
            response_data={"scores": response_data},
            http_status_code=200  
        )
    
    except Exception as e:
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR, 
            error_string=str(e),
            http_status_code=500
        )    


@router.post("/pseudotag-classifier-scores/set-image-classifier-score-list-v1", 
             status_code=200,
             response_model=StandardSuccessResponseV1[ListClassifierScore3],
             description="Set classifier image score",
             tags=["pseudotag-classifier-scores"], 
             responses=ApiResponseHandlerV1.listErrors([404, 422, 500]) 
             )
async def set_image_classifier_score_list(
    request: Request, 
    classifier_score_list: List[ClassifierScoreRequest],
    image_source: str = Query(..., regex="^(generated_image|extract_image|external_image)$")
):
    api_response_handler = await ApiResponseHandlerV1.createInstance(request)
    new_score_data_list = []

    try:
        for classifier_score in classifier_score_list:
            # Determine the appropriate collection based on image_source
            if image_source == "generated_image":
                collection = request.app.completed_jobs_collection
                projection = {"task_output_file_dict.output_file_hash": 1, "task_type": 1}
            elif image_source == "extract_image":
                collection = request.app.extracts_collection
                projection = {"image_hash": 1}
            elif image_source == "external_image":
                collection = request.app.external_images_collection
                projection = {"image_hash": 1}
            else:
                return api_response_handler.create_error_response_v1(
                    error_code=ErrorCode.INVALID_PARAMS,
                    error_string="Invalid image source provided.",
                    http_status_code=422
                )

            image_query = {
                '$or': [
                    {'uuid': classifier_score.job_uuid},
                    {'uuid': uuid.UUID(classifier_score.job_uuid)}
                ]
            }

            # Fetch image_hash from the determined collection
            job_data = collection.find_one(image_query, projection)
            if not job_data:
                return api_response_handler.create_error_response_v1(
                    error_code=ErrorCode.INVALID_PARAMS,
                    error_string="the image was not found ",
                    http_status_code=404
                )

            if image_source == "generated_image":
                if 'task_output_file_dict' not in job_data or 'output_file_hash' not in job_data['task_output_file_dict']:
                    return api_response_handler.create_error_response_v1(
                        error_code=ErrorCode.INVALID_PARAMS,
                        error_string=f"The provided UUID {classifier_score.job_uuid} does not have an associated image hash.",
                        http_status_code=404
                    )
                image_hash = job_data['task_output_file_dict']['output_file_hash']
                task_type = job_data.get('task_type', None)
            else:
                image_hash = job_data['image_hash']
                task_type = None

            # Fetch tag_id from classifier_models_collection
            classifier_data = request.app.classifier_models_collection.find_one(
                {"classifier_id": classifier_score.classifier_id}, 
                {"tag_id": 1}
            )
            if not classifier_data:
                return api_response_handler.create_error_response_v1(
                    error_code=ErrorCode.INVALID_PARAMS,
                    error_string=f"The provided classifier ID {classifier_score.classifier_id} does not exist.",
                    http_status_code=404
                )
            tag_id = classifier_data['tag_id']
            image_uuid = job_data.get('image_uuid', None)

            query = {
                "classifier_id": classifier_score.classifier_id,
                "uuid": classifier_score.job_uuid,
                "tag_id": tag_id,
                "image_source": image_source
            }

            # Get current UTC time in ISO format
            current_utc_time = datetime.utcnow().isoformat()

            # Initialize new_score_data
            new_score_data = {
                "uuid": classifier_score.job_uuid,
                "task_type": task_type,
                "classifier_id": classifier_score.classifier_id,
                "tag_id": tag_id,
                "score": classifier_score.score,
                "image_hash": image_hash,
                "creation_time": current_utc_time,
                "image_source": image_source,
                "image_uuid": image_uuid
            }

            # Check for existing score and update or insert accordingly
            existing_score = request.app.image_classifier_scores_collection.find_one(query)
            if existing_score:
                # Update existing score
                request.app.image_classifier_scores_collection.update_one(
                    query, 
                    {"$set": {
                        "score": classifier_score.score, 
                        "image_hash": image_hash, 
                        "creation_time": current_utc_time,
                        "image_source": image_source
                    }}
                )
            else:
                # Insert new score
                insert_result = request.app.image_classifier_scores_collection.insert_one(new_score_data)
                new_score_data['_id'] = str(insert_result.inserted_id)
                new_score_data_list.append(new_score_data)

        return api_response_handler.create_success_response_v1(
            response_data={
                "data": new_score_data_list
            },
            http_status_code=200  
        )
    
    except Exception as e:
        return api_response_handler.create_error_response_v1(
            error_code=ErrorCode.OTHER_ERROR, 
            error_string=str(e),
            http_status_code=500
        )