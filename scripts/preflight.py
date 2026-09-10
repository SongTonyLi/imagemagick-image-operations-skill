#!/usr/bin/env python3
"""Report ImageMagick capability without changing any file.

Prints a JSON capability report: binary, version, quantum/HDRI build flags,
compiled delegates, available sub-commands, coder policy denials, resource
limits, and optional external helpers. Read this before planning a command;
never assume a format or feature exists.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

DOWNLOAD_URL = "https://imagemagick.org/script/download.php"
# Legacy IM6 names are shims under IM7; probe both so the report is honest.
TOOLS = ("magick", "convert", "identify", "mogrify", "montage", "composite",
         "compare", "stream", "conjure", "display", "animate", "import")
# External programs ImageMagick shells out to for formats it cannot decode itself.
HELPERS = ("gs", "ffmpeg", "inkscape", "rsvg-convert", "exiftool", "cwebp",
           "dwebp", "avifenc", "dcraw", "libraw", "potrace", "ufraw-batch")
# Formats worth confirming explicitly: each is delegate- or policy-gated.
PROBE_FORMATS = ("PNG", "JPEG", "WEBP", "HEIC", "AVIF", "JXL", "GIF", "TIFF",
                 "SVG", "PDF", "PS", "EPS", "PSD", "DNG", "MIFF", "MPC", "MP4")


def run(*args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def parse_version(text: str) -> dict[str, object]:
    info: dict[str, object] = {}
    match = re.search(r"ImageMagick\s+(\d+)\.(\d+)\.(\d+)(?:-(\d+))?", text)
    if match:
        info["version"] = match.group(0).replace("ImageMagick ", "")
        info["major"] = int(match.group(1))
    quantum = re.search(r"Q(\d+)", text)
    if quantum:
        info["quantum_depth"] = int(quantum.group(1))
    info["hdri"] = "HDRI" in text
    delegates = re.search(r"(?m)^Delegates \(built-in\):\s*(.*)$", text)
    info["delegates"] = sorted(delegates.group(1).split()) if delegates else []
    features = re.search(r"(?m)^Features:\s*(.*)$", text)
    info["features"] = sorted(features.group(1).split()) if features else []
    return info


def list_formats(binary: str) -> dict[str, str]:
    """Map FORMAT -> mode string (e.g. 'rw+') from `magick -list format`."""
    rc, out = run(binary, "-list", "format")
    if rc != 0:
        return {}
    formats: dict[str, str] = {}
    for line in out.splitlines():
        match = re.match(r"\s+([A-Za-z0-9]+)\*?\s+[A-Za-z0-9-]+\s+([rw+-]{3,4})\s", line)
        if match:
            formats[match.group(1).upper()] = match.group(2)
    return formats


def denied_coders(binary: str) -> list[str]:
    """Coders that security-policy.xml forbids. A denial is a policy error, not a bug."""
    rc, out = run(binary, "-list", "policy")
    if rc != 0:
        return []
    denied: list[str] = []
    pattern = None
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("Path:"):
            pattern = None
        name = re.match(r"pattern:\s*(\S+)", stripped)
        if name:
            pattern = name.group(1)
        if pattern and re.match(r"rights:\s*None", stripped, re.IGNORECASE):
            denied.append(pattern)
            pattern = None
    return sorted(set(denied))


def policy_paths(binary: str) -> list[str]:
    rc, out = run(binary, "-list", "policy")
    if rc != 0:
        return []
    return re.findall(r"(?m)^Path:\s*(\S+)", out)


def resource_limits(binary: str) -> dict[str, str]:
    rc, out = run(binary, "identify", "-list", "resource")
    if rc != 0:
        rc, out = run(binary, "-list", "resource")
    if rc != 0:
        return {}
    limits: dict[str, str] = {}
    for line in out.splitlines():
        match = re.match(r"\s+([A-Za-z ]+):\s+(\S+)\s*$", line)
        if match:
            limits[match.group(1).strip().lower().replace(" ", "_")] = match.group(2)
    return limits


def probe_write(binary: str, fmt: str) -> bool:
    """Actually encode a 1x1 pixel. `-list format` can advertise a coder whose
    module is missing from disk, so only a real round-trip proves support."""
    proc = subprocess.run([binary, "-size", "1x1", "xc:red", f"{fmt}:-"],
                          capture_output=True, timeout=60)
    return proc.returncode == 0 and len(proc.stdout) > 0


def main() -> int:
    binary = shutil.which("magick") or shutil.which("convert")
    if not binary:
        print(f"ImageMagick was not found on PATH. Install it from {DOWNLOAD_URL}",
              file=sys.stderr)
        return 127

    rc, version_output = run(binary, "-version")
    report: dict[str, object] = {"binary": binary, "version_exit": rc}
    report.update(parse_version(version_output))
    report["im7"] = report.get("major") == 7
    report["tools"] = {name: shutil.which(name) for name in TOOLS}
    report["helpers"] = {name: shutil.which(name) for name in HELPERS}

    formats = list_formats(binary)
    report["format_count"] = len(formats)
    report["probe_formats"] = {name: formats.get(name, "MISSING") for name in PROBE_FORMATS}
    report["policy_paths"] = policy_paths(binary)
    report["denied_coders"] = denied_coders(binary)
    report["resource_limits"] = resource_limits(binary)

    warnings: list[str] = []
    if not report["im7"]:
        warnings.append("ImageMagick 6 detected: use `convert`, and expect IM6 option "
                        "semantics (see references/formats-and-compatibility.md).")
    for name in ("PDF", "PS", "EPS"):
        if name in report["denied_coders"]:
            warnings.append(f"security policy denies {name}; PDF/PostScript work will fail.")
    if not shutil.which("gs") and formats.get("PDF"):
        warnings.append("Ghostscript (gs) not on PATH: PDF/EPS/PS rendering may fail.")

    # A delegate compiled into the binary does not guarantee a loadable coder
    # module. Homebrew upgrades in particular can leave `-version` advertising
    # heic/jxl while lib/ImageMagick/modules-*/coders/*.la is gone.
    delegate_to_formats = {"heic": ("HEIC", "HEIF", "AVIF"), "jxl": ("JXL",),
                           "webp": ("WEBP",), "raw": ("DNG",), "jp2": ("JP2",),
                           "png": ("PNG",), "jpeg": ("JPEG",), "tiff": ("TIFF",)}
    broken: list[str] = []
    for delegate, names in delegate_to_formats.items():
        if delegate in report["delegates"] and not any(n in formats for n in names):
            broken.append(f"{delegate} -> {'/'.join(names)}")
    if broken:
        warnings.append(
            "delegate/coder mismatch: -version advertises " + ", ".join(broken) +
            " but -list format does not register them (coder module missing). "
            "These formats will fail at runtime; reinstall ImageMagick.")
    report["broken_delegates"] = broken
    report["warnings"] = warnings

    print(json.dumps(report, indent=2))
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    raise SystemExit(main())
