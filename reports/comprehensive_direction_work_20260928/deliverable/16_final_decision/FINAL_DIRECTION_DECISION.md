# FINAL DIRECTION DECISION

## Primary direction

**No validated primary is selected.** The provisional highest-priority existing-data validation hypothesis is **D: state-constrained thermal active-fire source-observation recovery**. It has a measurable complementarity signal (13/52 old T-only matched source marks; 9/32 active moments with T hit/V miss; three new reviewed active centers with V miss/T hit) and explicit residual/hot-background failures. Current data do not support a successful state gate, independent hot-background test, or downstream same-case localization gain. D becomes primary only if a fixed gate improves held-event active source availability at a matched false-recovery rate and does not worsen independently referenced localization where available.

## Backup direction

**A: physical ground-burning-source anchor estimation.** A2 has cross-batch pixel evidence on B3/B4 matched points. It remains backup because only two events have point labels, B1/B2 contact points are missing, and the B3 North downstream case shows pixel improvement can fail to improve geolocation.

## Third option

**Relative H/R: cross-UAV same-source association and topology.** B3 has one manually confirmed two-source instant with strong conditional separation. B4 and 5–9 UAV newly staged frames are not yet independently labeled. Elevate only after independent multi-time identity review and clock validation.

## Rejected/deferred directions

- B temporal point smoothing as a standalone paper: only within-clip image-space signal, no motion compensation/physical accuracy.
- C fixed global SIFT RGB-T mapping: 19/99 background-supported probes and no source mapping truth.
- E standalone state classifier: rare states are clip-confounded.
- F/G learned correction/reliability on current labels: three matched Gold sites and stable-but-wrong counterexample.
- I mode boresight: optical axis not measured and mode/site confounded.
- J free SfM as absolute location: B4 counterexample; background connectivity is not accuracy.
- L/M smoke/domain/small early smoke: leaked old split, thesis overlap, no ignition-onset truth.
- N/O joint graph and consensus-supervised learning: no verified graph or certified high-support Silver labels.
- Q synchronization as a paper: no physical clock truth or validated downstream effect.

## Minimum next experiment

Review the 298 staged V/T frames with independent annotators, then run event-level LOUO and held-out source projection on any moment with at least four verified same-source UAV views. In parallel, search B1/B2 for a second independent hot-background event; freeze a D threshold before testing. Stop O if no >=4-view source instant survives manual review, stop D if net active recovery vanishes at matched false-recovery rate, and stop A if held-event anchor improvement does not improve the same-case physical location.

## Paper contributions only if gates pass

1. A source/state annotation protocol that separates Candidate, Manual, Silver, and Gold with event-disjoint tests.
2. A method targeted to the surviving measured gap (state-aware net thermal recovery, or ground contact anchor, or independent relative association).
3. Cross-event source-level and downstream physical-location evaluation, including stable shared-bias failures.

These are conditional plans, not claims that current results are submission-ready.
