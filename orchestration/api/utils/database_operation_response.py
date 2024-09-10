from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, validator

class DatabaseOperationResponseType(Enum):
    SUCCESS = 1
    INTERNAL_ERROR = 2
    NOT_ALLOWED = 3

T = TypeVar('T')
class DatabaseOperationResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(validate_assignment='True')

    response_type: DatabaseOperationResponseType = DatabaseOperationResponseType.SUCCESS
    response_content: Optional[T] = None
    error_description: Optional[str] = None
    
    @validator("error_description")
    def check_if_valid_http_response_code(cls, v: Optional[str], values):
        if not 'response_type' in values:
            raise ValueError('Invalid response type.')
        
        if values['response_type'] != DatabaseOperationResponseType.SUCCESS and v == None:
            raise ValueError('Error responses must have an error description.')
        
        return v
