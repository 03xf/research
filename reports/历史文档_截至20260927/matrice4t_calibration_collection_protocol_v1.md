# Matrice 4T V/T calibration and localization data collection protocol

Status: **required before absolute visual localization**. No values in this protocol are substituted for measured camera parameters.

## Existing evidence

- DJI photo metadata includes GPS/RTK, aircraft and gimbal attitude, and LRF target coordinates in some captures.
- Project audit did not verify Matrice 4T V/T focal length, principal point, distortion, camera-to-gimbal/body transforms, or T/V extrinsics.
- The legacy H20T checkerboard PDF is not applicable to Matrice 4T.
- B4/F1 LRF reference repeatability is separately measured; its target point is not automatically the flame center.

## Required capture set

1. Record the exact drone, payload, V/T sensor identifiers, lens/zoom mode, image dimensions, distortion/dewarping setting, firmware version, and camera mode for every capture.
2. Capture a visible-light calibration board with known physical geometry at diverse image positions, roll/yaw/pitch views, and distances. Preserve original JPG/XMP and a board specification with measured dimensions.
3. Capture a thermal board or target pattern whose control points are genuinely visible in T. Do not reuse visible-image corner locations as thermal control points.
4. Capture common, stationary targets simultaneously in T and V to estimate their rigid transform. Keep raw T/V frames, original video PTS, photo timestamps, and the platform's sync records.
5. Place surveyed ground targets with independently measured WGS84/ENU coordinates. For each view record aircraft GPS/RTK, RTK quality and standard deviations, aircraft attitude, gimbal attitude, LRF distance and target coordinate, and original frame/photo timestamp.
6. Capture multiple separated camera positions and crossing view directions around each surveyed target. Maintain independent targets for fitting and validation; do not use all target coordinates to fit and then evaluate on the same points.
7. Repeat across relevant V zoom/focus and T modes. Parameters are mode-specific unless a mode-invariance test proves otherwise.

## Parameter package to produce

For each sensor and mode, save: image size, focal lengths, principal point, distortion model and coefficients, camera-to-gimbal transform, gimbal-to-body transform, sensor-to-sensor transform, timestamp offset/drift model, calibration target geometry, source capture IDs, fitting residuals, held-out reprojection error, and covariance/uncertainty where supported. Include coordinate-frame direction, handedness, units, rotation order, and geodetic reference definition.

## Acceptance before absolute localization

- Reprojection and independent surveyed-point errors are computed on held-out captures and reported by range/view angle/RTK state.
- The camera frame and gimbal/body frame composition reproduces known target directions; T/V reprojections agree on common targets within a declared tolerance established from held-out data.
- Packet/frame time alignment is measured, rather than inferred solely from nominal FPS.
- Geometry code refuses to run if any required parameter is `unavailable`, mode mismatched, or outside its calibration range.
- Single-view LRF distance is associated with the same physical object as the detection before it is used as a range constraint.
- Multi-view intersection reports baseline, ray angle, condition number, residual and reprojection error; ill-conditioned geometry yields a quality flag rather than an apparently precise coordinate.

Until this package exists, the project's valid localization outputs are image-plane center/track motion, T/V temporal candidates, grouped LRF reference analysis, and explicit `unavailable` absolute coordinates.
