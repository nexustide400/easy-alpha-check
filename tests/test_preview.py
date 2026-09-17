from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alphacheck.preview import render_preview


def test_transparency_map_highlights_transparent_pixels(tmp_path: Path) -> None:
    path = tmp_path / "alpha-scale.png"
    image = Image.new("RGBA", (3, 1))
    image.putdata([(255, 0, 0, 0), (255, 0, 0, 127), (255, 0, 0, 255)])
    image.save(path)

    normal_preview = render_preview(path, (3, 1), alpha_map=False)
    preview = render_preview(path, (3, 1), alpha_map=True)
    transparent = preview.getpixel((0, 0))
    partial = preview.getpixel((1, 0))
    opaque = preview.getpixel((2, 0))

    assert transparent == (79, 209, 197)
    assert opaque == (34, 40, 49)
    assert opaque[0] < partial[0] < transparent[0]
    assert preview.size == normal_preview.size == (3, 1)
