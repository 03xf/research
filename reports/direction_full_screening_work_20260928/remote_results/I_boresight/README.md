# Mode-conditioned angular residual

Uses accepted LRF observations and leave-session-out offsets; measures gimbal/laser bearing, not optical axis.

Run: `python experiment.py` from this directory. Inputs are the read-only `../input_snapshot` plus, for H/L, explicitly named server read-only data. `results.csv` uses the shared metric schema. `failures.csv` records interpretation limits.
