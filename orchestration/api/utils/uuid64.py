from __future__ import annotations

from datetime import datetime, timezone
import re
import secrets
from typing import List

class Uuid64():
    '''Object representing a 64bit Uuid. It includes helpers for converting to/from formatted strings and int values.

    For creating instances of this class, use the static methods it provides, don't create instances directly
    like "uuid = Uuid64()".

    Internally, 64bit UUIDs are 64bit numbers. The first 32 bits contain a poisix date and the last 32 bits contain a random value.'''

    _value: int = 0;
    '''Internally the value is saved as a uint64 value.'''

    def __init__(self, _value: int):
        if not _value:
            raise ValueError("Use one of the static methods to get an Uuid64 instance.")

        self._value = _value
    
    def __str__(self):
        # Convert the int value to a big endian hex string and separate it in 4 groups of 4 uppercase characters each.
        hex_string = self._value.to_bytes(8, 'big').hex()
        formatted_string = (hex_string[0:4] + '-' + hex_string[4:8] + '-' + hex_string[8:12] + '-' + hex_string[12:16]).upper()
        Uuid64._validate_uuid_string(formatted_string)

        return formatted_string
    
    @staticmethod
    def create_new_uuid() -> Uuid64:
        '''Creates a new random Uuid64 instance with the current UTC date.'''
        instance = Uuid64(Uuid64._create_random_value_with_date(datetime.now(timezone.utc)))

        return instance

    @staticmethod
    def create_new_from_date_string(date: str, date_formats: List[str]) -> Uuid64:
        '''Creates a new random Uuid64 instance for the provided date.'''
        if not date_formats:
            raise ValueError(f"date_formats must include at least one format")

        for fmt in date_formats:
            # Try to create a date from the string.
            try:
                date_value = datetime.strptime(date, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"time data '{date}' does not match any of the provided formats")

        instance = Uuid64(Uuid64._create_random_value_with_date(date_value));

        return instance
    
    @staticmethod
    def from_mongo_value(value: int) -> Uuid64:
        '''Creates a new Uuid64 instance from a uint64 value, which is the format used for saving in mongodb.
        The value must be for an UUID from the present or the past, not the future.'''
        Uuid64._validate_uuid_int_value(value)
        
        instance = Uuid64(value);

        return instance
    
    @staticmethod
    def from_formatted_string(value: str) -> str:
        '''Creates a new Uuid64 instance from a formatted string. The string must be an uppearcase hex string
        like this: "1234-5678-90AB-CDEF". The value must be for an UUID from the present or the past, not the future.'''
        Uuid64._validate_uuid_string(value)
        
        instance = Uuid64(int("0x" + value.replace("-", ""), 0))

        return instance
    
    def to_mongo_value(self) -> int:
        '''Returns a uint64 number representing the UUID, which is the format that must be saved in mongodb.'''
        Uuid64._validate_uuid_int_value(self._value)
        return self._value
    
    def to_formatted_str(self):
        '''Returns the formatted string representation of the UUID.'''
        return str(self)
    
    @staticmethod
    def _validate_uuid_string(uuid_string: str) -> bool:
        '''
        Validates if the provided string is a valid representation of a 64bit UUID. Valid representations
        have the following format: "1234-5678-90AB-CDEF". For the validation to pass, the UUID must also not
        be from the future.

        Returns:
            True if the validations pass. It never retuns False, it raises an error if the validation fails.
        '''
        validation_regex = re.compile(r"^[0-9A-F]{4}\b-[0-9A-F]{4}\b-[0-9A-F]{4}\b-[0-9A-F]{4}$")

        if not re.fullmatch(validation_regex, uuid_string):
            raise ValueError(f"Invalid UUID string.")
        
        uuid_posix_date = int("0x" + uuid_string.replace("-", "")[:8], 0)
        Uuid64._validate_date_not_in_the_future(uuid_posix_date)
        
        return True
    
    @staticmethod
    def _validate_uuid_int_value(uuid_int: int) -> bool:
        '''
        Validates if the provided number is a valid uint64 representation of a 64bit UUID. For the validation
        to pass, the UUID must also not be from the future.

        Returns:
            True if the validations pass. It never retuns False, it raises an error if the validation fails.
        '''
        if uuid_int < 0 or uuid_int > 18446744073709551615:
            raise ValueError(f"The provided number is not a valid UUID.")
        
        uuid_posix_date = int(uuid_int >> 32)
        Uuid64._validate_date_not_in_the_future(uuid_posix_date)
        
        return True
    
    @staticmethod
    def _validate_date_not_in_the_future(posix_date_value: int) -> bool:
        '''
        Validates if a number is a valid posix date not in the future.

        Returns:
            True if the validations pass. It never retuns False, it raises an error if the validation fails.
        '''
        current_posix_date = int(datetime.now(timezone.utc).timestamp()) & 0xFFFFFFFF
        
        if posix_date_value > current_posix_date + 3600:
            raise ValueError(f"The UUID date part must not be more than one hour in the future.")
        
        return True

    @staticmethod
    def _create_random_value_with_date(date_value: datetime) -> int:
        '''Creates a new uint64 value for a Uuid64 instance. The first part constains the provided date and the last
        part constians a random value'''
        # Posix time as a 32bit unsigned int
        unix_time_32bit = int(date_value.timestamp()) & 0xFFFFFFFF
        Uuid64._validate_date_not_in_the_future(unix_time_32bit)

        # Secure 32bit random number as 32 unsigned int
        random_32bit = int(secrets.randbits(32)) & 0xFFFFFFFF
        # 64bit number. Date in the first 32 bits and the random number in the last 32 bits
        return (random_32bit & 0xFFFFFFFF) | (unix_time_32bit << 32)
