# SDD ledger — plan: docs/superpowers/plans/2026-11-17-agrodoctor-multicrop.md

Approved spec: docs/superpowers/specs/2026-11-17-agrodoctor-multicrop-design.md.
Execution: native in existing feature branch, preserving full uncommitted source snapshot outside repo. No automatic commit/reset or extra worktree.
Pre-flight shared interfaces: Registry produces canonical crop catalog and result envelope used by API and UI; API validates plot crop and snapshots identity; UI never invents model availability.
Baseline: recent re-audit 28 API/18 web tests/typecheck/build passed; E2E 3 pass/1 pre-existing market-action failure. Fresh baselines will be captured with task tests.
Ruling: user approved implementation, so no redundant plan/execution confirmation. Model candidates are converted from pinned SafeTensors via known architectures; no downloaded source execution.
Task 1: complete —10 model tests pass, including source pinning, single-flight and preprocessing; both pinned exports passed3 native/export controls and reload parity(max error0). Runtime all12 crop groups available.
Task 2: complete — full API46 passed. Crop ownership/mismatch before decode, source snapshots, missing-photo detail, EXIF/alpha/animation, failed-write rollback; readiness now503 for unavailable active bundles. Original legacy results preserved.
Task 3: complete — extracted DoctorStudio/Result/CaseDetail; six browser regressions pass including first-plot readiness, pending drop blocking, stale upload response, matching potato/maize/rice plot creation, old-page pagination/plot switching, photo download/missing-photo detail and newest feedback. Actual English desktop rice result and Bengali390px layout inspected, no page errors/document overflow.
Task 4: complete for the approved local scope —46 API/18 web unit tests passed; typecheck/build passed; lint0errors/9warnings. Full E2E9passed/1pre-existing duplicate market-action failure. New source diff check clean. Upstream source/artifact hashes and export parity checked, real HTTP potato/maize/rice/control observations recorded. Independent review findings corrected and verified. Project remains running8300/3300; original3000/8000 untouched. Docker unavailable; new hosted build wiring not runtime/cloud verified. No commit/merge/push of the user's dirty tree.

Ruling: use long-running exec sessions for services after a background Start-Process launch was auto-review rejected. Only the prior audit dev server in this same checkout was stopped to release Next dev lock.

Review fixes RED→GREEN: active-model readiness returned200incorrectly before fix; shallow/container path raisedIndexError before fix; delayed createPlot response overrode a later selected plot before fix. All now covered and verified. Corrupt-binary regression retains full valid source metadata so it actually reaches torch.jit.load.
Ruling: adding model packaging/readiness wiring is necessary for the existing Compose/deploy layout. Model conversion runs in a separate hosted build stage; local Compose mounts pre-installed bundles. Container runtime execution remains unverified because Docker is unavailable.

Final regression: initial no-plot render allowed selecting a file which was cleared on plot load. New photo controls wait for owned plot/crop/model readiness; test was RED then GREEN. Existing journey now waits for the visible choose-photo control to be enabled before setting a file, then reaches the unchanged market duplicate-action failure.
