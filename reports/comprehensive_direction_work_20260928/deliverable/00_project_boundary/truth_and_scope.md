# Project boundary and truth levels

## Truth levels

- **Gold:** independent accepted LRF/physical measurement. There are 17 accepted observation rows in the reviewed LRF table, but repeated images target the same sites. B2 is a pre-fire pile. For the manually marked multi-UAV video seeds, only B1_F1 and B3_N/S have usable correspondence (three fire-source sites across two events). B4 LRF rows are one UAV repeatedly targeting one physical point and are not linked to the two-video-source scene by independent identity evidence.
- **Manual:** human-reviewed source point, state, or identity. Provenance and scope vary by benchmark; a manual image mark is not automatically a physical coordinate.
- **Silver:** geometry-derived reference from independent UAV support. It may support relative evaluation after LOUO; it is not absolute Gold. The prior audit found stable-but-wrong B3_N and therefore does not certify large-scale Silver-A/B.
- **Candidate:** any unreviewed V/T pair, 30-second overlap bin, detector proposal, or new frame in this directory. It is never counted as truth.

Every new contact sheet and annotation row is marked Candidate/pending_manual_review. Stream overlap is an opportunity count. Creation timestamps are an approximate extraction clock and do not establish sensor synchronization.

## Prior thesis boundary

The prior comparison in `07_codex_full_screening/01_previous_work_boundary.md` covers Zhao Di (2025) and Xu Ruiqing (2026): both already cover smoke detection/domain adaptation, smoke-source regions, segmentation, and ORB-SLAM/multi-frame smoke localization. Repeating smoke backbones, teacher-student adaptation, or ordinary smoke SLAM is not a new contribution. This project can differ only with independently evaluated ground burning-source observations, fire-state-conditioned thermal recovery, or cross-UAV physical-source identity. The existing old smoke split has exact duplicate leakage and cannot be reused as reported.

## Anti-circularity

For LOUO at UAV i, build reference only from other UAVs; the held-out source pixel is used only for projection/error. Association labels must come from independent scene topology/manual review or physical references, not the association score under test. Temporal frames from one fire are one event. Do not describe internally consistent rays as absolute accuracy.
