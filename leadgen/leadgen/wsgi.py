"""Entry point for production WSGI servers (gunicorn, etc.)."""
from .web.app import create_app

app = create_app()
