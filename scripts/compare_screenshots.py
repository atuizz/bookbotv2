from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


try:
    from PIL import Image, ImageChops
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "缺少依赖 Pillow，无法进行离线像素对比。\n"
        "请安装开发依赖后重试：python -m pip install -r requirements-dev.txt\n"
        f"原始错误: {e}"
    )


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class CompareResult:
    name: str
    baseline_path: str
    actual_path: str
    width: int
    height: int
    diff_pixels: int
    total_pixels: int
    diff_ratio: float
    diff_image_path: str


def iter_images(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            yield p


def build_binary_mask(diff_rgb: Image.Image, threshold: int) -> Image.Image:
    r, g, b = diff_rgb.split()
    m = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return m.point(lambda v: 255 if v > threshold else 0)


def compare_pair(baseline: Path, actual: Path, out_dir: Path, threshold: int) -> CompareResult:
    b_img = Image.open(baseline).convert("RGBA")
    a_img = Image.open(actual).convert("RGBA")

    if b_img.size != a_img.size:
        raise ValueError(f"图片尺寸不一致: baseline={b_img.size}, actual={a_img.size}")

    diff = ImageChops.difference(b_img, a_img)
    diff_rgb = diff.convert("RGB")

    mask = build_binary_mask(diff_rgb, threshold)
    total = b_img.size[0] * b_img.size[1]
    diff_pixels = sum(1 for v in mask.getdata() if v != 0)
    diff_ratio = diff_pixels / total if total else 0.0

    red = Image.new("RGBA", b_img.size, (255, 0, 0, 160))
    out = Image.composite(red, a_img, mask)

    out_path = out_dir / f"{baseline.stem}.diff.png"
    out.save(out_path)

    return CompareResult(
        name=baseline.name,
        baseline_path=str(baseline),
        actual_path=str(actual),
        width=b_img.size[0],
        height=b_img.size[1],
        diff_pixels=diff_pixels,
        total_pixels=total,
        diff_ratio=diff_ratio,
        diff_image_path=str(out_path),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="离线截图像素对比（简化 PixelMatch）")
    parser.add_argument("--baseline-dir", action="append", default=[], help="基线截图目录（可多次传入）")
    parser.add_argument("--actual-dir", required=True, help="实际截图目录（文件名需与基线一致）")
    parser.add_argument("--out-dir", default="artifacts/screenshot_diff", help="输出目录")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        help="阈值（0~1），数值越大越宽松；与 PixelMatch 阈值含义近似但非完全一致",
    )
    args = parser.parse_args()

    baseline_dirs = [Path(p) for p in (args.baseline_dir or [])]
    if not baseline_dirs:
        baseline_dirs = [Path("docs/原型截图"), Path("docs/screenshots")]

    actual_dir = Path(args.actual_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    threshold_int = max(0, min(255, int(args.threshold * 255)))

    baseline_files: list[Path] = []
    for d in baseline_dirs:
        if d.exists():
            baseline_files.extend(list(iter_images(d)))

    results: list[CompareResult] = []
    missing: list[str] = []
    mismatched: list[str] = []

    for baseline in sorted(baseline_files, key=lambda p: p.name):
        actual = actual_dir / baseline.name
        if not actual.exists():
            missing.append(baseline.name)
            continue
        try:
            results.append(compare_pair(baseline, actual, out_dir, threshold_int))
        except Exception as e:
            mismatched.append(f"{baseline.name}: {e}")

    summary = {
        "threshold": args.threshold,
        "baseline_dirs": [str(p) for p in baseline_dirs],
        "actual_dir": str(actual_dir),
        "out_dir": str(out_dir),
        "missing_actual": missing,
        "mismatched": mismatched,
        "results": [r.__dict__ for r in results],
        "max_diff_ratio": max((r.diff_ratio for r in results), default=0.0),
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    failing = [r for r in results if r.diff_ratio > args.threshold]
    return 1 if failing or mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main())

