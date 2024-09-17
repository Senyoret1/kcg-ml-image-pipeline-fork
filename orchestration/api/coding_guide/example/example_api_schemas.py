from typing import List
from pydantic import BaseModel

from orchestration.api.manual.example.example_db_schemas import ExampleDbSchemas

class ExampleApiSchemas():
    '''
    All schemas are inside a class called f"{collection_name}ApiSchemas". This is for code organization.
    '''

    class EntriesListResponse(BaseModel):
        '''
        This is for indicating how a specific endpoint responds. Note that the name ends with Response.
        '''
        entries: List[ExampleDbSchemas.DatabaseSchema]

    class ExampleCreationRequest(BaseModel):
        '''
        This is for indicating what data a specific endpoint receives. Note that the name ends with Request.
        '''
        example_name: str
