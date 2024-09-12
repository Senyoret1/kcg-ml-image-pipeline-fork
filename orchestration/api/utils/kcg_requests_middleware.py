from fastapi import Request

from orchestration.api.api_utils import ApiResponseHandlerV1, ErrorCode

class KcgRequestsMiddleware():
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
