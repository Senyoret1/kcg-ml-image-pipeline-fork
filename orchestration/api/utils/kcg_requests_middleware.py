from fastapi import Request

from orchestration.api.api_utils import ApiResponseHandlerV1, ErrorCode

class KcgRequestsMiddleware():
    '''
    Includes a function called "process_requests" that works as a FastAPI middleware. The functions do some
    important things:

        - Processes all the uncatched errors raised during the excecution of any endpoint and returns a standarized
        error response to the client, instead of a plain error 500 responses that FastAPI would return by default.

        - Makes the request object include a object for creating standarized API responses. The object can be accesed
        in the endpoints code in "request.state.response_handler".
    '''
    @staticmethod
    async def process_requests(request: Request, call_next):
        response_handler = await ApiResponseHandlerV1.createInstance(request)
        request.state.response_handler = response_handler
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            print(f"Exception: {e}")
            return response_handler.create_error_response_v1(
                error_code=ErrorCode.OTHER_ERROR,
                error_string=str(e),
                http_status_code=500
            )
