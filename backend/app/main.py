from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.errors import ApiError, api_error_handler, http_error_handler, validation_error_handler
from app.routers import auth, queues, services
from app.store import seed_demo_services, seed_demo_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_demo_users()
    seed_demo_services()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="QueueSmart API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.include_router(auth.router)
    app.include_router(services.router)
    app.include_router(queues.router)

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
