"""Strict PlantVillage manifest validation (MD-05) and pinned download-only rehydration (MR-01).

This module never rewrites the published inventory. Use --rehydrate to download the exact
pinned source revision and verify recorded SHA-256 digests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

REQUIRED_LICENSE_FIELDS = (
    'name', 'version', 'url', 'license', 'attribution',
    'permission_verified', 'grouping_method',
)
REQUIRED_CSV_COLUMNS = ('path', 'label', 'group_id', 'split', 'sha256', 'source_url')


class ManifestValidationError(ValueError):
    def __init__(self, message: str, *, row: int | None = None, field: str | None = None):
        self.row = row
        self.field = field
        prefix = []
        if row is not None:
            prefix.append(f'row={row}')
        if field:
            prefix.append(f'field={field}')
        head = f"[{', '.join(prefix)}] " if prefix else ''
        super().__init__(head + message)


def _load_license(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ManifestValidationError('dataset.json must be a JSON object')
    for key in REQUIRED_LICENSE_FIELDS:
        if key not in data:
            raise ManifestValidationError(f'Missing verified dataset field: {key}', field=key)
    # Strict boolean — the string "false" must NOT pass (MD-05)
    if data.get('permission_verified') is not True:
        raise ManifestValidationError(
            'permission_verified must be JSON boolean true (string "false"/truthy values rejected)',
            field='permission_verified',
        )
    return data


def validate_manifest(
    manifest: str | Path,
    root: str | Path,
    license_file: str | Path,
    *,
    require_images: bool = True,
    decode_images: bool = True,
) -> tuple[list[dict], dict, list[str]]:
    """Validate inventory metadata, paths, hashes and (optionally) decodable images."""
    license_data = _load_license(Path(license_file))
    manifest_path = Path(manifest)
    with manifest_path.open(encoding='utf-8', newline='') as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ManifestValidationError('Manifest CSV has no header row')
        missing = [c for c in REQUIRED_CSV_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ManifestValidationError(f'Missing CSV columns: {", ".join(missing)}')
        rows = list(reader)

    if not rows:
        raise ManifestValidationError('Manifest contains no data rows')

    groups: dict[str, str] = {}
    hashes: dict[str, str] = {}
    labels: dict[str, set[str]] = {}
    base = Path(root).resolve()

    for index, row in enumerate(rows, start=2):
        for col in REQUIRED_CSV_COLUMNS:
            if not (row.get(col) or '').strip():
                raise ManifestValidationError('Required cell is empty', row=index, field=col)
        split = row['split'].strip()
        if split not in ('train', 'val', 'test'):
            raise ManifestValidationError('Invalid split', row=index, field='split')
        label = row['label'].strip()
        if 'tomato' not in label.lower():
            raise ManifestValidationError('Tomato labels only', row=index, field='label')
        group_id = row['group_id'].strip()
        recorded = row['sha256'].strip().lower()
        if len(recorded) != 64 or any(ch not in '0123456789abcdef' for ch in recorded):
            raise ManifestValidationError('sha256 must be 64 hex chars', row=index, field='sha256')

        relative = row['path'].strip().replace('\\', '/')
        image_path = (base / relative).resolve()
        if not image_path.is_relative_to(base):
            raise ManifestValidationError('Image path escapes dataset directory', row=index, field='path')

        if require_images:
            if not image_path.is_file():
                raise ManifestValidationError('Image file missing', row=index, field='path')
            payload = image_path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if digest != recorded:
                raise ManifestValidationError(
                    f'Recorded checksum mismatch (file={digest[:12]}… manifest={recorded[:12]}…)',
                    row=index,
                    field='sha256',
                )
            if decode_images:
                try:
                    from PIL import Image
                    with Image.open(image_path) as im:
                        im.verify()
                    with Image.open(image_path) as im:
                        im.convert('RGB').load()
                except Exception as exc:
                    raise ManifestValidationError(f'Undecodable image: {exc}', row=index, field='path') from exc

        for lookup, key in ((groups, group_id), (hashes, recorded)):
            if key in lookup and lookup[key] != split:
                raise ManifestValidationError(
                    'Group or exact duplicate leakage across splits',
                    row=index,
                    field='group_id' if lookup is groups else 'sha256',
                )
            lookup[key] = split
        labels.setdefault(split, set()).add(label)

    if set(labels) != {'train', 'val', 'test'}:
        raise ManifestValidationError('Each of train/val/test splits must be present')
    if len(labels['train']) < 2:
        raise ManifestValidationError('Training split must contain at least two classes')
    for split_name, split_labels in labels.items():
        if split_labels != labels['train']:
            raise ManifestValidationError(f'Split {split_name} labels do not match training classes')

    return rows, license_data, sorted(labels['train'])


def rehydrate_pinned(
    manifest: Path,
    output_root: Path,
    *,
    max_workers: int = 8,
    dry_run: bool = False,
) -> dict:
    """Download each manifest image from its pinned source_url and verify SHA-256.

    Never rewrites manifest.csv / dataset.json.
    """
    rows = list(csv.DictReader(manifest.open(encoding='utf-8')))
    output_root.mkdir(parents=True, exist_ok=True)
    verified = 0
    downloaded = 0
    failures: list[dict] = []

    def fetch_one(row: dict) -> tuple[str, str | None]:
        nonlocal downloaded
        target = output_root / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == row['sha256'].lower():
            return row['path'], None
        if dry_run:
            return row['path'], 'missing_for_dry_run'
        url = row['source_url']
        last_error = None
        for attempt in range(3):
            try:
                with urlopen(url, timeout=45) as response:
                    payload = response.read(25 * 1024 * 1024)
                digest = hashlib.sha256(payload).hexdigest()
                if digest != row['sha256'].lower():
                    return row['path'], f'checksum mismatch after download ({digest[:12]}…)'
                target.write_bytes(payload)
                downloaded += 1
                return row['path'], None
            except Exception as exc:
                last_error = str(exc)
                time.sleep(1 + attempt)
        return row['path'], last_error or 'download failed'

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(fetch_one, row) for row in rows]
        for future in as_completed(futures):
            path, error = future.result()
            if error:
                failures.append({'path': path, 'error': error})
            else:
                verified += 1

    return {
        'manifest': str(manifest),
        'output_root': str(output_root),
        'rows': len(rows),
        'verified': verified,
        'downloaded': downloaded,
        'failures': failures,
        'rewrote_published_inventory': False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate or rehydrate the published PlantVillage inventory')
    parser.add_argument('--manifest', default='data/plantvillage/manifest.csv')
    parser.add_argument('--root', default='data/plantvillage/images')
    parser.add_argument('--license', default='data/plantvillage/dataset.json')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--allow-missing-images', action='store_true', help='Validate CSV/license only')
    parser.add_argument('--rehydrate', action='store_true', help='Download pinned images without rewriting inventory')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    manifest = (repo / args.manifest).resolve() if not Path(args.manifest).is_absolute() else Path(args.manifest)
    root = (repo / args.root).resolve() if not Path(args.root).is_absolute() else Path(args.root)
    license_file = (repo / args.license).resolve() if not Path(args.license).is_absolute() else Path(args.license)

    if args.rehydrate:
        result = rehydrate_pinned(manifest, root, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        return 1 if result['failures'] else 0

    try:
        rows, license_data, labels = validate_manifest(
            manifest,
            root,
            license_file,
            require_images=not args.allow_missing_images,
            decode_images=not args.allow_missing_images,
        )
    except ManifestValidationError as exc:
        print(json.dumps({'status': 'invalid', 'error': str(exc)}, indent=2))
        return 1

    report = {
        'status': 'manifest_valid',
        'images': len(rows),
        'labels': labels,
        'dataset_version': license_data.get('version'),
        'permission_verified': True,
        'require_images': not args.allow_missing_images,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
