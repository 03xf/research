# B1-B3 V/T candidate dataset v1

This directory contains uniformly sampled paired V/T frames from B1-B3. The frames are candidates only: no flame/hotspot label is considered ground truth until human review writes an annotation ledger. B4 is excluded and reserved for final evaluation.

- `dataset_manifest.json`: provenance, video groups, split and counts
- `video_groups.json`: one row per complete V/T recording group
- `candidate_frames.jsonl`: one row per paired timestamp candidate
- `images/V|T/{train,dev}`: extracted native-resolution frames
