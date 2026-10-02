# Temporal anchor accuracy

Tests trailing image-space median against manual source points; reports point error, not only jitter.

Run: `python experiment.py` from this directory. Inputs are the read-only `../input_snapshot` plus, for H/L, explicitly named server read-only data. `results.csv` uses the shared metric schema. `failures.csv` records interpretation limits.
