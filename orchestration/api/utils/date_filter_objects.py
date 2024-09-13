from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, ValidationError, validate_call, validator

correct_api_date_format = "%Y-%m-%dT%H:%M:%S"

class ElapsedTimeUnit(str, Enum):
    '''Time units for the time filters.'''
    minutes = "minutes"
    hours = "hours"

class DateFilterParams(BaseModel):
    '''Values for filtering data by start date, final date or both.'''

    model_config = ConfigDict(validate_assignment='True')

    initial_date: Optional[datetime]
    '''If provided, the data must be from this date (inclusive) or newer. Must be a naive datetime object.'''

    final_date: Optional[datetime]
    '''If provided, the data must be from this date (inclusive) or older. Must be a naive datetime object.'''

    @validator("initial_date", "final_date")
    def check_if_utc(cls, v: Optional[datetime]):
        if v != None and v.tzinfo != None:
            raise ValueError('DateFilterParams can only work with naive datetime objects')
        return v
    
    @validator("final_date")
    def check_reversed_dates(cls, v: Optional[str], values):
        if values['initial_date'] and v and values['initial_date'] > v:
            raise ValueError('The initial date must not be after the final date.')
        
        return v

class ElapsedTimeFilterParams(BaseModel):
    '''Values for filtering data by elapsed time. This is for indicating that only entries of a certain age or newer must be considered'''
    model_config = ConfigDict(validate_assignment='True')

    time_unit: ElapsedTimeUnit
    time: int

class ApiDateFilterCreationError(BaseModel):
    '''Error when trying to create a date filter with the create_date_filter_from_api_values function.'''
    error_msg: str

@validate_call
def create_date_filter_from_api_values(
        start_date: Optional[str],
        end_date: Optional[str],
        time_interval: Optional[int],
        time_unit: Optional[ElapsedTimeUnit]
) -> DateFilterParams | ElapsedTimeFilterParams | ApiDateFilterCreationError | None:
    '''
    Gets the values sent to an API endpoint and creates date validation object, depending on the provided values.
    The procedure goes as follow.

    - If "time_interval" is provided, the function will try to create an instance of "ElapsedTimeFilterParams", ignoring the start
    and end date values. In this case, a value for "time_unit" must be providad.

    - If no "time_interval" value is provided but a start or end date value is, the function will try to create a "DateFilterParams"
    instance.

    - In both previous cases the function performs several validations. If any of the validations fail, an instance of
    ApiDateFilterCreationError is returned, with a human readable text indicating what went wrong.

    - If none of the previous cases is true, the function returns None.

    Args:
        start_date (str): start date (inclusive) for filtering by date. Must be in the format defined in "correct_api_date_format".

        end_date (str): end date (inclusive) for filtering by date. Must be in the format defined in "correct_api_date_format".

        time_interval (int): If set, only entries this old or newer must be returned.

        time_unit (ElapsedTimeUnit): Indicates if the value of 'time_interval' is in minutes or seconds.
    '''

    date_filter = None
    if time_interval != None:
        if not time_unit:
            return ApiDateFilterCreationError(error_msg="If a 'time_interval' value is set, a valid 'time_unit' value must be set too.")

        try:
            date_filter = ElapsedTimeFilterParams(time_unit = time_unit, time = time_interval)
        except ValidationError as e:
            # Process any validation error returned by pydantic.
            err = e.errors()[0]
            if err:
                return ApiDateFilterCreationError(error_msg=err['msg'])
            raise e
    elif start_date != None or end_date != None:
        converted_start_date = None
        if start_date != None:
            try:
                converted_start_date = datetime_from_api_string(start_date)
            except Exception as e:
                return ApiDateFilterCreationError(error_msg=f"Invalid start date format. The correct format is {correct_api_date_format}.")
        
        converted_end_date = None
        if end_date != None:
            try:
                converted_end_date = datetime_from_api_string(end_date)
            except Exception as e:
                return ApiDateFilterCreationError(error_msg=f"Invalid end date format. The correct format is {correct_api_date_format}.")
        
        try:
            date_filter = DateFilterParams(
                initial_date = converted_start_date,
                final_date = converted_end_date
            )
        except ValidationError as e:
            # Process any validation error returned by pydantic.
            err = e.errors()[0]
            if err:
                return ApiDateFilterCreationError(error_msg=err['msg'])
            raise e
    
    return date_filter

def datetime_from_api_string(date_str: str) -> datetime:
    '''Creates a datetime instance from an API string. The string must be in the format deffined in "correct_api_date_format".'''
    try:
        return datetime.strptime(date_str, correct_api_date_format)
    except ValueError as e:
        raise Exception(f"Error parsing date string: {e}")
