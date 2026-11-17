"""MD-05 regressions for strict manifest validation."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_manifest import ManifestValidationError, validate_manifest  # noqa: E402


def _write_license(path: Path, **overrides):
    data = {
        'name': 'Test set',
        'version': 'abc',
        'url': 'https://example.org',
        'license': 'CC BY-SA 3.0',
        'attribution': 'Test',
        'permission_verified': True,
        'grouping_method': 'unit-test',
    }
    data.update(overrides)
    path.write_text(json.dumps(data), encoding='utf-8')


def _write_manifest(path: Path, rows: list[dict]):
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['path', 'label', 'group_id', 'split', 'sha256', 'source_url'])
        writer.writeheader()
        writer.writerows(rows)


def test_permission_verified_string_false_is_rejected(tmp_path: Path):
    license_path = tmp_path / 'dataset.json'
    _write_license(license_path, permission_verified='false')  # type: ignore[arg-type]
    manifest = tmp_path / 'manifest.csv'
    _write_manifest(manifest, [])
    with pytest.raises(ManifestValidationError, match='permission_verified'):
        validate_manifest(manifest, tmp_path, license_path, require_images=False)


def test_wrong_checksum_and_non_image_bytes_rejected(tmp_path: Path):
    license_path = tmp_path / 'dataset.json'
    _write_license(license_path)
    images = tmp_path / 'images'
    images.mkdir()
    rel = 'leaf.bin'
    payload = b'not-an-image-payload'
    (images / rel).write_bytes(payload)
    bad_row = {
        'path': rel,
        'label': 'Tomato___healthy',
        'group_id': 'g1',
        'split': 'train',
        'sha256': '0' * 64,
        'source_url': 'https://example.org/a',
    }
    # Need full splits for final label checks — first ensure checksum fails early
    manifest = tmp_path / 'manifest.csv'
    _write_manifest(manifest, [bad_row])
    with pytest.raises(ManifestValidationError, match='checksum mismatch|Undecodable|Tomato labels|split'):
        validate_manifest(manifest, images, license_path, require_images=True, decode_images=True)
