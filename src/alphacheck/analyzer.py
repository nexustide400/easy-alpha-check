"""Read-only image alpha-channel analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_PIXELS = 250_000_000


class AlphaCheckError(Exception):
    """An image could not be safely analyzed."""


def _percentage(count: int, total: int) -> float:
    return round((count / total) * 100, 2) if total else 0.0


def _content_bounds(alpha: Image.Image) -> tuple[int, int, int, int] | None:
    """Return inclusive content bounds for pixels whose alpha is greater than zero."""
    bounds = alpha.getbbox()
    if bounds is None:
        return None
    left, top, right, bottom = bounds
    return left, top, right - 1, bottom - 1


def analyze_image(path: str | Path) -> dict[str, Any]:
    """Analyze an image without modifying it.

    Pixel statistics use the stored pixel matrix. EXIF orientation is intentionally
    only applied by the preview renderer.
    """
    image_path = Path(path)
    if not image_path.is_file():
        raise AlphaCheckError("ファイルが見つかりません。 / File not found.")

    try:
        file_size = image_path.stat().st_size
        with Image.open(image_path) as image:
            image_format = image.format or "Unknown"
            mode = image.mode
            width, height = image.size
            total_pixels = width * height

            if total_pixels > MAX_IMAGE_PIXELS:
                raise AlphaCheckError(
                    f"画像が大きすぎます（{total_pixels:,} pixels）。"
                    f"上限は {MAX_IMAGE_PIXELS:,} pixels です。 / The image exceeds the safety limit."
                )

            # Force decoding now so truncated/corrupt data is reported here.
            image.load()

            bands = image.getbands()
            has_alpha = "A" in bands or "transparency" in image.info

            result: dict[str, Any] = {
                "path": str(image_path.resolve()),
                "file_name": image_path.name,
                "format": image_format,
                "mode": mode,
                "width": width,
                "height": height,
                "file_size": file_size,
                "total_pixels": total_pixels,
                "has_alpha": has_alpha,
                "alpha_min": None,
                "alpha_max": None,
                "transparent_pixels": None,
                "semi_transparent_pixels": None,
                "opaque_pixels": None,
                "transparent_percent": None,
                "semi_transparent_percent": None,
                "opaque_percent": None,
                "content_bounds": (0, 0, width - 1, height - 1) if total_pixels else None,
                "classification": "NO_ALPHA_CHANNEL",
            }

            if not has_alpha:
                return result

            alpha = image.convert("RGBA").getchannel("A")
            histogram = alpha.histogram()
            transparent = histogram[0]
            semi_transparent = sum(histogram[1:255])
            opaque = histogram[255]
            non_empty_values = [index for index, count in enumerate(histogram) if count]

            if transparent:
                classification = "TRUE_TRANSPARENT"
            elif semi_transparent:
                classification = "PARTIAL_TRANSPARENCY_ONLY"
            else:
                classification = "ALPHA_CHANNEL_ONLY"

            result.update(
                {
                    "alpha_min": non_empty_values[0] if non_empty_values else None,
                    "alpha_max": non_empty_values[-1] if non_empty_values else None,
                    "transparent_pixels": transparent,
                    "semi_transparent_pixels": semi_transparent,
                    "opaque_pixels": opaque,
                    "transparent_percent": _percentage(transparent, total_pixels),
                    "semi_transparent_percent": _percentage(semi_transparent, total_pixels),
                    "opaque_percent": _percentage(opaque, total_pixels),
                    "content_bounds": _content_bounds(alpha),
                    "classification": classification,
                }
            )
            return result
    except AlphaCheckError:
        raise
    except Image.DecompressionBombError as exc:
        raise AlphaCheckError("安全上の上限を超える巨大画像です。 / The image exceeds the safety limit.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AlphaCheckError(
            "画像を読み込めません。壊れているか、未対応の形式です。 / "
            "The file is damaged or uses an unsupported image format."
        ) from exc
