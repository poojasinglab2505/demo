"""Entry point for production WSGI servers running the multi-tenant platform
(as opposed to wsgi.py, which runs the single-company tool)."""
from .platform.app import create_platform_app

app = create_platform_app()
