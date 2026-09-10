#!/usr/bin/env python3
"""Validate natural-language intent fixtures and their documentation coverage.

This is a static contract/schema check, not a model-behavior evaluation. It
proves every intent the skill claims to handle is backed by an option or a
behavior that the skill's own documentation actually mentions.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

REQUIRED_FAMILIES = {
    "basic", "geometry", "convert", "transform", "color", "alpha", "composite",
    "text", "effects", "animation", "batch", "compare", "metadata", "raster",
    "pipeline", "performance", "limitation", "preflight",
}
ALLOWED_FIELDS = {
    "id", "prompt", "expected_options", "expected_geometry", "expected_behavior",
    "family",
}
DOC_FILES = (
    "SKILL.md",
    "references/command-line-processing.md",
    "references/operation-reference.md",
    "references/natural-language-recipes.md",
    "references/formats-and-compatibility.md",
)
# Every skill must state these, or its safety story is incomplete.
REQUIRED_SAFETY_PHRASES = (
    "mogrify overwrites",
    "not redaction",
    "command -v magick",
    "https://imagemagick.org/script/download.php",
    "security policy",
)


def validate(root: Path) -> dict[str, object]:
    cases_path = root / "tests" / "natural_language_cases.json"
    cases = json.loads(cases_path.read_text())

    docs_parts = []
    missing_docs = []
    for name in DOC_FILES:
        path = root / name
        if path.is_file():
            docs_parts.append(path.read_text())
        else:
            missing_docs.append(name)
    docs = "\n".join(docs_parts)

    errors: list[str] = list(f"missing documentation file: {name}" for name in missing_docs)
    ids: set[str] = set()
    prompts: set[str] = set()
    families: set[str] = set()

    if not isinstance(cases, list) or not cases:
        return {"ok": False, "errors": ["case file must be a nonempty JSON array"]}

    for index, case in enumerate(cases):
        label = case.get("id", f"index-{index}") if isinstance(case, dict) else f"index-{index}"
        if not isinstance(case, dict):
            errors.append(f"{label}: case must be an object")
            continue
        unknown = set(case) - ALLOWED_FIELDS
        if unknown:
            errors.append(f"{label}: unknown fields {sorted(unknown)}")
        for field in ("id", "prompt", "family"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f"{label}: missing nonempty {field}")
        if case.get("id") in ids:
            errors.append(f"{label}: duplicate id")
        ids.add(case.get("id"))
        if case.get("prompt") in prompts:
            errors.append(f"{label}: duplicate prompt")
        prompts.add(case.get("prompt"))
        families.add(case.get("family"))

        expected = case.get("expected_options", [])
        behavior = case.get("expected_behavior")
        if not expected and not behavior and "expected_geometry" not in case:
            errors.append(f"{label}: no expected options/geometry/behavior")
        if expected:
            if not isinstance(expected, list) or not all(isinstance(x, str) and x for x in expected):
                errors.append(f"{label}: expected_options must be nonempty strings")
            else:
                for token in expected:
                    if token not in docs:
                        errors.append(f"{label}: expected token not documented: {token}")
        if "expected_geometry" in case and str(case["expected_geometry"]) not in docs:
            errors.append(f"{label}: expected geometry not documented: {case['expected_geometry']}")

    missing_families = REQUIRED_FAMILIES - families
    if missing_families:
        errors.append(f"missing families: {sorted(missing_families)}")

    haystack = (docs + " " + " ".join(str(case.get("expected_behavior", "")) for case in cases)).lower()
    for phrase in REQUIRED_SAFETY_PHRASES:
        if phrase.lower() not in haystack:
            errors.append(f"safety/preflight phrase missing from docs and cases: {phrase}")

    return {
        "ok": not errors,
        "kind": "static-schema-and-documentation-coverage",
        "not_model_behavior_test": True,
        "cases": len(cases),
        "families": sorted(f for f in families if f),
        "errors": errors,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = validate(root)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
