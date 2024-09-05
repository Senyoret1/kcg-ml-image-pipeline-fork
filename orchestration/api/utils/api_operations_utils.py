from enum import Enum

class ApiUtils():
    class SortOrder(str, Enum):
        asc = "asc"
        desc = "desc"
