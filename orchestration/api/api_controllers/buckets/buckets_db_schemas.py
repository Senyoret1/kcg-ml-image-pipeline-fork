from __future__ import annotations
from typing import Optional
from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field

class BucketsDbSchemas():
    class DatabaseSchema(BaseModel):
        model_config = ConfigDict(extra='forbid')

        bucket_id: Annotated[
            int,
            Field(
                json_schema_extra={'bsonType': 'int'}
            )
        ]
        bucket_name: Annotated[
            str,
            Field(
                json_schema_extra={'bsonType': 'string'},
                min_length=1,
                max_length=1024,
            )
        ]
        creation_time: Annotated[
            str,
            Field(
                json_schema_extra={'bsonType': 'string'}
            )
        ]

    class FullDatabaseSchema(DatabaseSchema):
        id: Annotated[
            str,
            Field(
                validation_alias="_id",
                json_schema_extra={'bsonType': 'objectId'}
            )
        ]
    
    class AddDataSchema(BaseModel):
        bucket_name: str
    