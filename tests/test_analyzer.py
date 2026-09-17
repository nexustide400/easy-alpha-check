from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alphacheck.analyzer import AlphaCheckError, analyze_image


def save_image(tmp_path: Path, name: str, mode: str, pixels: list, size: tuple[int, int]) -> Path:
    path = tmp_path / name
    image = Image.new(mode, size)
    image.putdata(pixels)
    image.save(path)
    return path


def test_rgb_jpeg_has_no_alpha(tmp_path: Path) -> None:
    path = save_image(tmp_path, "rgb.jpg", "RGB", [(255, 0, 0)] * 4, (2, 2))
    result = analyze_image(path)
    assert result["classification"] == "NO_ALPHA_CHANNEL"
    assert result["has_alpha"] is False


def test_rgb_png_has_no_alpha(tmp_path: Path) -> None:
    path = save_image(tmp_path, "rgb.png", "RGB", [(255, 0, 0)] * 4, (2, 2))
    assert analyze_image(path)["classification"] == "NO_ALPHA_CHANNEL"


def test_rgba_all_opaque(tmp_path: Path) -> None:
    path = save_image(tmp_path, "opaque.png", "RGBA", [(0, 0, 0, 255)] * 4, (2, 2))
    result = analyze_image(path)
    assert result["classification"] == "ALPHA_CHANNEL_ONLY"
    assert result["alpha_min"] == result["alpha_max"] == 255


def test_rgba_transparent_and_opaque(tmp_path: Path) -> None:
    path = save_image(
        tmp_path,
        "transparent.png",
        "RGBA",
        [(0, 0, 0, 0), (0, 0, 0, 255), (0, 0, 0, 0), (0, 0, 0, 255)],
        (2, 2),
    )
    result = analyze_image(path)
    assert result["classification"] == "TRUE_TRANSPARENT"
    assert result["transparent_pixels"] == 2
    assert result["transparent_percent"] == 50.0


def test_rgba_partial_only(tmp_path: Path) -> None:
    path = save_image(tmp_path, "partial.png", "RGBA", [(0, 0, 0, 1), (0, 0, 0, 254)], (2, 1))
    result = analyze_image(path)
    assert result["classification"] == "PARTIAL_TRANSPARENCY_ONLY"
    assert result["semi_transparent_pixels"] == 2


def test_rgba_mixed_alpha(tmp_path: Path) -> None:
    path = save_image(
        tmp_path,
        "mixed.png",
        "RGBA",
        [(0, 0, 0, 0), (0, 0, 0, 127), (0, 0, 0, 255)],
        (3, 1),
    )
    result = analyze_image(path)
    assert result["classification"] == "TRUE_TRANSPARENT"
    assert result["alpha_min"] == 0
    assert result["alpha_max"] == 255


def test_palette_png_transparency(tmp_path: Path) -> None:
    path = tmp_path / "palette.png"
    image = Image.new("P", (2, 1))
    image.putpalette([0, 0, 0, 255, 0, 0] + [0, 0, 0] * 254)
    image.putdata([0, 1])
    image.save(path, transparency=0)
    result = analyze_image(path)
    assert result["mode"] == "P"
    assert result["has_alpha"] is True
    assert result["classification"] == "TRUE_TRANSPARENT"
    assert result["transparent_pixels"] == 1


def test_content_bounds_are_inclusive(tmp_path: Path) -> None:
    pixels = [(0, 0, 0, 0)] * 9
    pixels[4] = (255, 255, 255, 255)
    path = save_image(tmp_path, "bounds.png", "RGBA", pixels, (3, 3))
    assert analyze_image(path)["content_bounds"] == (1, 1, 1, 1)


def test_corrupt_file_raises_friendly_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.png"
    path.write_bytes(b"not an image")
    with pytest.raises(AlphaCheckError):
        analyze_image(path)
