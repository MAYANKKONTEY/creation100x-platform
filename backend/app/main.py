"""ASGI entry point: `uvicorn app.main:app`."""

from app.api.main import create_app

app = create_app()
