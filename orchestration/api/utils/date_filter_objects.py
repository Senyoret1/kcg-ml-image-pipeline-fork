from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

class ElapsedTimeUnit(Enum):
    MINUTES = 1
    HOURS = 2

class DateFilterParams():
    initial_date: Optional[datetime]
    final_date: Optional[datetime]

    @staticmethod
    def create_instance(initial_date: Optional[datetime], final_date: Optional[datetime]) -> 'DateFilterParams':
        instance = DateFilterParams()
        instance.initial_date = initial_date
        instance.final_date = final_date

        return instance

class ElapsedTimeFilterParams():
    time_unit: ElapsedTimeUnit
    time: int

    @staticmethod
    def create_instance(time_unit: ElapsedTimeUnit, time: int) -> 'ElapsedTimeFilterParams':
        instance = ElapsedTimeFilterParams()
        instance.time_unit = time_unit
        instance.time = time

        return instance
