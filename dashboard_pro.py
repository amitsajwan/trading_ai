"""Dashboard shim that delegates to dashboard.app."""

from dashboard.app import app, add_camel_aliases

__all__ = ["app", "add_camel_aliases"]
