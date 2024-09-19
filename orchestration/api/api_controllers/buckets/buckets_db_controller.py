from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from pydantic import validate_call
from pymongo.collection import Collection
from pymongo.database import Database

from orchestration.api.api_controllers.all_images.all_images_db_controller import AllImagesDbController
from orchestration.api.api_controllers.buckets.buckets_db_schemas import BucketsDbSchemas
from orchestration.api.api_controllers.database_collection_controller_base import DatabaseCollectionControllerBase
from orchestration.api.utils.database_operation_response import DatabaseOperationResponse, DatabaseOperationResponseType

class BucketsDbController(DatabaseCollectionControllerBase['BucketsDbController']):
    @classmethod
    def _create_instance(cls):
        return BucketsDbController(cls._creation_key)
    
    def prepare(self, mongodb_db: Database) -> Collection:
        self._internal_preparation(mongodb_db, "buckets", BucketsDbSchemas.FullDatabaseSchema)

        # Unique indexes, to avoid having more than one record with the same value in the database.
        self.create_index_if_not_exists('bucket_id', 'buckets_unique_id_index', True)
        self.create_index_if_not_exists('bucket_name', 'buckets_unique_name_index', True)

        return self.collection
    
    @validate_call
    def add_bucket(self, data: BucketsDbSchemas.AddDataSchema) -> DatabaseOperationResponse[BucketsDbSchemas.DatabaseSchema]:
        try:
            old_entry = self.collection.find_one({"bucket_name": data.bucket_name})
            if old_entry:
                return DatabaseOperationResponse(
                    response_type=DatabaseOperationResponseType.REQUEST_REJECTED,
                    error_description=f"A bucket named '{data.bucket_name}' already exists."
                )
            
            
            last_bucket = self.collection.find_one(sort=[("bucket_id", -1)])
            next_bucket_id = last_bucket["bucket_id"] + 1 if last_bucket else 0

            # Create the new bucket document
            new_bucket = BucketsDbSchemas.DatabaseSchema(
                bucket_id= next_bucket_id,
                bucket_name= data.bucket_name,
                creation_time= datetime.now(timezone.utc).isoformat()
            )
            new_bucket = new_bucket.model_dump();
            
            self.collection.insert_one(new_bucket)
            self._process_data_types(new_bucket)

            return DatabaseOperationResponse(response_content=new_bucket)
        except Exception as e:
            raise Exception(f"Error adding a bucket to the buckets collection: {e}")

    def list_all_buckets(self) -> DatabaseOperationResponse[list[BucketsDbSchemas.DatabaseSchema]]:
        try:
            cursor = self.collection.find({}).sort('bucket_id', 1)
            data = list(cursor)

            self._process_data_types(data)

            return DatabaseOperationResponse(response_content=data)
        except Exception as e:
            raise Exception(f"Error while getting the buckets list from the collection: {e}")
    
    # TODO: this should be in the base class.
    def find_buckets_with_invalid_schema(self) -> DatabaseOperationResponse[List[dict]]:
        try:
            query = { "$nor": [ self._validation_schema ] }

            data = self.collection.find(query)
            data = list(data)
            self._process_data_types(data)

            return DatabaseOperationResponse(response_content=data)
        except Exception as e:
            raise Exception(f"Error while finding invalid buckets in database: {e}")
        
    def delete_bucket_by_id(self, bucket_id: int) -> DatabaseOperationResponse[int]:
        try:
            if 0 <= bucket_id < 3:
                return DatabaseOperationResponse(
                    response_type=DatabaseOperationResponseType.REQUEST_REJECTED,
                    error_description="The first 3 buckets cannot be removed."
                )

            # Check if the bucket is referenced in any entry in the all images collection.
            bucket_in_use_response = AllImagesDbController.get_instance().find_single_image(None, bucket_id)
            if bucket_in_use_response.response_type != DatabaseOperationResponseType.SUCCESS:
                return DatabaseOperationResponse(
                    response_type = bucket_in_use_response.response_type,
                    error_description = f"Error trying to delete the bucket: {bucket_in_use_response.error_description}"
                )
            
            if bucket_in_use_response.response_content != None:
                return DatabaseOperationResponse(
                    response_type = DatabaseOperationResponseType.REQUEST_REJECTED,
                    error_description = f"Bucket with ID {bucket_id} is in use and cannot be removed."
                )

            result = self.collection.delete_one({"bucket_id": bucket_id})
            return DatabaseOperationResponse(response_content=result.deleted_count)
        except Exception as e:
            raise Exception(f"Error while deleting a bucket using the id {bucket_id} in database: {e}")

    def _perform_db_element_processing(self, data: dict):
        data.pop('_id', None)
