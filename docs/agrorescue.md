# AgroRescue decision planner

Open `/en/agrorescue` or `/bn/agrorescue` inside the existing workspace. Select an owned plot, enter available harvested kilograms, confirm readiness, and compare up to six selling options. Each option uses an owned saved market quote or an explicitly entered price, plus declared transport, handling and fees.

For 100 kg, an entered offer of BDT 40/kg with BDT 100 transport leaves BDT 3,900; BDT 45/kg with BDT 800 transport leaves BDT 3,700. These are proceeds after entered costs, not profit, a price forecast or guaranteed buyers. Missing transport remains unknown; it is never silently zero. A question can show the transport cost at which a competing option would break even. Ties, nonpositive proceeds and unknown/not-ready crop status do not produce a unique positive recommendation.

## Evidence and method

The implementation is an explainable symbolic constraint planner, `symbolic_constraint_planner_v1`. It does not train a new model or claim to predict future prices, shelf life or losses. Existing AgroDoctor inference remains separate and research-only. The planner reads narrow summaries of the latest owned plot screening and saved weather: no photo copies or symptom/private-note text are embedded in plans.

Weather refresh is an explicit user action through the existing weather API. LIVE uses consented farm coordinates; DEMO is visibly simulated. Failed live refreshes are recorded against existing cached weather; there is no automatic substitution of demo weather. Missing, unknown, stale, expired and failed-refresh context remains visible. Rainfall is not converted into flood probability, harvest loss or a road-closure prediction.

Saved quote prices must match the plot crop and kilograms, with matching saved price type/grade. Quote dates older than three UTC calendar days, future dates and unknown dates require explicit farmer confirmation for comparison; that confirmation remains self-reported. Manual quotes are entered assumptions. No competitor listing, cart or unconfirmed interest is treated as buyer demand. Mixed and simulated sources remain labelled.

## Holding illustration

The optional hold scenario requires farmer-entered future price, assumed loss percentage, suitable storage confirmation and total holding plus later selling costs. The API field `storage_cost_bdt` means that total: storage + later delivery/transport + handling + fees. It is not estimated by the system. A hypothetical hold outcome is displayed separately; the recommended option compares eligible sell-now choices only. No automatic harvest, sale, discount, buyer contact, payment or chemical recommendation occurs.

## Persistence and API

- POST `/api/v1/rescue/plans`: validate owned plot/quotes, calculate and save immutable snapshot; update the plot's single rescue action.
- GET `/api/v1/rescue/plans?plot_id=...`: latest 20 owned snapshots.
- GET `/api/v1/rescue/plans/{id}`: owned snapshot, explicitly not refreshed advice.
- DELETE `/api/v1/rescue/plans/{id}`: remove owned plan and linked rescue action.

Uses existing shared `Record` documents; no destructive migration or new table. Plans participate in existing account export, account deletion and plot/farm deletion. Deleting a source does not silently rewrite a saved plan's narrow historical evidence; delete the plan to remove its snapshot. A new plan uses current evidence. The page resets results after edits or plot/account changes and distinguishes opened history from newly calculated results.

## Marketplace images

Crop images are local illustrative fallbacks. Uploaded seller photos with both dimensions at least 32 pixels take precedence; missing, broken or tiny placeholder uploads fall back without changing stored bytes. Unsupported/ambiguous names retain a neutral placeholder. Fallback images show their illustrative status and credits; they are not proof of the seller's stock, freshness, variety or grade. See `docs/crop-images.md` and `/crops/credits.html` for individual sources and licenses.

## Limits

No field, economic, food-safety or agronomist validation is claimed. There is no learned profit/price/spoilage predictor, automatic demand matching, live courier verification or verified buyer commitment. English/Bangla copy and source policies need local expert/user evaluation before field claims. Production security, cloud hosting and load validation remain separate work. The competition novelty is the integrated evidence and decision workflow; no world-first or measured loss-reduction claim is made.
