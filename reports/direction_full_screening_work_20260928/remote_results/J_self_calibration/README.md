# Background self-calibration

Checks SfM graph connectivity/reprojection against the B4 absolute-reference counterexample.

Run: `python experiment.py` from this directory. Inputs are the read-only `../input_snapshot` plus, for H/L, explicitly named server read-only data. `results.csv` uses the shared metric schema. `failures.csv` records interpretation limits.
