__all__ = ["core"]
__schema_version__ = "0.1"

try:
    from importlib.metadata import version as _version
    __version__ = _version("itaoagpt")
except Exception:
    __version__ = "0.0.0"
