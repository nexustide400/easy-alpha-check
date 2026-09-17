"""Preview rendering helpers. Source image files are never changed."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def _checkerboard(size: tuple[int, int], tile: int = 16) -> Image.Image:
    width, height = size
    background = Image.new("RGB", size, "#d8d8d8")
    draw = ImageDraw.Draw(background)
    alternate = "#f2f2f2"
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            if ((x // tile) + (y // tile)) % 2 == 0:
                draw.rectangle((x, y, min(x + tile - 1, width), min(y + tile - 1, height)), fill=alternate)
    return background


def render_preview(
    path: str | Path,
    max_size: tuple[int, int],
    *,
    alpha_map: bool = False,
) -> Image.Image:
    """Create an EXIF-aware checkerboard or alpha-map preview."""
    target = (max(1, max_size[0]), max(1, max_size[1]))
    with Image.open(path) as source:
        oriented = ImageOps.exif_transpose(source)
        rgba = oriented.convert("RGBA")
        rgba.thumbnail(target, Image.Resampling.LANCZOS)

        if alpha_map:
            # Show transparency itself as the bright silhouette: fully
            # transparent is cyan, fully opaque is charcoal, and partial
            # transparency is interpolated between them.
            transparency = ImageOps.invert(rgba.getchannel("A"))
            return ImageOps.colorize(transparency, black="#222831", white="#4FD1C5")

        checker = _checkerboard(rgba.size)
        checker.paste(rgba, (0, 0), rgba)
        return checker
