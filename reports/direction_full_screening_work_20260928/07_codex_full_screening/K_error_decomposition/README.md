# Oracle pipeline availability

Measures the same-case manual point/association geometry substitution and identifies three unsupported stages.

Run: `python experiment.py` from this directory. Inputs are the read-only `../input_snapshot` plus, for H/L, explicitly named server read-only data. `results.csv` uses the shared metric schema. `failures.csv` records interpretation limits.

The B3 same-frame five-level grid has two prerequisites: run `detect_b3_manual.py` with the server's `yolov8` environment, then `b3_oracle_grid.py` with `colmap_exp`. These write only into this directory. Finally run `experiment.py` to add their metrics to the common schema. The frozen E2 model's hash is checked before inference; its historical development exposure is preserved as a limitation.
