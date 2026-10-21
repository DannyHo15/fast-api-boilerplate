"""API layer (presentation adapter): FastAPI routers, schemas, DI, errors.

This layer knows about HTTP and the framework. It translates between
HTTP/JSON and the domain/application layers, and translates domain
exceptions into HTTP error responses.
"""
