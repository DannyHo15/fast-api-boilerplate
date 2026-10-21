"""Logging configuration."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging with a readable format.

    Call once at application startup (see `app.main.create_app`).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # Third-party loggers: keep at INFO/WARNING unless debugging.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
