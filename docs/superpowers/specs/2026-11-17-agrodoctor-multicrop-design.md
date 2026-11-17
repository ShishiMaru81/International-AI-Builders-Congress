# AgroDoctor genuine multi-crop screening design

This proposal addresses the user's request for actual disease inference beyond tomato, plus the related AgroDoctor edge cases. It is not a proposal to close every unrelated market, deployment or device issue in the previous audit.

## Current cause

The installed artifact declares only Tomato Early blight, Late blight and Healthy. The API rejects other crops; plot creation is typed as tomato-only; the crop control is disabled; upload/history/result copy assumes tomato. Changing the dropdown alone cannot expand the classifier.

## Recommended approach

Keep the original tomato research artifact and its historical results unchanged. Add separately identified, revision-pinned CPU research models with explicit provenance, checksums, preprocessing, class order and capability metadata. Screen only the crop/model combinations actually installed and tested. Existing tomato cases remain readable with their original model snapshots.

Candidate adapters:

- PlantVillage MobileNetV2 from `neghani/plantvillage-mobilenetv2`, revision `d33601185b32cf05b3942661b8d84ffb86dc48ec`. Published Apache-2.0 model metadata; SafeTensors; 38 labels across 14 crops. Only 11 crop groups contain a disease class: apple, cherry, maize, grape, orange, peach, bell pepper, potato, squash, strawberry and tomato. Blueberry, raspberry and soybean have only healthy-reference classes and must not be advertised as disease screening. Some supported crop groups lack a healthy class; disclose that limitation per crop.
- Rice EfficientNet-B0 from `Huyt/rice-leaf-disease-efficientnet-b0`, revision `a12e09fd765eda2b846836a965e951151a9125f7`. Published Apache-2.0 model metadata; SafeTensors; 17 rice condition labels. Attribute the author and dataset sources. Its rare-class and domain-shift limitations remain visible.

These are candidates, not already independently validated integrations. Admit each only after checking its artifact, architecture, labels, preprocessing and bounded inference controls. Publisher-reported metrics must be labelled external and never presented as newly measured AgroSphere field accuracy. Preserve applicable model/data attribution and terms; do not execute downloaded repository code or use untrusted pickle loaders. Load local pinned SafeTensors with known library architectures and remote code disabled.

My proposed default is the new multi-crop model for its 11 disease-enabled crop groups (including tomato), plus the separate rice model, once their local checks pass. Historical cases keep the original model snapshot; old tomato artifacts remain untouched. Do not silently switch to a different model with different label coverage during a failed request. The capability response must identify the exact active provider per crop and its current readiness. Model adoption can establish working research inference, not independently establish published accuracy or safe field deployment.

If a candidate fails the acceptance checks, leave that capability unavailable with the reason; do not replace outputs with fixtures. No paid API or remote image upload is needed. Unsupported photos/crops must not be forced through the tomato model.

## User flow and crop consistency

- Fetch a backend capability catalog rather than hardcoding a list in the browser.
- Show disease-enabled crops, available classes, model availability and limitations in English/Bangla. Default the crop from the selected plot. Provide a clear way to create/select a plot of another crop; do not silently relabel an existing plot or case.
- Verify owner, plot crop, declared request crop and selected model on the server. Missing/unsupported crop, unavailable model, mismatched plot/crop and changed context produce explicit safe responses.
- Keep broad multi-crop outputs unconditioned for mismatch checking; never renormalize a selected crop's labels to manufacture high confidence. Abstain on a predicted different crop, insufficient confidence, invalid/nonfinite output or failed image-quality gate. A crop-specific rice model cannot establish that an arbitrary image is rice: explicitly disclose that limit and test negative controls; do not claim a validated universal crop/OOD detector.
- Preserve submitted crop, plot identity and model snapshot on each result and report. Use generic, safe scouting advice and qualified human escalation without invented treatment/dosing.

## Related edge cases to fix

1. Freeze or invalidate every upload input path while a request is active, including drag/drop and camera. Tie responses to immutable request/photo/crop/plot identity; changing context must clear/cancel or discard the old result.
2. Fix the undefined-case pagination render loop, owner/plot-keyed loading and accumulation, truthful totals and older-history access so multi-crop cases cannot mix across plots.
3. Show the actual authorized saved photo, alternatives and correctly ordered saved notes, with a clear missing-file state. Preserve legacy tomato cases.
4. Validate file suffix and decoded format, corrupt/empty/oversized images, excessive pixels, EXIF orientation, transparency, low light, blur and supported dimensions. Failed model/storage writes must not leave misleading saved cases or dangling files/actions.
5. Validate unique class labels/crop mappings, digest, model availability, output shape and finite scores; cache initialization safely and bound inference concurrency. Missing/corrupt artifacts must not claim ready.
6. Keep source/capability selection consistent across reload, plot switches, edits, history, exports and source disclosures. Invalid/null crops must never poison persisted records. Avoid disrupting user data or the existing services on ports 3000/8000.

## Alternatives considered

- **Recommended: integrate pinned existing multi-crop research models.** Gives genuine inference now with manageable CPU models and honest limitations; requires additional runtime libraries, source notices and verification. This does not establish Bangladesh field performance.
- **Train and independently evaluate a new multi-crop model.** Offers more control over data/splits/crops but requires substantial permitted data, compute and annotation/evaluation work. It cannot be represented as complete by merely generating training code.
- **Dropdown/record support only.** Cheap but does not satisfy the user's clarified request for genuine additional-crop inference; therefore not selected.

## Acceptance and delivery

Use isolated databases and services for regressions, preserving the dirty working tree and historical artifacts. Add meaningful backend/component/browser checks for catalog-to-model consistency, at least two genuinely non-tomato inference paths, rice if its adapter passes, unsupported/mismatched crops, corrupt/missing model, bad inputs, request races, multi-plot history and legacy cases. Verify current API/UI/unit/typecheck/lint/build/E2E checks and document failures honestly. Record small model smoke controls separately from accuracy benchmarks. Do not claim every conceivable edge case or field robustness is solved.

Deliver working code, pinned installation/export instructions and provenance, revised status/model/capability documentation, passing relevant checks, a running local demonstration of the new checkout and a precise list of remaining model/research limitations. No publishing, competition submission, collaborator changes or destructive production-data operations are included.

## Source references

- [Multi-crop model card](https://huggingface.co/neghani/plantvillage-mobilenetv2)
- [Rice model card](https://huggingface.co/Huyt/rice-leaf-disease-efficientnet-b0)
