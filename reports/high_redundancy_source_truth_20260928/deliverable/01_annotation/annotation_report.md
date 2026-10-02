# Source-level annotation outcome

Reviewed **298 frames** (149 V, 149 T) in 20 candidate moments. They belong to four batch events. Visual fixed-site identity can be tracked in all 20 moments at some viewpoints, but prefire/residual states and uncertain cross-UAV clock alignment limit burning-source inference. B3 and B4 are two independent multi-source events, each sampled five times.

| 批次 | 物理事件数 | 站点时刻数 | >=4 机站点 | >=6 机站点 | 精确点时刻 |
| --- | --- | --- | --- | --- | --- |
| B1 | 1 | 5 | 5 | 5 | 1 |
| B2 | 1 | 5 | 5 | 5 | 1 |
| B3 | 1 | 10 | 10 | 7 | 1 |
| B4 | 1 | 10 | 9 | 6 | 1 |


Adjudicated V site-support source–moment counts: >=3: 29, >=4: 29, >=5: 27, >=6: 23. For **active flame state** alone: >=3: 13, >=4: 13, >=5: 13, >=6: 11. These source–moment rows are correlated within four events.

The final two multi-source test moments had 34 same-agent second-pass frame reviews. Site-presence agreement 88.2%; visibility agreement 70.6%; source-count agreement 88.2%. Disagreements are downgraded conservatively in `02_identity/identity_truth_adjudicated.csv`. No independent second annotator or second point placement exists.

Point annotations: 42 manual V flame-base proxies across six moment/source groups, with 6 source groups and **0 exact ground-contact marks**. Thermal bright regions remain source-identity observations, not point equivalents.

Physical ID checks: B3_N/B3_S expanded across five moments using fixed pile positions; an image-background SIFT homography between B3_M02 UAV02 and UAV05 had 73 inliers and revealed a left/right reversal in UAV05, corrected before geometry scoring. UAV08's background site was too occluded for an N point. B4 road/tree piles are traceable around the curved road and tree canopy; UAV05's second V point was removed after review.
