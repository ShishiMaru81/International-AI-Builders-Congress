"""Non-mutating release verification that survives `python -O` (MD-06, MR-01/03).

Unlike scripts/release_model.py, this command never writes model.json release flags
or overwrites failures.json. It raises explicit exceptions (not assert) so optimized
Python cannot bypass gates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


class ReleaseVerificationError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseVerificationError(message)


def verify_release(
    repo: Path,
    *,
    require_images: bool = True,
    predictions_path: Path | None = None,
) -> dict:
    out = repo / 'ml' / 'artifacts'
    card_path = out / 'model.json'
    evaluation_path = out / 'evaluation.json'
    model_path = out / 'model.pt'
    manifest_path = repo / 'data' / 'plantvillage' / 'manifest.csv'

    _require(card_path.is_file(), 'model.json missing')
    _require(evaluation_path.is_file(), 'evaluation.json missing')
    card = json.loads(card_path.read_text(encoding='utf-8'))
    evaluation = json.loads(evaluation_path.read_text(encoding='utf-8'))

    _require(card.get('field_validated') is False, 'field_validated must remain false until real field study')
    _require(isinstance(card.get('labels'), list) and len(card['labels']) >= 2, 'labels missing')
    _require(manifest_path.is_file(), 'manifest.csv missing')

    manifest_bytes = manifest_path.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    _require(
        manifest_sha == card.get('manifest_sha256'),
        f"manifest_sha256 mismatch: card={card.get('manifest_sha256')} actual={manifest_sha}",
    )

    rows = list(csv.DictReader(manifest_path.open(encoding='utf-8')))
    _require(len(rows) > 0, 'manifest empty')
    _require(len({r['group_id'] for r in rows}) == len(rows), 'duplicate group_id in manifest')
    _require(
        evaluation.get('split_counts') == {'train': 360, 'val': 90, 'test': 120},
        f"Unexpected split_counts: {evaluation.get('split_counts')}",
    )

    checks_run = [
        'manifest_sha256',
        'group_id_uniqueness',
        'split_counts',
        'field_validated_false',
    ]

    if model_path.is_file():
        artifact_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
        expected = str(card.get('artifact_sha256', '')).lower()
        _require(bool(expected), 'artifact_sha256 missing from model card')
        _require(artifact_sha == expected, f'artifact_sha256 mismatch: {artifact_sha} != {expected}')
        checks_run.append('artifact_sha256')
    else:
        raise ReleaseVerificationError('model.pt missing; cannot verify artifact digest')

    test_rows = [r for r in rows if r['split'] == 'test']
    _require(len(test_rows) == 120, f'Expected 120 holdout rows, found {len(test_rows)}')

    image_root = repo / 'data' / 'plantvillage' / 'images'
    per_image = []
    if require_images:
        missing = [r['path'] for r in test_rows if not (image_root / r['path']).is_file()]
        if missing:
            raise ReleaseVerificationError(
                f'{len(missing)} holdout images missing under data/plantvillage/images. '
                f'Rehydrate with scripts/validate_manifest.py --rehydrate before full parity.'
            )
        import torch
        from PIL import Image
        from torchvision import transforms

        torch.set_num_threads(2)
        model = torch.jit.load(str(model_path), map_location='cpu').eval()
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        correct = 0
        for row in test_rows:
            path = image_root / row['path']
            file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            _require(file_sha == row['sha256'].lower(), f"checksum fail for {row['path']}")
            with Image.open(path) as im:
                with torch.inference_mode():
                    probs = model(transform(im.convert('RGB')).unsqueeze(0)).softmax(1)[0]
            predicted_idx = int(probs.argmax())
            predicted = card['labels'][predicted_idx]
            score = float(probs.max())
            logits = [float(x) for x in probs.tolist()]
            ok = predicted == row['label']
            correct += int(ok)
            per_image.append({
                'path': row['path'],
                'expected': row['label'],
                'predicted': predicted,
                'score': score,
                'probs': logits,
                'correct': ok,
            })
        accuracy = correct / 120
        saved = float(evaluation['metrics']['accuracy'])
        _require(abs(accuracy - saved) < 1e-8, f'Aggregate accuracy mismatch export={accuracy} saved={saved}')
        checks_run.extend(['holdout_checksums', 'exported_model_aggregate_accuracy'])

        if predictions_path and predictions_path.is_file():
            saved_preds = json.loads(predictions_path.read_text(encoding='utf-8'))
            by_path = {p['path']: p for p in saved_preds}
            mismatches = []
            for item in per_image:
                prior = by_path.get(item['path'])
                if not prior:
                    mismatches.append({'path': item['path'], 'reason': 'missing_saved_prediction'})
                    continue
                if prior.get('predicted') != item['predicted']:
                    mismatches.append({'path': item['path'], 'reason': 'predicted_label_changed'})
                # Probabilities within tight absolute tolerance
                prior_probs = prior.get('probs') or []
                if prior_probs and any(abs(a - b) > 1e-5 for a, b in zip(prior_probs, item['probs'])):
                    mismatches.append({'path': item['path'], 'reason': 'prob_tolerance_exceeded'})
            _require(not mismatches, f'Per-image parity failures: {mismatches[:5]}')
            checks_run.append('per_image_export_parity')
        else:
            checks_run.append('per_image_table_not_provided')
    else:
        checks_run.append('images_skipped')

    return {
        'ok': True,
        'mutating': False,
        'checks_run': checks_run,
        'manifest_sha256': manifest_sha,
        'artifact_sha256': card.get('artifact_sha256'),
        'holdout_rows': len(test_rows),
        'per_image_count': len(per_image),
        'optimized_python_safe': True,
        'wrote_release_metadata': False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default=None)
    parser.add_argument('--allow-missing-images', action='store_true')
    parser.add_argument('--predictions', default=None, help='Optional saved per-image prediction table JSON')
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[1]
    try:
        report = verify_release(
            repo,
            require_images=not args.allow_missing_images,
            predictions_path=Path(args.predictions) if args.predictions else None,
        )
    except ReleaseVerificationError as exc:
        print(json.dumps({'ok': False, 'error': str(exc), 'mutating': False}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    # Deliberately no `assert` gates — this must work under python -O
    sys.exit(main())
