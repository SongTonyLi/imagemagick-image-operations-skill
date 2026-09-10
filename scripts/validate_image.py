#!/usr/bin/env python3
"""Validate image outputs with the ImageMagick found on PATH.

Reports geometry, format, colorspace, alpha, frame count, bit depth and mean
value for each path, plus optional assertions. Exit status is nonzero if any
file fails to decode or fails an assertion, so it can gate a workflow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

DOWNLOAD_URL = "https://imagemagick.org/script/download.php"
# One record per frame; %n is the total frame count of the sequence.
FIELDS = "%m|%w|%h|%[colorspace]|%A|%z|%n|%[mean]|%[standard-deviation]|%Q\n"


def identify(path: Path, binary: str) -> dict[str, object]:
    result: dict[str, object] = {"path": str(path), "ok": False}
    if not path.is_file():
        result["error"] = "not a file"
        return result
    size = path.stat().st_size
    result["bytes"] = size
    if size == 0:
        result["error"] = "file is empty"
        return result

    # -ping avoids decoding full pixel data, but %[mean] needs real pixels.
    proc = subprocess.run([binary, "identify", "-format", FIELDS, str(path)],
                          text=True, capture_output=True)
    if proc.returncode != 0:
        result["error"] = (proc.stderr or proc.stdout).strip()[-800:]
        result["identify_exit"] = proc.returncode
        return result

    frames = [line for line in proc.stdout.splitlines() if line.strip()]
    if not frames:
        result["error"] = "identify produced no output"
        return result

    first = frames[0].split("|")
    if len(first) < 10:
        result["error"] = f"unexpected identify output: {frames[0]!r}"
        return result

    result.update({
        "format": first[0],
        "width": int(first[1]),
        "height": int(first[2]),
        "colorspace": first[3],
        "alpha": first[4],
        "depth": int(first[5]),
        "frames": len(frames),
        "declared_frames": int(first[6]) if first[6].isdigit() else None,
        "mean": float(first[7]) if first[7] else None,
        "standard_deviation": float(first[8]) if first[8] else None,
        "quality": int(first[9]) if first[9].isdigit() else None,
    })
    if proc.stderr.strip():
        result["warnings"] = proc.stderr.strip()[-400:]
    result["ok"] = True
    return result


def assert_expectations(record: dict[str, object], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    if args.expect_format and str(record.get("format", "")).upper() != args.expect_format.upper():
        failures.append(f"format {record.get('format')} != {args.expect_format}")
    if args.expect_width is not None and record.get("width") != args.expect_width:
        failures.append(f"width {record.get('width')} != {args.expect_width}")
    if args.expect_height is not None and record.get("height") != args.expect_height:
        failures.append(f"height {record.get('height')} != {args.expect_height}")
    if args.expect_frames is not None and record.get("frames") != args.expect_frames:
        failures.append(f"frames {record.get('frames')} != {args.expect_frames}")
    if args.expect_alpha is not None:
        has_alpha = str(record.get("alpha", "")).lower() in {"true", "blend", "on", "activate"}
        if has_alpha != args.expect_alpha:
            failures.append(f"alpha {record.get('alpha')} != {args.expect_alpha}")
    if args.max_bytes is not None and int(record.get("bytes", 0)) > args.max_bytes:
        failures.append(f"bytes {record.get('bytes')} > {args.max_bytes}")
    # A uniformly flat image usually means the pipeline silently produced a blank.
    if args.reject_blank and record.get("standard_deviation") == 0.0:
        failures.append("image is completely uniform (standard deviation 0)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="+", type=Path)
    parser.add_argument("--expect-format")
    parser.add_argument("--expect-width", type=int)
    parser.add_argument("--expect-height", type=int)
    parser.add_argument("--expect-frames", type=int)
    parser.add_argument("--expect-alpha", type=lambda v: v.lower() in {"1", "true", "yes"})
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--reject-blank", action="store_true",
                        help="fail if an image has zero pixel variance. Only use when the "
                             "output should have detail: a trimmed solid, a color swatch, a "
                             "mask, or a generated xc: canvas is legitimately uniform.")
    args = parser.parse_args()

    binary = shutil.which("magick") or shutil.which("identify")
    if not binary:
        print(f"ImageMagick was not found on PATH. Install it from {DOWNLOAD_URL}",
              file=sys.stderr)
        return 127
    # `identify` (IM6) does not accept a leading "identify" argument.
    if Path(binary).name != "magick":
        results = []
        for path in args.image:
            resolved = path.expanduser().resolve()
            proc = subprocess.run([binary, "-format", FIELDS, str(resolved)],
                                  text=True, capture_output=True)
            record: dict[str, object] = {"path": str(resolved), "ok": proc.returncode == 0}
            if proc.returncode:
                record["error"] = (proc.stderr or proc.stdout).strip()[-800:]
            else:
                record["identify"] = proc.stdout.strip()
            results.append(record)
        print(json.dumps(results, indent=2))
        return 0 if all(r["ok"] for r in results) else 1

    results = []
    for path in args.image:
        record = identify(path.expanduser().resolve(), binary)
        if record["ok"]:
            failures = assert_expectations(record, args)
            if failures:
                record["ok"] = False
                record["assertion_failures"] = failures
        results.append(record)

    print(json.dumps(results, indent=2))
    return 0 if all(record["ok"] for record in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
