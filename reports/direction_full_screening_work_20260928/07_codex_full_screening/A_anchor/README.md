# Matched-box source anchor

Compares center, bottom, and a cross-batch median offset against manual source points. Conditional on an existing detection match.

Run: `python experiment.py` from this directory. Inputs are the read-only `../input_snapshot` plus, for H/L, explicitly named server read-only data. `results.csv` uses the shared metric schema. `failures.csv` records interpretation limits.
