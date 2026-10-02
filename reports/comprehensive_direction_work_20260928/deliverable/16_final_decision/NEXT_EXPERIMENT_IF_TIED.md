# Minimum tie-break experiment using existing data

1. Human-review the staged 20 moments in `02_high_redundancy_multiview/annotation_manifest.csv`; first determine source count, whether the exact ground contact is visible, per-view pixels, source state, and physical ID. Do not infer a point through occlusion. Check cross-UAV timing against repeated visible events before triangulation.
2. Prioritize moments with >=5 views in at least two independent physical events, including one multi-source event. Ask a second reviewer for identity/point agreement on the held-out evaluation moments.
3. Run LOUO by support 2/3/4/5/6+ using held-out manual pixels and accepted LRF only where physical correspondence is independently verified. Report per-event curves; never pool frames as independent events.
4. In parallel, seek a second independent hot-background/residual event in B1/B2 and manually verify T false-recovery versus active source. Freeze thresholds before scoring held-out sessions.
5. For B3_N, obtain a surveyed optical-axis target or an independent camera/gimbal calibration and synchronize source frames. Re-run the same source points under that calibration; do not tune to N and report S/B1 as a test if parameters are shared.

**Decision gate:** if no >=4-UAV instant has independently reviewed same-source marks, stop consensus-supervised learning. If D cannot add active source observations at a fixed false-recovery rate on an independent event, stop D and test A only on hand-marked B1/B2 contact points with same-case LRF evaluation. H/R remains exploratory until B4 IDs receive an independent physical mapping.
