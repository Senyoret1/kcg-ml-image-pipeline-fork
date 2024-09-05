from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, validate_call, validator

correct_api_date_format = "%Y-%m-%dT%H:%M:%S"

class ElapsedTimeUnit(str, Enum):
    minutes = "minutes"
    hours = "hours"

class DateFilterParams(BaseModel):
    initial_date: Optional[datetime]
    final_date: Optional[datetime]

    @validator("initial_date", "final_date")
    def check_if_utc(cls, v: Optional[datetime]):
        if v != None and v.tzinfo != None:
            raise ValueError('DateFilterParams can only work with naive datetime objects')
        return v

    class Config:
        validate_assignment = True

class ElapsedTimeFilterParams(BaseModel):
    time_unit: ElapsedTimeUnit
    time: int

    class Config:
        validate_assignment = True

@validate_call
def create_date_filter_from_api_values(
        start_date: Optional[str],
        end_date: Optional[str],
        time_interval: Optional[int],
        time_unit: Optional[ElapsedTimeUnit]
) -> DateFilterParams | ElapsedTimeFilterParams | None:
    date_filter = None
    if time_interval != None:
        if not time_unit:
            raise Exception("If a 'time_interval' value is set, a valid 'time_unit' value must be set too.")

        date_filter = ElapsedTimeFilterParams(time_unit = time_unit, time = time_interval)
    elif start_date != None or end_date != None:
        converted_start_date = None
        if start_date != None:
            try:
                converted_start_date = datetime_from_api_string(start_date)
            except Exception as e:
                raise Exception(f"Invalid start date format. The correct format is {correct_api_date_format}.")
        
        converted_end_date = None
        if end_date != None:
            try:
                converted_end_date = datetime_from_api_string(end_date)
            except Exception as e:
                raise Exception(f"Invalid end date format. The correct format is {correct_api_date_format}.")
            
        date_filter = DateFilterParams(
            initial_date = converted_start_date,
            final_date = converted_end_date
        )
    
    return date_filter

def datetime_from_api_string(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, correct_api_date_format)
    except ValueError as e:
        raise Exception(f"Error parsing date string: {e}")
