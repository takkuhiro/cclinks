"""Open links from a Claude Code session."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    # pyproject is the only place the version is written down.
    __version__ = version("cclinks")
except PackageNotFoundError:  # a source tree with nothing installed
    __version__ = "0.0.0+unknown"
