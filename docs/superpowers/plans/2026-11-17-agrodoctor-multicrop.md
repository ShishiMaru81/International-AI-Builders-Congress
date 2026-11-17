# AgroDoctor Multi-crop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Genuine local research inference beyond tomato with crop-aware plots/cases and stable upload/history behavior.
**Architecture:** Preserve original model; install two pinned SafeTensors candidates into separate exported TorchScript bundles. A dedicated capability registry drives API validation and UI; explicit crop/plot/request identity prevents mixing results.
**Tech Stack:** Existing FastAPI/SQLAlchemy/Next.js/PyTorch; Transformers/timm/SafeTensors for reproducible conversion only, not remote code.
**Spec:** `docs/superpowers/specs/2026-11-17-agrodoctor-multicrop-design.md` (user approved).

## Global constraints

- Existing dirty `fix/audit-remediation` branch is preserved; snapshot saved outside repository. Work in place; do not commit unrelated existing changes or create a worktree containing only old committed source.
- Old model binary/card/results and historical cases remain untouched. Additional models are separate, pinned and attributed.
- Only actual disease-enabled labels count as support; no healthy-only crop advertised as disease screening; no fabricated field metrics or validated OOD claims.
- Isolated DB/storage and ports 3300/8300; leave current 3000/8000 services alone.
- Plan execution is authorized by the user's “Approve and implement this design”; settle routine implementation choices without another permission round.

## Review focus

1. Selected crop versus plot ownership/crop mismatch: reject without saving.
2. Upload A followed by drop/crop/plot B: no old result displayed in new context.
3. Missing/corrupt artifact/nonfinite logits: unavailable/abstention, no fabricated result.
4. Case list loading/error/plot changes and page-two mutations: no render loop or mixed history.
5. Legacy cases and images/EXIF/transparent/large/corrupt inputs: stable readback and useful errors.

## Task 1: Pin and verify model bundles and capability registry

Files: create `apps/api/app/doctor_models.py`, `apps/api/tests/test_doctor_models.py`, `scripts/install_doctor_models.py`, `ml/doctor/requirements-export.txt`; separate `ml/artifacts/multicrop/*` ignored binaries.
Interfaces: `DoctorRegistry(root=None).capabilities()->dict`, `.card(crop='tomato')->dict`, `.infer(image,crop)->dict`; `normalize_crop(str)->str`; canonical model/crop mappings. Per-crop capability includes id, bilingual name, model_id, labels, available, limitations. Result preserves existing classification/model/advice/status envelope plus crop/rejection reason.
- [x] Write tests: exact 12 disease-enabled crops, excluded healthy-only groups, missing/corrupt artifact, finite output, mismatched global top crop, preprocessing and single-flight cache. Observe RED.
- [x] Implement registry using known TorchScript architecture outputs and metadata; quality gate; conservative uncalibrated threshold, no crop-conditioned score inflation.
- [x] Install conversion dependencies in local environment, download fixed SafeTensors revisions/hashes, convert wrappers and verify parity/output shape with deterministic tensors. Preserve source metadata and reported metrics as external.
- [x] Verify new tests plus actual two-model inference controls; record upstream limitations and artifact receipts.

## Task 2: API/plot/case integration

Files: `apps/api/app/main.py`, `schemas.py`, `tests/test_doctor_api.py`, `contracts/openapi/schema.json`.
Interfaces: GET `/doctor/capabilities`; current model accepts crop; POST cases declared crop defaults from owned plot, validates exact match; crop catalog shared by plot validation; complete case image/crop/plot identity response.
- [x] HTTP RED tests: catalog, non-tomato plot creation, invalid/null crop, foreign plot, mismatched crop, missing model, quality failure, unsupported file, legacy detail with image/notes.
- [x] Implement before-image-read validation, robust decoded-image handling/EXIF/alpha, model invocation and failure cleanup; preserve legacy snapshots and per-crop generic advice.
- [x] Verify targeted and full API suites in per-run isolation; regenerate contract.

## Task 3: Crop-aware frontend and upload identity

Files: create `apps/web/src/components/doctor-studio.tsx`; modify `workspace.tsx`, `types.ts`; add browser regressions in `e2e/doctor.spec.ts`.
Interfaces: DoctorStudio consumes plot/plots/farms, capabilities query, mutation callback and plot setter; Result/detail show stored crop/model/image; plot creation supports catalog crop.
- [x] Browser RED tests: actual capability-driven selector, create/select potato/maize/rice plot, mismatched crop disables submit, delayed upload/drop/plot switch cannot display stale result.
- [x] Extract focused DoctorStudio/DoctorResult/CaseDetail components; disable all file paths while pending, abort/discard obsolete response generations, crop-aware bilingual copy/condition limits and unavailable states.
- [x] Replace unstable case accumulator with plot-keyed infinite query; shared older-history control and accurate dashboard totals; safe image blob cleanup and correctly ordered feedback.
- [x] Verify typecheck/component/browser regressions including no update-depth errors and legacy routes.

## Task 4: Final integration and review

Files: `docs/status.md`, `docs/model_card.md`, README, new `docs/agrodoctor-multicrop.md`; ledger at `docs/superpowers/plans/2026-11-17-agrodoctor-multicrop-progress.md`.
- [x] Run full API/unit/typecheck/lint/build/E2E; distinguish pre-existing market-action/map failures from new scope and don't weaken checks to hide them.
- [x] Actual non-tomato images and synthetic controls through local API; preserve licenses and report small smoke observations separately from accuracy.
- [x] Fresh independent review of changes against approved spec; fix consequential findings with RED/GREEN evidence.
- [x] Put the updated project in a running local session without disturbing existing original checkout processes. Deliver exact URL, supported crops, verification and model limitations.

## Execution ledger

No source commit is automatically made: preserve pre-existing dirty work and review the isolated change set against the snapshot. This departs from generic skill commit steps because committing this tree would mix the user's unrelated Cursor changes into the feature.

Completion qualification: all scoped implementation/verification steps executed. Full E2E was run, not claimed fully green:9pass/1pre-existing market comparison action duplication. Docker/hosted image execution is unavailable here; only configuration and shallow-container constructor were checked. No production or field-validation claim.
