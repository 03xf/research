# DJI recovery_v1 current state

Updated 2026-09-25. Authoritative workspace: `@recovery/`.

- The 214-image data repair and V/T preflight are complete. Twelve E1/E2 controlled trainings and E0 historical reevaluations are recorded in `comparison_seed0_seed1_seed2_v1.json`.
- Two historically exposed confirmation sessions were reviewed every 10 seconds: 194 V/T pairs. Frozen decisions SHA256: `9e11c2e06bbc5290e64c5fdc60f01b9840bb52e6b3293e2fee9ed63ca38072e5`.
- E2 seed-0 V/T weights and class thresholds were frozen before confirmation. The one confirmation run is complete at `evaluations/confirmation_frozen_v1/result.json`; smoke, flame and hotspot all fail the P/R/AP50 gate. No threshold tuning on confirmation was performed.
- Four 30-second, 5 Hz development clips have improved provisional ByteTrack outputs in `tracking_v2/`. Thermal tracks now exist, but true identity switches and physical T/V correspondence remain unverified.
- `localization_confirmation_v1/` contains reviewed boxes and 176 image-space flame lower-midpoint candidates. They are proxies, not confirmed ground contact points.
- Confirmed LRF-to-ground-burning-source groups: 0. Matrice 4T calibration is missing; absolute visual coordinates remain `unavailable`.

See `REPORT_20260925.md` for metrics, limits, artifacts and reproducibility. Machine-readable status: `status_current.json`.
