#!/usr/bin/env python3
"""
Temporary batch tester for the Gemini aircraft classifier.

Usage:
    python test_local_images.py               # scans ./testimages
    python test_local_images.py --dir foo     # custom folder
    python test_local_images.py --topk --k 5  # ask for top-5 airlines
    python test_local_images.py --save out.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

import config as cfg
from gemini_classifier import classify_aircraft, classify_aircraft_topk


IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def list_images(folder: Path) -> List[Path]:
    """Return sorted list of image files in folder."""
    return sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS and p.is_file()]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch test local images with Gemini.")
    parser.add_argument(
        "--dir",
        default="testimages",
        help="Folder containing test images (default: ./testimages)",
    )
    parser.add_argument(
        "--topk",
        action="store_true",
        default=False,
        help="Use top-k airline predictions instead of single best.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Number of top-k predictions (default: config.TOP_K).",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Optional JSON file to write full results.",
    )
    args = parser.parse_args()

    folder = Path(args.dir)
    if not folder.exists():
        print(f"[ERROR] Folder not found: {folder}")
        return 1

    images = list_images(folder)
    if not images:
        print(f"[ERROR] No .jpg/.jpeg/.png files found in {folder}")
        return 1

    use_topk = args.topk or cfg.USE_TOPK
    k = args.k if args.k is not None else cfg.TOP_K

    print(f"[INFO] GEMINI_MODEL={cfg.GEMINI_MODEL}")
    print(f"[INFO] Processing {len(images)} image(s) from {folder}")
    print(f"[INFO] topk={use_topk} k={k if use_topk else 'n/a'}")
    print()

    results = []
    for img_path in images:
        try:
            img_bytes = img_path.read_bytes()
            if use_topk:
                result = classify_aircraft_topk(img_bytes, k=k)
            else:
                result = classify_aircraft(img_bytes)
        except Exception as exc:  # pragma: no cover - diagnostic
            print(f"[ERROR] {img_path.name}: {exc}")
            result = {"error": str(exc)}

        # human-readable line
        airline = result.get("airline", "UNKNOWN")
        family = result.get("aircraft_family", "UNKNOWN")
        conf = result.get("confidence", result.get("family_confidence", 0.0))
        print(f"{img_path.name:<35} airline={airline:<22} family={family:<14} conf={conf:.2f}")

        results.append({"file": img_path.name, "result": result})

    if args.save:
        out_path = Path(args.save)
        out_path.write_text(json.dumps(results, indent=2))
        print(f"\n[INFO] Results saved to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
