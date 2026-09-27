"""Verify the paired sample frames and model weights in this snapshot."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
sample_root = root / "样本/候选抽帧"
rows = [
    json.loads(line)
    for line in (sample_root / "选取样本来源.jsonl").read_text(encoding="utf-8").splitlines()
]
assert len(rows) == 36
assert len({row["candidate_id"] for row in rows}) == 36

for row in rows:
    for channel in ("v", "t"):
        relative = row[f"{channel}_image"].split("/images/")[1]
        path = sample_root / "images" / relative
        assert path.is_file(), path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row[f"{channel}_image_sha256"], path

weights = json.loads((root / "权重校验.json").read_text(encoding="utf-8"))
for item in weights:
    path = root / item["file"]
    assert path.is_file(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["expected_sha256"], path

print(f"Verified {len(rows)} V/T pairs and {len(weights)} model weights")
