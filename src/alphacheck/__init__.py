"""Easy Alpha Check - inspect whether image files contain real transparency."""

from .analyzer import AlphaCheckError, analyze_image

__all__ = ["AlphaCheckError", "analyze_image"]
__version__ = "0.1.0"
