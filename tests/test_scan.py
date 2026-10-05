import io
import random
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from synthform import __version__
from synthform import scan
from synthform.scan import apply_scan, params_for

ROOT = Path(__file__).resolve().parents[1]
GRAIN_SIGMA = 5.0
MM_PER_INCH = 25.4
PYTHON_CLAIM = "Python 3.12/3.13 only, no CI"


def _scan_params(seed: int, dpi: int = 200):
    return params_for(random.Random(seed), dpi)


def _add_grain(page: Image.Image, rng: random.Random, sigma: float) -> Image.Image:
    return scan._grain(page, rng, sigma)


def _mean_shift(level: int, seed: int = 1) -> float:
    page = Image.new("RGB", (400, 400), (level, level, level))
    grained = _add_grain(page, random.Random(seed), GRAIN_SIGMA)
    return ImageStat.Stat(grained).mean[0] - level


@pytest.mark.parametrize(
    ("level", "low", "high"),
    [(255, -2.25, 0.0), (0, 0.0, 2.25), (128, -0.25, 0.25)],
    ids=["white", "black", "gray"],
)
def test_grain_is_zero_mean_on_white_black_and_gray(level: int, low: float, high: float):
    for seed in (1, 2, 3):
        assert low <= _mean_shift(level, seed) <= high, (level, seed)


def test_grain_has_the_requested_spread_on_gray():
    page = Image.new("RGB", (400, 400), (128, 128, 128))
    grained = _add_grain(page, random.Random(4), GRAIN_SIGMA)
    spread = ImageStat.Stat(grained).stddev[0]
    assert 4.5 <= spread <= 5.5


def test_grain_adds_the_same_offset_to_red_green_and_blue():
    page = Image.new("RGB", (120, 120), (128, 128, 128))
    red, green, blue = _add_grain(page, random.Random(5), GRAIN_SIGMA).split()
    assert ImageChops.difference(red, green).getbbox() is None
    assert ImageChops.difference(red, blue).getbbox() is None


def test_grain_repeats_for_one_seed_and_changes_with_another():
    page = Image.new("RGB", (120, 120), (128, 128, 128))
    first = _add_grain(page, random.Random(6), GRAIN_SIGMA)
    again = _add_grain(page, random.Random(6), GRAIN_SIGMA)
    other = _add_grain(page, random.Random(7), GRAIN_SIGMA)
    assert ImageChops.difference(first, again).getbbox() is None
    assert ImageChops.difference(first, other).getbbox() is not None


@pytest.mark.parametrize("dpi", [100, 200, 300])
def test_blur_sigma_stays_between_0_10_and_0_22_mm(dpi: int):
    for seed in range(60):
        params = params_for(random.Random(seed), dpi)
        sigma_mm = params.blur_radius * MM_PER_INCH / dpi
        assert 0.10 - 1e-9 <= sigma_mm <= 0.22 + 1e-9, (dpi, seed)


def test_blur_radius_scales_with_dpi():
    for seed in range(20):
        at_100 = params_for(random.Random(seed), 100)
        at_200 = params_for(random.Random(seed), 200)
        assert at_200.blur_radius / at_100.blur_radius == pytest.approx(2.0)
        assert at_200.angle == at_100.angle
        assert at_200.jpeg_quality == at_100.jpeg_quality
        assert at_200.grain_sigma == at_100.grain_sigma


def test_grain_sigma_stays_between_2_and_5_levels():
    for seed in range(60):
        assert 2.0 <= params_for(random.Random(seed), 200).grain_sigma <= 5.0


def test_cast_is_applied_before_jpeg(monkeypatch):
    seen: list = []
    real_encode = scan._jpeg_bytes

    def spy(image: Image.Image, quality: int) -> bytes:
        seen.append(image.copy())
        result = real_encode(image, quality)
        seen.append(Image.open(io.BytesIO(result)).convert("RGB"))
        return result

    monkeypatch.setattr(scan, "_jpeg_bytes", spy)
    params = replace(_scan_params(1), angle=0.0, cast_alpha=0.12, cast_color=(240, 230, 200))
    page = Image.new("RGB", (96, 96), (255, 255, 255))
    result = apply_scan(page, params, random.Random(1))
    encoder_input, decoded = seen
    red_mean, _, blue_mean = ImageStat.Stat(encoder_input).mean
    assert red_mean - blue_mean > 3
    assert ImageChops.difference(result, decoded).getbbox() is None


def test_pyproject_and_package_versions_match():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__ == "0.2.0"


def test_python_version_claims_agree_in_pyproject_readme_and_skill():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["requires-python"] == ">=3.12,<3.14"
    classifiers = {item for item in project["classifiers"] if item.startswith("Programming Language :: Python :: 3.")}
    assert classifiers == {
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    }
    for relative in ("README.md", "skills/verify-synthform/SKILL.md"):
        assert PYTHON_CLAIM in (ROOT / relative).read_text(encoding="utf-8"), relative
