import os
from PIL import Image
from tqdm import tqdm

# ========== 配置（无需修改，直接用） ==========
# 原始路径
REAL_SRC = "/home/member/xmy/xmy/datasets/smoke/datasets_yolo/images/train0/"
FAKE_SRC = "/home/member/zd/DEADiff-main/output_gradio/train_smoke/"
# 标准化后的路径（自动创建）
REAL_CLEAN = "/home/member/xmy/xmy/datasets/smoke/datasets_yolo/images/train0_512/"
FAKE_CLEAN = "/home/member/xmy/xmy/datasets/smoke/datasets_yolo/images/train_smoke_512/"
# 目标尺寸（和生成图一致）
TARGET_SIZE = (512, 512)

# ========== 创建目录 ==========
os.makedirs(REAL_CLEAN, exist_ok=True)
os.makedirs(FAKE_CLEAN, exist_ok=True)

# ========== 批量缩放图片 ==========
def resize_images(src_dir, dst_dir):
    print(f"处理 {src_dir} → {dst_dir}")
    img_list = [f for f in os.listdir(src_dir) if f.endswith(".jpg")]
    for img_name in tqdm(img_list):
        src_path = os.path.join(src_dir, img_name)
        dst_path = os.path.join(dst_dir, img_name)
        try:
            # 打开图片并转为RGB（确保3通道）
            img = Image.open(src_path).convert("RGB")
            # 等比例缩放+居中裁剪（避免拉伸变形）
            img.thumbnail(TARGET_SIZE, Image.Resampling.LANCZOS)
            # 居中裁剪到512×512
            left = (img.width - TARGET_SIZE[0]) / 2
            top = (img.height - TARGET_SIZE[1]) / 2
            right = left + TARGET_SIZE[0]
            bottom = top + TARGET_SIZE[1]
            img = img.crop((left, top, right, bottom))
            # 保存
            img.save(dst_path, quality=95)
        except Exception as e:
            print(f"\n跳过损坏图片：{img_name} - {str(e)}")

# 处理真实集和生成集
resize_images(REAL_SRC, REAL_CLEAN)
resize_images(FAKE_SRC, FAKE_CLEAN)

print("\n✅ 尺寸标准化完成！")
print(f"真实集（512×512）：{REAL_CLEAN}")
print(f"生成集（512×512）：{FAKE_CLEAN}")