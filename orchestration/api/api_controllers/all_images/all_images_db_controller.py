from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Union
import pymongo.collection
from pymongo.collection import Collection
from pymongo.database import Database
import pymongo
import pymongo.database

from orchestration.api.api_controllers.database_collection_controller_base import DatabaseCollectionControlletBase
from orchestration.api.utils.date_filter_objects import DateFilterParams, ElapsedTimeFilterParams, ElapsedTimeUnit
from orchestration.api.utils.uuid64 import Uuid64

class AllImagesDbController(DatabaseCollectionControlletBase['AllImagesDbController']):
    @classmethod
    def _create_instance(cls):
        return AllImagesDbController(cls._creation_key)
    
    def prepare(self, mongodb_db: Database) -> Collection:
        self._internal_preparation(mongodb_db, "all-images")
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

    def list_images_with_filtering_and_pagination(
        self,
        bucket_ids: Optional[List[int]],
        dataset_ids: Optional[List[int]],
        limit: int,
        offset: int,
        sort_ascending: str,
        date_filter: Optional[Union[DateFilterParams, ElapsedTimeFilterParams]]
    ):
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
                    if date_filter.time_unit == ElapsedTimeUnit.MINUTES:
                        threshold_time = current_time - timedelta(minutes=date_filter.time)
                    if date_filter.time_unit == ElapsedTimeUnit.HOURS:
                        threshold_time = current_time - timedelta(hours=date_filter.time)
                    else:
                        raise Exception("Invalid time unit for filtering by elapsed time.")
                    
                    date_query['$gte'] = int(threshold_time.timestamp())

            if date_query:
                query['date'] = date_query

            sort_order = 1 if sort_ascending else -1
            cursor = self.collection.find(query).sort('date', sort_order).skip(offset).limit(limit)
            data = list(cursor)

            self._process_data_types(data)

            return data
        except Exception as e:
            raise Exception(f"Error while getting a filtered images list from the all images collection: {e}")
        
    def find_image_by_hash(self, image_hash: str):
        try:
            data = self.collection.find_one({"image_hash": image_hash})
            self._process_data_types(data)

            return data
        except Exception as e:
            raise Exception(f"Error while finding an image using the {image_hash} hash in database: {e}")

    def _perform_db_element_processing(self, data: dict):
        data.pop('_id', None)

        if "uuid" in data:
            if isinstance(data['uuid'], int):
                uuid64 = Uuid64.from_mongo_value(data['uuid'])
                data['uuid'] = uuid64.to_formatted_str()
            if isinstance(data['uuid'], Uuid64):
                data['uuid'] = data['uuid'].to_formatted_str()
