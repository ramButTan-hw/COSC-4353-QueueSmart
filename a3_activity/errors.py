"""Errors belonging only to the activity router and service."""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class ActivityRoute(APIRoute):
    """Return the original API's 400/error format for these routes only."""
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                response = await handler(request)
            except RequestValidationError as error:
                first = error.errors()[0]
                field = ".".join(str(part) for part in first["loc"] if part != "body")
                response = JSONResponse({"error": f"{field}: {first['msg']}"}, status_code=400)
            response.headers["Cache-Control"] = "no-store"
            return response

        return handle


async def activity_error(_request: Request, error: ApiError):
    return JSONResponse({"error": error.message}, status_code=error.status,
                        headers={"Cache-Control": "no-store"})
