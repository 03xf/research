# import os
# import json
# from pathlib import Path
# from PIL import Image

# def yolo_to_coco(yolo_dir, output_json, dataset_type='train'):
#     images = []
#     annotations = []
#     categories = []
#     category_id_map = {}  # Mapping from class name to id
#     annotation_id = 1  # Unique annotation id

#     # 加载类别文件
#     class_file = Path(yolo_dir) /'labels'/'class_names.txt'
#     if not class_file.exists():
#         raise FileNotFoundError(f"未找到类别文件: {class_file}")
    
#     with open(class_file) as f:
#         class_names = f.read().strip().splitlines()
#         for idx, name in enumerate(class_names):
#             category_id_map[name] = idx + 1  # COCO类别id从1开始
#             categories.append({"id": idx + 1, "name": name})

#     # 获取图像和标签路径
#     image_dir = Path(yolo_dir) / 'images' / dataset_type
#     label_dir = Path(yolo_dir) / 'labels' / dataset_type

#     for label_file in label_dir.glob("*.txt"):
#         if label_file.name == "class_names.txt":
#             continue

#         # 获取图像路径
#         img_name = label_file.stem + ".jpg"  # 如果是 .png，请相应修改
#         img_path = image_dir / img_name

#         # 确保图像存在
#         if not img_path.exists():
#             print(f"图像文件未找到: {img_path}")
#             continue

#         # 读取图像信息
#         with Image.open(img_path) as img:
#             width, height = img.size
        
#         # 创建图像信息
#         image_id = len(images) + 1
#         images.append({
#             "id": image_id,
#             "file_name": img_name,
#             "width": width,
#             "height": height
#         })

#         # 读取标签文件中的目标信息
#         with open(label_file) as f:
#             for line in f:
#                 parts = line.strip().split()
#                 if len(parts) != 5:
#                     continue  # 忽略格式不正确的行

#                 class_id, x_center, y_center, box_width, box_height = map(float, parts)
#                 class_id = int(class_id)

#                 # 转换中心点坐标和宽高为COCO格式的边界框
#                 x_min = (x_center - box_width / 2) * width
#                 y_min = (y_center - box_height / 2) * height
#                 bbox_width = box_width * width
#                 bbox_height = box_height * height

#                 annotations.append({
#                     "id": annotation_id,
#                     "image_id": image_id,
#                     "category_id": class_id + 1,  # 注意类别id要从1开始
#                     "bbox": [x_min, y_min, bbox_width, bbox_height],
#                     "area": bbox_width * bbox_height,
#                     "segmentation": [],
#                     "iscrowd": 0
#                 })
#                 annotation_id += 1

#     # 创建COCO格式的数据结构
#     coco_data = {
#         "images": images,
#         "annotations": annotations,
#         "categories": categories
#     }

#     # 保存为JSON文件
#     with open(output_json, 'w') as f:
#         json.dump(coco_data, f, indent=4)
#     print(f"已保存COCO格式数据至: {output_json}")

# # 示例调用，分别转换训练集和验证集
# yolo_dir = "/home/member/xmy/xmy/datasets/smoke/datasets_yolo"  # 替换为实际路径
# output_train_json = "train_coco.json"
# output_val_json = "val_coco.json"

# # 转换训练集和验证集
# yolo_to_coco(yolo_dir, output_train_json, dataset_type='train')
# yolo_to_coco(yolo_dir, output_val_json, dataset_type='val')


import os
import json
from pathlib import Path
from PIL import Image

def yolo_to_coco(yolo_dir, output_json, dataset_type='train'):
    images = []
    annotations = []
    categories = []
    category_id_map = {}  # Mapping from class name to id
    annotation_id = 1  # Unique annotation id

    # 加载类别文件
    class_file = Path(yolo_dir) / 'labels' / 'class_names.txt'
    if not class_file.exists():
        raise FileNotFoundError(f"未找到类别文件: {class_file}")
    
    with open(class_file) as f:
        class_names = f.read().strip().splitlines()
        for idx, name in enumerate(class_names):
            category_id_map[name] = idx + 1  # COCO类别id从1开始
            categories.append({"id": idx + 1, "name": name})

    # 获取图像和标签路径，并按文件名排序
    image_dir = Path(yolo_dir) / 'images' / dataset_type
    label_dir = Path(yolo_dir) / 'labels' / dataset_type

    image_files = sorted(image_dir.glob("*.jpg"))  # 确保图像按文件名顺序排列
    label_files = sorted(label_dir.glob("*.txt"))  # 确保标签按文件名顺序排列

    for img_path, label_file in zip(image_files, label_files):
        if label_file.name == "class_names.txt":
            continue

        # 读取图像信息
        with Image.open(img_path) as img:
            width, height = img.size
        
        # 创建图像信息
        image_id = len(images) + 1
        images.append({
            "id": image_id,
            "file_name": img_path.name,
            "width": width,
            "height": height
        })

        # 读取标签文件中的目标信息
        with open(label_file) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue  # 忽略格式不正确的行

                class_id, x_center, y_center, box_width, box_height = map(float, parts)
                class_id = int(class_id)

                # 转换中心点坐标和宽高为COCO格式的边界框
                x_min = (x_center - box_width / 2) * width
                y_min = (y_center - box_height / 2) * height
                bbox_width = box_width * width
                bbox_height = box_height * height

                annotations.append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": class_id + 1,  # 注意类别id要从1开始
                    "bbox": [x_min, y_min, bbox_width, bbox_height],
                    "area": bbox_width * bbox_height,
                    "segmentation": [],
                    "iscrowd": 0
                })
                annotation_id += 1

    # 创建COCO格式的数据结构
    coco_data = {
        "images": images,
        "annotations": annotations,
        "categories": categories
    }

    # 保存为JSON文件
    with open(output_json, 'w') as f:
        json.dump(coco_data, f, indent=4)
    print(f"已保存COCO格式数据至: {output_json}")

# 示例调用，分别转换训练集和验证集
yolo_dir = "/home/member/xmy/xmy/datasets/smoke/datasets_yolo"  # 替换为实际路径
output_train_json = "coco_train.json"
output_val_json = "coco_val.json"

# 转换训练集和验证集
yolo_to_coco(yolo_dir, output_train_json, dataset_type='train')
yolo_to_coco(yolo_dir, output_val_json, dataset_type='val')
