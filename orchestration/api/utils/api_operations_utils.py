from enum import Enum

class ApiUtils():
    class SortOrder(str, Enum):
        '''Valid values for the sorting properties returned by the endpoints.'''
        asc = "asc"
        desc = "desc"
