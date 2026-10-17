"""Serve only the public A2 UI files alongside the API."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]


def mount_ui(app: FastAPI):
    app.mount("/js", StaticFiles(directory=ROOT / "js"), name="javascript")
    app.mount("/css", StaticFiles(directory=ROOT / "css"), name="styles")

    def page_handler(path):
        def page():
            return FileResponse(path)
        return page

    for path in ROOT.glob("*.html"):
        app.add_api_route("/" + path.name, page_handler(path), methods=["GET", "HEAD"], include_in_schema=False)
    app.add_api_route("/", page_handler(ROOT / "index.html"), methods=["GET", "HEAD"], include_in_schema=False)
