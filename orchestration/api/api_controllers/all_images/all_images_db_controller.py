from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Union
from pydantic import validate_call
import pymongo.collection
from pymongo.collection import Collection
from pymongo.database import Database
import pymongo
import pymongo.database

from orchestration.api.api_controllers.all_images.all_images_db_schemas import AllImagesDbSchemas
from orchestration.api.api_controllers.database_collection_controller_base import DatabaseCollectionControllerBase
from orchestration.api.utils.api_operations_utils import ApiUtils
from orchestration.api.utils.database_operation_response import DatabaseOperationResponse
from orchestration.api.utils.date_filter_objects import DateFilterParams, ElapsedTimeFilterParams, ElapsedTimeUnit
from orchestration.api.utils.uuid64 import Uuid64

class AllImagesDbController(DatabaseCollectionControllerBase['AllImagesDbController']):
    @classmethod
    def _create_instance(cls):
        return AllImagesDbController(cls._creation_key)
    
    def prepare(self, mongodb_db: Database) -> Collection:
        self._internal_preparation(mongodb_db, "all-images", AllImagesDbSchemas.FullDatabaseSchema)
        self._set_top_properties(['image_path'])

        self.create_index_if_not_exists(
            [('image_hash', pymongo.ASCENDING)],
            'all_images_hash_index'
        )

        self.create_index_if_not_exists(
            [('image_hash', pymongo.ASCENDING), ('bucket_id', pymongo.ASCENDING)],
            'all_images_hash_and_bucket_index'
        )

        return self.collection
    
    @validate_call
    def add_image(self, data: AllImagesDbSchemas.AddDataSchema) -> DatabaseOperationResponse[list[AllImagesDbSchemas.DatabaseSchema]]:
        try:
            new_document = data.model_dump()
            new_document['uuid'] = Uuid64.from_formatted_string(data.uuid).to_mongo_value()
            new_document['index'] = -1
            self.collection.insert_one(new_document)

            print(f"Inserted new document into all-images collection: {new_document}")

            self._process_data_types(new_document)

            return DatabaseOperationResponse(response_content=new_document)
        except Exception as e:
            raise Exception(f"Error adding an image to the all images collection: {e}")

    def list_images_with_filtering_and_pagination(
        self,
        bucket_ids: Optional[List[int]],
        dataset_ids: Optional[List[int]],
        limit: int,
        offset: int,
        sort_order: ApiUtils.SortOrder,
        date_filter: Optional[Union[DateFilterParams, ElapsedTimeFilterParams]]
    ) -> DatabaseOperationResponse[list[AllImagesDbSchemas.DatabaseSchema]]:
        try:
            query = {}

            bucket_and_dataset_conditions = []
            if bucket_ids:
                bucket_and_dataset_conditions.append({"bucket_id": {"$in": bucket_ids}})
            if dataset_ids:
                bucket_and_dataset_conditions.append({"dataset_id": {"$in": dataset_ids}})

            if bucket_and_dataset_conditions:
                if (len(bucket_and_dataset_conditions) > 1):
                    query = {"$or": bucket_and_dataset_conditions}
                else:
                    query = bucket_and_dataset_conditions[0]

            date_query = {}
            if date_filter:
                if isinstance(date_filter, DateFilterParams):
                    if date_filter.initial_date:
                        date_query['$gte'] = int(date_filter.initial_date.timestamp())
                    if date_filter.final_date:
                        date_query['$lte'] = int(date_filter.final_date.timestamp())
                if isinstance(date_filter, ElapsedTimeFilterParams):
                    current_time = datetime.utcnow()
                    if date_filter.time_unit == ElapsedTimeUnit.minutes:
                        threshold_time = current_time - timedelta(minutes=date_filter.time)
                    elif date_filter.time_unit == ElapsedTimeUnit.hours:
                        threshold_time = current_time - timedelta(hours=date_filter.time)
                    else:
                        raise Exception("Invalid time unit for filtering by elapsed time.")
                    
                    date_query['$gte'] = int(threshold_time.timestamp())

            if date_query:
                query['date'] = date_query

            sort_order = 1 if sort_order == ApiUtils.SortOrder.asc else -1
            cursor = self.collection.find(query).sort('date', sort_order).skip(offset).limit(limit)
            data = list(cursor)

            self._process_data_types(data)

            return DatabaseOperationResponse(response_content=data)
        except Exception as e:
            raise Exception(f"Error while getting a filtered images list from the all images collection: {e}")
        
    def find_single_image(
        self, image_hash: Optional[str] = None, bucket_id: Optional[int] = None, values_to_get: Optional[dict] = None
    ) -> DatabaseOperationResponse[AllImagesDbSchemas.DatabaseSchema | None]:
        try:
            query = {}
            if image_hash != None:
                query["image_hash"] = image_hash
            if bucket_id != None:
                query["bucket_id"] = bucket_id

            data = self.collection.find_one(query, values_to_get)
            self._process_data_types(data)

            return DatabaseOperationResponse(response_content=data)
        except Exception as e:
            raise Exception(f"Error while finding an image using the {image_hash} hash in database: {e}")
    
    def find_images_with_invalid_schema(self) -> DatabaseOperationResponse[List[dict]]:
        try:
            query = { "$nor": [ self._validation_schema ] }

            data = self.collection.find(query)
            data = list(data)
            self._process_data_types(data)

            return DatabaseOperationResponse(response_content=data)
        except Exception as e:
            raise Exception(f"Error while finding invalid images in database: {e}")
        
    def delete_images_by_hash(self, image_hash: str, bucket_id: Optional[int] = None) -> DatabaseOperationResponse[int]:
        try:
            query = {"image_hash": image_hash}
            if bucket_id:
                query["bucket_id"] = bucket_id

            result = self.collection.delete_many(query)

            return DatabaseOperationResponse(response_content=result.deleted_count)
        except Exception as e:
            raise Exception(f"Error while deleting images using the {image_hash} hash in database: {e}")

    def _perform_db_element_processing(self, data: dict):
        data.pop('_id', None)

        if "uuid" in data:
            if isinstance(data['uuid'], int):
                uuid64 = Uuid64.from_mongo_value(data['uuid'])
                data['uuid'] = uuid64.to_formatted_str()
            if isinstance(data['uuid'], Uuid64):
                data['uuid'] = data['uuid'].to_formatted_str()
