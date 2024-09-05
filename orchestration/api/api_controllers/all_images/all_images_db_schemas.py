from __future__ import annotations

from pydantic import BaseModel

class AllImagesDbSchemas():
    validation_schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["uuid", "index", "bucket_id", "dataset_id", "image_hash", "image_path", "date"],
            "additionalProperties": False,
            "properties": {
                "_id": { "bsonType": "objectId" },
                "uuid": {
                    "bsonType": "long",
                    "description": "Uuids are saved as longs internally"
                },
                "index": {
                    "bsonType": "int"
                },
                "bucket_id": {
                    "bsonType": "int"
                },
                "dataset_id": {
                    "bsonType": "int"
                },
                # The value should be always 64 characters long, but there are hashes with 32
                # characters, so this value had to be used to prevent problems.
                "image_hash": {
                    "bsonType": "string",
                    "minLength": 32,
                    "maxLength": 128
                },
                "image_path": {
                    "bsonType": "string",
                    "minLength": 10,
                    "maxLength": 512,
                },
                "date": {
                    "bsonType": "int"
                }
            }
        }
    }

    class AddDataSchema(BaseModel):
        uuid: str
        bucket_id: int
        dataset_id: int
        image_hash: str
        image_path: str
        date: int
    
    class DatabaseSchema(BaseModel):
        uuid: str
        index: int
        bucket_id: int
        dataset_id: int
        image_hash: str
        image_path: str
        date: int
