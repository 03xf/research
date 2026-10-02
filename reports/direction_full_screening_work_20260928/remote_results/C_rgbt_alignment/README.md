# RGB-T registration viability

Audits SIFT homography inlier support over 99 samples and across recordings; source mapping truth is still missing.

Run: `python experiment.py` from this directory. Inputs are the read-only `../input_snapshot` plus, for H/L, explicitly named server read-only data. `results.csv` uses the shared metric schema. `failures.csv` records interpretation limits.
