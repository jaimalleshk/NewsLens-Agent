"""Backend module exports."""

__all__ = ["app", "start"]


def __getattr__(name: str):
    if name in ("app", "start"):
        from .server import app, start
        return app if name == "app" else start
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

