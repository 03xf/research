# B — temporal source estimation

The previous trailing-median probe gives a modest within-clip pixel-point reduction. It does not compensate camera/gimbal motion and has no held-out physical-coordinate error. The new 20 moments are spatial opportunity samples, not verified repeated source tracks. Temporal jitter reduction must not be reported as physical accuracy. Do not train a temporal model before time synchronization and event-level point truth.
