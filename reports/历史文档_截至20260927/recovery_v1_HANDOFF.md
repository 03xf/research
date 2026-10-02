# DJI recovery_v1 handoff

This directory is a new server-side recovery workspace. Historical datasets,
weights, labels, and state files are unchanged.

## Current state

- Source: `datasets_round56_deconflicted_dev_v2`
- Derived diagnostic dataset: `dataset_diagnostic_v1`
- V train: 335 included, 69 empty-label records quarantined
- T train: 415 included, 18 empty-label records quarantined
- V validation: 61 images, 42 smoke and 23 flame instances
- T validation: 66 images, 70 hotspot instances
- Independent review queue: 214 records
- Formal training: locked until review decisions are complete
- Absolute visual localization: unavailable because Matrice 4T calibration parameters are unavailable

## Files

- `sample_ledger.json`: source, timestamp, session, hash, split, and review state
- `review_queue.json`: priority records for full-image adjudication
- `review_decisions.json`: append-only decision store for the review UI
- `preflight.json`: dataset construction and provenance checks
- `lrf/lrf_event_audit.json`: photo-record versus capture-group audit
- `status_current.json`: current machine-readable stage and blockers

## Review UI

The server binds only to `127.0.0.1:8780`. From a local PowerShell window:

```powershell
ssh -N -L 18780:127.0.0.1:8780 -p 1021 member@@research_server
```

Open `http://127.0.0.1:18780/`. Review the priority queue first. Select the
class, draw every visible `smoke`, `flame`, or `hotspot` box, and save. If the
image has no target, leave it empty and save. A non-empty label is recorded as
`approved_complete`; an empty label is recorded as `confirmed_negative`. The UI
writes only `review_decisions.json` and `review_history.jsonl`.

## Training gate

Do not start formal 100-epoch training until:

1. Every quarantined empty label and every partial patch has a decision.
2. Positive decisions contain complete boxes for all visible targets.
3. Negative decisions contain no boxes.
4. Development validation decisions are independently reviewed.
5. A new derived dataset is built from the decisions and passes absolute-path,
   image-label, class, bounds, split, and hash checks.

The 3-epoch V/T runs under `runs/V_smoke3_wandboff` and
`runs/T_smoke3_wandboff` only prove that the locked training path works. They
are diagnostic results and do not pass the detection gate.
