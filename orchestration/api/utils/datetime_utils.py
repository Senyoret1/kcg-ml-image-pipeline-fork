from datetime import datetime

def get_current_datetime_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class DatetimeUtils():
    @staticmethod
    def get_datetime_from_api_string(date_str: str) -> datetime:
        """
        Converts a date string in the format 'YYYY-MM-DDTHH:MM:SS' to a datetime instance, without time zone info.
        """
        
        try:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError as e:
            raise Exception(f"Error parsing date string: {e}")
