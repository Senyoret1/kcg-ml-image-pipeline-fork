from __future__ import annotations
from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field

class AllImagesDbSchemas():
    class DatabaseSchema(BaseModel):
        model_config = ConfigDict(extra='forbid')

        uuid: Annotated[
            str,
            Field(
                description='Uuids are saved as longs internally',
                json_schema_extra={'bsonType': 'long'}
            )
        ]
        index: Annotated[
            int,
            Field(
                json_schema_extra={'bsonType': 'int'}
            )
        ]
        bucket_id: Annotated[
            int,
            Field(
                json_schema_extra={'bsonType': 'int'}
            )
        ]
        dataset_id: Annotated[
            int,
            Field(
                json_schema_extra={'bsonType': 'int'}
            )
        ]
        # The value should be always 64 characters long, but there are hashes with 32
        # characters, so this value had to be used to prevent problems.
        image_hash: Annotated[
            str,
            Field(
                json_schema_extra={'bsonType': 'string'},
                min_length=32,
                max_length=128,
            )
        ]
        image_path: Annotated[
            str,
            Field(
                json_schema_extra={'bsonType': 'string'},
                min_length=10,
                max_length=512,
            )
        ]
        date: Annotated[
            int,
            Field(
                json_schema_extra={'bsonType': 'int'},
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
        uuid: str
        bucket_id: int
        dataset_id: int
        image_hash: str
        image_path: str
        date: int
