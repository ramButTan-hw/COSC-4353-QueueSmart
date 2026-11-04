"""Tests never touch the real database file: use an in-memory SQLite database unless told otherwise.

This runs for both pytest and `python -m tests.serve_app` (the front-end tests), before the app is imported.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
