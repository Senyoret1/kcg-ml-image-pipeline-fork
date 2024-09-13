from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, validator

class DatabaseOperationResponseType(Enum):
    '''Posible results of the database operations. It is to be used with the DatabaseOperationResponse class.'''
    SUCCESS = 1
    '''The opertaion finished correctly.'''
    INTERNAL_ERROR = 2
    '''The operation failed due to other cause.'''
    REQUEST_REJECTED = 3
    '''The operation was rejected because it violates a rule.'''

T = TypeVar('T')
class DatabaseOperationResponse(BaseModel, Generic[T]):
    '''
    Response that must be returned by the database operations. It allows not just to return the requested
    data, but also to give information about internal errors that don't raise errors.

    It includes a generic param, which allows to indicate the data type of the value returned by the database
    operation, to make the code completion tools work.
    '''
    model_config = ConfigDict(validate_assignment='True')

    response_type: DatabaseOperationResponseType = DatabaseOperationResponseType.SUCCESS
    '''If the operation finished correctly or if there was an error. Not all errors are reported using
    this param, some operations could just raise an exception, especially in case of unexpected errors.'''
    response_content: Optional[T] = None
    '''Content retuened by the database operation. If the operation finished with an error, this is
    normally None.'''
    error_description: Optional[str] = None
    '''The description of the error, if the operation finished with an error. It is normally None if the
    operation finished correctly.'''
    
    @validator("error_description")
    def check_mandatory_error_description(cls, v: Optional[str], values):
        if not 'response_type' in values:
            raise ValueError('Invalid response type.')
        
        if values['response_type'] != DatabaseOperationResponseType.SUCCESS and v == None:
            raise ValueError('Error responses must have an error description.')
        
        return v
