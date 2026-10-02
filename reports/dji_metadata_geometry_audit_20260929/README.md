# 审计复现说明

源数据位于只读访问的服务器目录 `@raw`；本目录是本次新建的结果目录。原始 JPG、MP4、MRK、RTK、OBS、NAV 均未写入。52 张原始 JPG 的前后 SHA-256 见 `source_integrity_check.csv`。

执行顺序：

1. 在数据服务器用 Python 运行 `extract_images_server.py`，调用 ExifTool 完整枚举原始 JPG 的 EXIF、DJI 私有字段及原始 XMP 包。
2. 运行 `audit_aux_server.py`，读取所有 MP4 容器/流、每个内嵌字幕开头/中间/结尾样本、MRK 和 RINEX/RTK 文件头。
3. 运行 `b3_channel_check_server.py`，按历史标称 PTS 分别读取 B3 S/V/T 原视频字幕。
4. 运行 `scan_full_subtitles_server.py` 遍历全部 208 条 MP4 内嵌字幕。将 `/tmp/dji_metadata_geometry_audit_20260929/` 的产物复制回本目录，在本地运行 `python analyze_full_subtitles.py` 和 `python make_audit.py`，生成逐镜头、时间链、全视频状态、几何状态和异常表。
5. 运行 `verify_source_hashes_server.py`，复制哈希核验结果回本目录；最后运行 `python validate_audit.py`。

`scan_full_subtitles_server.py` 按连续相同焦距/zoom 汇总全视频状态，不修改 MP4。`analyze_full_subtitles.py` 使用原视频 PTS 比较同期 S/V 状态；极短差异仍须结合字幕墙钟时间复核。

核心文件：`all_image_metadata.csv` 为每张原始照片的常用字段；`all_metadata_keys_long.csv`、`all_xmp_values_long.csv`、`raw_exiftool_metadata.jsonl` 保留所有读到的键和值；`all_xmp_keys.csv` 记录 XMP 字段的文件、镜头和批次覆盖；`camera_lens_inventory.csv`、`physical_camera_ledger.csv`、`focal_zoom_inventory.csv` 按物理相机记账；`time_alignment_audit.csv`、`b3_channel_telemetry.csv`、`video_subtitle_channel_comparison.csv` 保留时间和通道核对；`rtk_mrk_file_inventory.csv`、`mrk_exposure_events.csv` 记录辅助文件；`geometry_parameter_status.csv` 与 `anomalies.csv` 是结论与追溯索引。
