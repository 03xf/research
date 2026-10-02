# DJI Matrice 4T 全量影像元数据与相机几何审计（2026-09-29）

## 1. 现有数据里到底有哪些相机几何参数？

原始数据树共 **52 张 JPG/JPEG、208 个 MP4、9 个 MRK、4 组 RTK/OBS/NAV/pbk**，没有独立的 SRT/S 文本文件；字幕嵌在 MP4。逐张读取了完整 EXIF、全部 XMP 包及 ExifTool 未知/私有标签，得到 9,371 个 ExifTool 键实例和 5,216 个原始/解析 XMP 值实例；每个字段及原值见 `all_metadata_keys_long.csv`、`all_xmp_values_long.csv`，字段覆盖率见 `all_xmp_keys.csv`。52 张原图均在 B1–B4；没有发现额外的原始 JPG。项目其他 JPG 属于导出/实验结果，不并入原始影像统计。审计结束后重新哈希 52 张原图，SHA-256 全部与首次读取一致，见 `source_integrity_check.csv`。

| 物理镜头（按相机序列号和原图 35 mm 等效焦距） | 原图 | 原图尺寸 | 原图实际/等效焦距 | 原图 DigitalZoomRatio | 相机序列号数 |
|---|---:|---|---|---|---:|
| 广角 Wide | 26 | 4032×3024 | 6.72 / 24 mm | 1、1.25、1.41、1.67、2.22、2.63 | 4 |
| 中长焦 MediumTele | 1 | 4032×3024 | 19.35 / 70 mm | 1.24 | 1 |
| 长焦 Tele | 0 | — | 原图中未见 168 mm 基础档；视频 V 有 45 帧符合 168 mm 基础档 | — | 0 |
| 热成像 Thermal | 25 | 1280×1024 | 12 / 52 mm | 1 | 3 |

`ImageSource=ZoomCamera` 的 17 张中，**16 张仍来自 24 mm 广角物理相机**，只有 1 张是 70 mm 中长焦。两台广角相机序列号同时出现在 `WideCamera` 和 `ZoomCamera` 图中。因此 `ImageSource` 是必须保留的采集模式标签，不能单独用来指定镜头；逐机账本见 `camera_lens_inventory.csv`、`physical_camera_ledger.csv`、`focal_zoom_inventory.csv`。24/70/168 mm 的镜头档位也与 [DJI Matrice 4 系列官方规格](https://enterprise.dji.com/matrice-4-series/specs)一致；热成像 JPG 自报 52 mm，官方规格约 53 mm，按各原图字段记账。

52 张都有相机/飞机序列号、图像尺寸、实际及等效焦距、DigitalZoomRatio、GPS、云台 yaw/pitch/roll、机体 yaw/pitch/roll、绝对/相对高度、文件名和 EXIF 时间。35 张有 `UTCAtExposure`、`RtkFlag` 和 `RtkStdLon/Lat/Hgt`；17 张 `ZoomCamera` 可见光照片没有这些 XMP 项。虽然没有题目列举的 `LaserMeasure*` 键名，**52 张全有实际的 DJI `LRFStatus=Normal`、`LRFTargetDistance/Lat/Lon/Alt/AbsAlt`**；测距值为 0.863–45.374 m。它们给出逐照片的激光目标记录，需按具体打点对象和高度基准使用，不能误判成“没有激光元数据”，也不能把目标坐标当相机内参。逐项可用性和边界见 `geometry_parameter_status.csv`。

按 **35 mm 等效焦距×图像宽度/36 mm** 的宽度约定，只能计算名义焦距：广角约 `fx=fy=2688 px`，唯一中长焦照片约 `7840 px`，热成像约 `1848.9 px`。若 DJI 的 35 mm 等效值按画面对角线定义，改用 **等效焦距×像素对角线/43.2666 mm**，则三者分别为 **2795.7、8154.1、1970.1 px**。实际焦距与等效焦距还能推得名义传感器对角线，但不能从原图判定 DJI 采用的等效口径、视频裁切及每个 zoom 的实际 K。`fy=fx` 也假定方形像素。这些数值**均不是厂家标定内参**。若再乘照片 zoom 得到有效焦距，只是“简单裁切并缩放”的条件估计，详见 `focal_zoom_inventory.csv`。

208 个 MP4 分为 `S=72、V=68、T=68`。每个文件已读取容器/流信息，并**逐帧遍历全部内嵌字幕约 2,979,760 条**，按连续焦距/zoom 状态压缩成 2,881 段。可见光 V 的 983,088 帧中，按 `focal_len/dzoom_ratio` 与 DJI 基础焦段相差不超过 2% 分类：**982,195 帧为 24 mm 广角、848 帧为 70 mm 中长焦、45 帧为 168 mm 长焦候选**，没有未分类状态。短暂的长焦候选出现在 B4 uav-03 的原 V 视频，字幕本身不含物理相机序列号，因此最终物理确认仍需设备记录。V 字幕给出**名义有效 35 mm 等效焦距与 zoom 状态**，仍不提供经标定的 fx/fy 或畸变。逐视频、逐状态、逐切换和物理镜头推断见 `video_file_inventory.csv`、`subtitle_full_file_inventory.csv`、`subtitle_full_state_inventory.csv`、`subtitle_state_segments.csv`、`video_full_focal_zoom_mapping.csv`、`video_lens_state_ledger.csv`。

## 2. 哪些参数其实已经存在，只是之前没有用？

**曝光事件和天线补偿已经在 MRK 中。** 29 条 MRK 事件均含照片序号、N/E/V 补偿列、曝光点经纬高及质量数值，其中 12 条有有效周数/周内时刻，17 条为 `[-522] / -259200` 哨兵时间。按 [DJI 对 MRK 字段的说明](https://enterprise-insights.dji.com/fr/blog/faq-des-solutions-geospatiales-dji-enterprise)，N/E/V 是天线相位中心至相机 CMOS 中心的毫米级补偿列，MRK 经纬高描述曝光时 CMOS 中心。**这是一种逐曝光的照片定位补偿，不能直接当作所有视频镜头的固定机体杆臂。** 有效事件匹配 18 张 JPG：10 张可见光图的 MRK 周内秒与 XMP `UTCAtExposure` 数值吻合到 1 µs 内；8 张配对热成像图晚 0.032–0.107 s。匹配图的 MRK 与 XMP 位置水平差中位约 0.0006 m、最大约 0.0102 m，高程差最大 0.002 m。照片 GPS 很可能已经是补偿后的 CMOS 位置，**不可再次无条件加 MRK N/E/V**。原始行、事件号、N/E/V 与匹配残差在 `mrk_exposure_events.csv`、`time_alignment_audit.csv`。

**激光目标记录原本就存在。** `LRFTargetDistance`、目标经纬度、`LRFTargetAlt` 与 `LRFTargetAbsAlt` 在每张原图中均可提取；20 对同事件 V/T 照片的 LRF 目标平面坐标最大相差约 0.092 m、距离最大相差 0.093 m。它们可用于复核拍摄时标记的目标位置/距离，但必须先区分哪个 LRF 点对应研究中的哪个火点、采用何种高度基准。原字段值逐张见 `all_image_metadata.csv` 和 `all_xmp_values_long.csv`。

**可见光视频的等效焦距与 zoom 已在 V 字幕中。** 当前 M0 用 `fx=fy=1280×focal_len/24`（1920×1080），等价于 `1920×focal_len/36` 的**宽度约定名义换算**；在全部 V 字幕状态下，`focal_len` 与各自 24/70/168 mm 基础焦段乘 zoom 对应。因此 M0 不再单独乘 `dzoom_ratio` 有数据依据，若再乘一次会重复放大。证据支持的是 `focal_len` 已包含 zoom，**不证明 `1920/36` 这一步是 DJI 视频真实的像素焦距换算**，更不证明主点、视频裁切或畸变已标定。原图可见光焦距和 zoom 也能按每个物理相机分别入账，不能把广角、中长焦、长焦、热成像共享一套 K。

17 张 `ZoomCamera` 可见光 JPG 没有自身 `UTCAtExposure`，但其中 12 张有同事件、同文件名前缀的 T 照片，后者有 UTC 曝光时间。用已验证成对图的 0.032–0.107 s 热成像滞后来推算 V 时刻，只能标成**近似**；剩余 5 张无配对 T，不能用秒级文件名替代精确曝光时刻。4 组 `.RTK/.OBS/.NAV` 保留 GNSS 原始观测/星历，可用于另行 PPK；RINEX 头部 `APPROX POSITION XYZ` 和 `ANTENNA: DELTA H/E/N` 在本批数据中均为零，占位值不是相机内参或已解算轨迹。

## 3. 哪些元数据存在冲突或时间对应错误？

**JPG 时间链：** 52 张 `DateTimeOriginal` 与文件名秒级时间全部一致；有 UTC 的 35 张在加 8 小时转换后，`UTCAtExposure` 比 EXIF/文件名晚 **16.391978–27.962307 s**（均值 21.348494 s）。MRK 有效周内秒与可见光 XMP 数值一致，因此该差异不能简单当作 UTC 时区问题，也不能把文件名时间作为精确曝光时刻。29 条 MRK 中的 17 条哨兵时间不具备绝对时标。照片均有对应 MRK 事件号，但与原始 V MP4 没有可证实的同帧关联：按容器创建时间和时长筛查，照片曝光 UTC 没有落入同机同批 V 视频时段；不得把“最近视频”冒充照片对应帧。每张图的文件名、EXIF、UTC、MRK、最近视频候选 PTS/时段间隔均在 `time_alignment_audit.csv`。

**MP4 时间链：** 全量字幕以每条字幕真实 PTS 对照墙钟时间，逐视频的“字幕墙钟 − 容器 `creation_time` − PTS”中位偏移介于 **−0.537 至 +1.027 s**，无超过 2 s 的视频。容器创建时间只有秒级，字幕墙钟才有毫秒级记录；跨通道比较应保留各自原始 PTS 和墙钟，不能用 MP4 文件名秒数替代精确帧时刻。逐视频首末字幕时间、PTS 与偏移范围见 `subtitle_full_file_inventory.csv`。

**PPK 观测覆盖例外：** B3 uav-08 的 MRK 第 3 号曝光为 GPS 周时 `2026-09-08 02:19:55.851125`，对应 OBS 的首条观测为 `02:20:56.600000`，曝光早了 **60.748875 s**。该曝光不能仅凭这份 OBS 获得同期 PPK 解；其余 11 条有效 MRK 事件处于各自 OBS 时间范围内。逐事件见 `mrk_obs_coverage.csv`，原 OBS 路径和头部见 `rtk_mrk_file_inventory.csv`。

**字幕通道冲突：** 67 组同时有 S/V 的录像全时段对照后，**36 组、373 个区间**的 S 与 V 焦距或 zoom 不同，按原始 MP4 PTS 对齐累计约 **8,618 s / 2.39 h**；开头/中间/结尾抽样原本只发现 17 组。由于两个文件的字幕墙钟与容器起点有至约 1 秒的偏移，极短过渡区间仍需墙钟复核，持续数分钟的冲突则明确。B3 的关键例子是：uav-04 标称 PTS 71 s 时，`S=52.7/1.00`、`V=53.8/2.24`；uav-09 标称 PTS 55 s 时，`S=52.7/1.00`、`V=54.7/2.28`。对应 T 也为 `52.7/1.00`。因此历史 V 记录 **53.8/2.24、54.7/2.28 得到同一时刻原 V 字幕支持**；此前只重读 S 而认定旧 V 记录冲突的结论应撤回。S 与 V 的字幕时间在这些点相近，但记录不同通道镜头状态。原视频路径、请求 PTS、帧号、字幕墙钟时间与完整字段原值见 `b3_channel_telemetry.csv`；全时段逐区间和逐录像统计见 `video_channel_state_conflicts_full.csv`、`video_channel_pair_summary_full.csv`，异常索引见 `anomalies.csv`。历史导出帧的**精确 PTS 仍未反查**，所以目前只能确认“标称 PTS 处 V 记录一致”，不能越界声称旧导出 JPG 的实际拍摄档位已经绝对证实。

另一类冲突是 17 张 `ImageSource=ZoomCamera` 中 16 张仍是广角物理相机；把 `ZoomCamera` 当成 70/168 mm 镜头会误分相机。17 张变焦可见光照片缺少 UTC/RTK 精度字段，说明同机不同采集模式的元数据格式不一致。所有异常行都带原文件路径、文件名、批次、无人机、原字段值与对照值，见 `anomalies.csv`。

激光值也需要有效性筛选：B1 uav-09 的 `DJI_20260907163440_0003_V/T.JPG` 均报 `LRFStatus=Normal`、距离 **0.863 m**，低于 [DJI 公布的 1 m 测距盲区](https://enterprise.dji.com/matrice-4-series/specs)。这条目标记录已保留，但在确认它是当前有效回波前不应作为定位真值。

## 4. 多视角定位真正还缺哪些参数，以及优先级？

| 优先级 | 参数/动作 | 本次判定 | 对 M0 的影响 |
|---|---|---|---|
| P0 | 精确原视频帧 PTS → **同通道 V/T 字幕** → 墙钟/GPS/姿态链 | 视频 PTS、字幕已有；历史导出帧 PTS 尚缺 | B3 的 S/V 混用已证明会换错镜头档；先修数据关联再评定位 |
| P0 | 每个物理可见光镜头、每个使用 zoom/分辨率状态的校准 fx/fy、cx/cy、畸变 | 直接校准值没有；名义 fx/fy 可计算，中心只能近似 | M0 的 `fx=fy=1280×focal_len/24` 是名义换算；`cx=960,cy=540` 与零畸变未获原始元数据证实 |
| P1 | 相机—云台固定旋转/平移和机体—云台完整姿态链 | 没有 | JPG/视频有云台和机体姿态；M0 只用 yaw/pitch，roll/固定外参仍未知 |
| P1 | 视频 GPS/RTK 参考点 → 各镜头光心的杆臂、高程基准 | 没有可直接用于视频的固定参数 | MRK 已有**照片曝光时**天线→CMOS 补偿和近似 CMOS 位置；不能据此把视频 GPS 直接设为所有镜头光心 |
| P2 | 逐镜头 zoom→校准内参映射 | 没有；zoom→**名义等效焦距**可计算 | 不得跨广角、中长焦、热成像共享 K，也不得默认同镜头所有 zoom 的 fx/fy 固定 |
| P2 | GNSS 原始观测的 PPK 解算及控制基准 | 原始输入已有，解算轨迹没有 | 4 组 RTK/OBS/NAV 不能直接代替内参；仍需测站数据、基准与解算质量检查 |

把本次原始字段与当前冻结的 M0 假设逐项对照：V 中 `focal_len` 已包含 zoom、无需再乘一次，获得全量原始 V 字幕支持；“可用 S 字幕代替 V 镜头状态”和“JPG 文件名秒数就是曝光时刻”已被原始记录否定。M0 的 `1920/36` 宽度换算、`cx/cy` 恰在图像中心、零畸变、固定外参为零、所有视频 GPS 即各镜头光心、忽略 roll 仍无原始标定支持。照片 MRK 的补偿与 CMOS 位置可缩小**照片**杆臂不确定性，但不能外推到视频或其他镜头。M0 所用绝对高度与地面参考的垂直基准是否一致也仍未知。

优先路径是：先从历史导出帧追认源 MP4 和**原始帧 PTS**，固定 V/T 通道映射；再按 24/70/168 mm 物理镜头及实际 zoom 档采集已知几何标靶，测出 fx/fy、cx/cy、畸变；随后用独立控制点与姿态变化求相机固定外参及视频杆臂，最后用未参与标定的多视角火点验证定位。现有数据可支持名义射线和时间/模式诊断，不能把照片/字幕的等效焦距、MRK 原始观测或既有 SfM 拟合值冒充厂家标定参数。
