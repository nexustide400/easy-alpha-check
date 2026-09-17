from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from alphacheck.analyzer import analyze_image


@pytest.mark.parametrize(
    "file_name",
    [
        "elf_true_transparent.png",
        "elf_partial_transparency.png",
        "elf_alpha_only.png",
        "elf_no_alpha.png",
        "app_icon.png",
    ],
)
def test_elf_asset_has_real_transparency(file_name: str) -> None:
    result = analyze_image(ROOT / "src" / "alphacheck" / "assets" / file_name)
    assert result["classification"] == "TRUE_TRANSPARENT"
    assert result["alpha_min"] == 0
    assert result["alpha_max"] == 255
