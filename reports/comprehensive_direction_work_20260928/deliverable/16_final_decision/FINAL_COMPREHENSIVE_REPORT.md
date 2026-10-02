# FINAL COMPREHENSIVE REPORT

## 1. What the data uniquely contain

The asset is not simply “many videos”. The formal set has 34 V, 34 T, and 35 S streams across B1–B4; 143 fixed 30-second bins were inventoried. Recomputed **distinct-aircraft** V/T opportunities are shown in `01_data_support/uav_opportunity_summary.csv`. Earlier batch bins with >=5 streams were checked again after deduplicating by UAV. The new first-pass sample selected 20 candidate moments (five per batch), each with 5–9 UAVs, and extracted 149 V plus 149 T images (298 frames total). It has still not established which UAVs see the same physical source. In the previous manual benchmark, 50 moments across five short clips have active/residual/hot-background labels and 74 V/72 T source marks; a separate finalist review inspected 59 center frames. These counts overlap in time scope and must not be added as independent samples. The old 2,401 V/T pairs across 42 groups/26 sessions remain Candidate. The LRF review has 17 accepted observation rows, but many repeat sites; only three sites link to the multi-UAV video seed across two events. B1–B4 background graphs exist, but graph connectivity does not certify source geometry.

## 2. What is missing

Gold: few independent linked physical fire sites; B2 is pre-fire pile and B4 repeated LRF target has no independent cross-video source association. Manual source points: concentrated in five old clips, plus center-frame review that is not equivalent to ground-contact points on every view. State: residual/hot-background examples are event-confounded; the second independent hot-background event was not found in prior review. Cross-UAV identity: only one B3 double-source instant is confirmed; B4 remains provisional. Synchronization: stream creation tags provide extraction opportunities but not clock offset/drift. Manual review of new 5–9-UAV source points is pending. These gaps prevent event-independent train/dev/test for most candidate directions.

## 3. High-redundancy 5–9 UAV experiment

The staging sampled five bins per batch, yielding 20 Candidate moments and 298 frames: B1: 7,7,7,7,7, B2: 6,9,9,9,6, B3: 7,8,8,7,5, B4: 8,9,9,9,5 UAVs per selected moment. Contact sheets and an annotation manifest are ready. Exact same-source labels, visible contact points, source state, and independent time alignment remain blank by design. On previously verified data, only 2-of-3 LOUO and three-UAV consensus are available. At >=4 UAV verified source-moment count is zero. Therefore 5/6/9-view LOUO error, held-out projection, subset disagreement, and association-margin curves are **not estimable** from staged views before independent annotation. More UAVs may reduce random noise, but the B3_N example shows they can preserve shared error. See support curve and opportunity summary.

## 4. A–R experimental signals

The evidence table includes every direction. The clearest current gaps are: D has T-only active-source observations but also residual/hot false triggers; A2 improves selected image pixels but not B3 North geolocation; H/R separates sources conditionally in one B3 instant but has no second confirmed event; F/G has a stable-but-wrong B3 North case; P cannot yet explain it. C, L, M, N, O, Q lack the source-level or independent truth needed for a claim. K localizes the bottleneck in one case only. See `experimental_signal_matrix.csv` and the direction-specific notes.

## 5. A–R data support

`direction_data_support.csv` is the main selection table. We defined **strong** as independently labeled support across at least three events with train/dev/test separated by event; **moderate** requires at least two independent events with a genuine held-out test and enough truth for the direction; **weak** means a measured signal exists but event-level scope/truth fails that gate; **unsupported** means no independent task truth or valid test exists. None of A–R reaches strong or moderate. A, B, F, G, J, K, P, R remain weak exploratory; C, E, H, I, L, M, N, O, Q are unsupported as complete papers on the current evidence. D has real active-recovery signal but is weak overall because difficult negative states and the deployment gate are not event-independent. 20 staged moments do not change these levels until reviewed.

## 6. Shared systematic error

B3_N is 13.283 m from its accepted LRF under nominal geometry while ray residual is 1.185 m; C1–C4 remain 11.535–12.676 m away. C1 LOUO outputs cluster within 0.5 m but retain the bias. The common yaw/pitch/focal/GPS one-factor sweep is in `09_calibration/systematic_bias_sweep.csv`; it tests whether a simple global shift consistently explains B1_F1 and B3 N/S. With three sites/two events, any apparent pooled optimum is post hoc and not identifiable. No source data establish whether boresight, camera model, zoom conversion, GPS/altitude, time alignment, source-pixel semantics, or LRF targeting caused N. Per-mode/drone effects are confounded; no causal explanation has been proven. The appropriate next reference is a surveyed optical-axis target plus synchronized repeated manual source marks.

## 7. Oracle bottleneck

Current dataset-level bottleneck is **independent truth and correspondence**, then per-view physical-source visibility/anchor, then absolute geometry/calibration/synchronization. Scene-specific: B3 North remains wrong with oracle source/identity so geometry dominates; B3 South has a good manual geometric point but automatic V has only one valid view so observation availability dominates. H correctness is only one-event conditional; T same-case identity is missing. No model-capacity claim is supported. The oracle decomposition does not yet provide enough complete events to estimate population bottleneck proportions.

## 8. Surviving directions

**Strong Candidate:** none.

**Moderate Candidate:** none.

**Exploratory:** D (priority next validation, not a validated paper); A (backup physical-anchor question); H/R (relative same-source topology, only after independent B4/manual IDs); F/G/P (diagnose and calibrate shared absolute bias); K as an experiment framework. These are questions, not claims.

**Rejected for current evidence/protocol:** B as a standalone temporal model; fixed SIFT as reusable source alignment (C); standalone state classifier E; mode calibration I; free SfM as geolocation and background self-calibration as an absolute solution (J); smoke domain-generalization claim under leaked split and unsupported early-smoke direction (L/M); learned joint graph N; consensus-supervised source learning O before verified high-support labels; clock-offset paper Q without physical sync truth. These are current-scope decisions, not judgments that the broad topics are impossible.

## 9. Head-to-head of exploratory candidates

| Candidate | Data/truth | Signal | Novelty boundary | Main risk |
|---|---|---|---|---|
| D: state-aware thermal recovery | 50 old manual moments, 59 separate review centers; difficult negatives event-confounded | 13/52 old T-only source points; new 3/25 center misses complemented | Must go beyond ordinary RGB-T/temporal detection to net active-source recovery | No held-out state gate or second hot-background event |
| A: ground source anchor | 33 V + 44 T matched active points, B3/B4; 3 linked Gold sites overall | A2 improves matched pixels on B3/B4 | Ground contact, uncertainty, and same-case physical location, beyond smoke-source box prediction | Pixel gain failed to improve B3 North location |
| H/R: association/relative geometry | One B3 confirmed dual-source moment; B4 provisional | 6/6 conditional held-out marks and clear B3 geometric margin | Independent identity, rejection, multi-event relative topology | No second event with verified UAV-to-source IDs |
| P/F/G: systematic calibration/reliability | 3 linked LRF sites / 2 events | Stable shared error defeats residual/spread | External calibration indicator and held-site risk control | Cause not identifiable and sample too small |

## 10. Final direction

**Validated primary: none.** If continuing without new collection, the highest-value *validation hypothesis* is D, because it has a cross-batch observation-complementarity signal and a concrete counterexample; it must pass a fixed false-recovery/held-event test before becoming a paper. Backup is A, restricted to manually visible ground-contact points and same-case LRF downstream tests. Third is relative H/R, contingent on independently reviewed B4 identities and time synchronization. If those gates cannot be met from existing footage, do not force a paper direction from this dataset. The unique research asset is multi-UAV visible/thermal/telemetry redundancy combined with a few LRF references; the strongest safe contribution today is a rigorous dataset/benchmark audit and failure analysis, not a claimed new algorithm.
