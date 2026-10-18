"""One error shape for the whole API:

    {"error": {"code": "...", "message": "...", "fields": {"email": "..."}}}
"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
}


class ApiError(Exception):
    """Raise this from any module to return a consistent error response."""

    def __init__(self, status_code, code, message, fields=None, headers=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields
        self.headers = headers


def error_body(code, message, fields=None):
    body = {"code": code, "message": message}
    if fields:
        body["fields"] = fields
    return {"error": body}


def describe(err):
    "Turn pydantic errors into human readable comments"
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    if kind == "missing":
        return "This field is required."
    if kind == "string_too_short":
        return "This field is required." if ctx.get("min_length") == 1 else f"Must be at least {ctx.get('min_length')} characters."
    if kind == "string_too_long":
        return f"Must be at most {ctx.get('max_length')} characters."
    if kind == "string_type":
        return "Must be a string."
    if kind in ("int_type", "int_parsing"):
        return "Must be a whole number."
    if kind == "greater_than_equal":
        return f"Must be at least {ctx.get('ge')}."
    if kind == "less_than_equal":
        return f"Must be at most {ctx.get('le')}."
    if kind == "literal_error":
        return f"Must be one of: {ctx.get('expected')}."
    if kind == "extra_forbidden":
        return "Unknown field."
    if kind == "value_error":
        return err.get("msg", "Invalid value.").removeprefix("Value error, ")
    return err.get("msg", "Invalid value.")


async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.fields),
        headers=exc.headers,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError):
    fields = {}
    for err in exc.errors():
        loc = [str(p) for p in err["loc"] if p != "body"]
        name = loc[-1] if loc else "body"
        fields.setdefault(name, describe(err))
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", "Request is invalid.", fields),
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException):
    code = STATUS_CODES.get(exc.status_code, "error")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, str(exc.detail)),
        headers=getattr(exc, "headers", None),
    )
