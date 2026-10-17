"""Standalone FastAPI preview for the existing A2 frontend."""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from . import install_activity

ROOT = Path(__file__).resolve().parent.parent


def create_app() -> FastAPI:
    app = FastAPI(title="QueueSmart — Notifications & History", version="1.0.0")
    install_activity(app, demo_bridge=True)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, error: StarletteHTTPException):
        return JSONResponse({"error": str(error.detail)}, status_code=error.status_code, headers=error.headers)

    app.mount("/js", StaticFiles(directory=ROOT / "js"), name="javascript")
    app.mount("/css", StaticFiles(directory=ROOT / "css"), name="styles")

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def index():
        return FileResponse(ROOT / "index.html")

    pages = {file.name: file for file in ROOT.glob("*.html")}

    @app.api_route("/{page_name}", methods=["GET", "HEAD"], include_in_schema=False)
    def page(page_name: str):
        if page_name not in pages:
            raise HTTPException(404, "Page not found.")
        return FileResponse(pages[page_name])

    return app


app = create_app()
