"""V.I.S.O.R — Visual Intelligence System for Orchestrated Reasoning."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("visor-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
