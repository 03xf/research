"""
YOLO 格式的数据集转化为 COCO 格式的数据集
--root_dir 输入根路径
--save_path 保存文件的名字(没有random_split时使用)
--random_split 有则会随机划分数据集，然后再分别保存为3个文件。
--split_by_file 按照 ./train.txt ./val.txt ./test.txt 来对数据集进行划分。
"""

import os
import cv2
import json
from tqdm import tqdm
# from sklearn.model_selection import train_test_split
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--root_dir', default='/home/member/xmy/xmy/datasets/smoke/datasets_yolo',type=str, help="root path of images and labels, include ./images and ./labels and classes.txt")
parser.add_argument('--save_path', type=str,default='/home/member/xmy/xmy/datasets/smoke/datasets_coco/annotations/train.json', help="if not split the dataset, give a path to a json file")
parser.add_argument('--random_split', action='store_true', help="random split the dataset, default ratio is 8:1:1")
parser.add_argument('--split_by_file', action='store_true', help="define how to split the dataset, include ./train.txt ./val.txt ./test.txt ")

arg = parser.parse_args()

# def train_test_val_split_random(img_paths,ratio_train=0.8,ratio_test=0.1,ratio_val=0.1):
#     # 这里可以修改数据集划分的比例。
#     assert int(ratio_train+ratio_test+ratio_val) == 1
#     train_img, middle_img = train_test_split(img_paths,test_size=1-ratio_train, random_state=233)
#     ratio=ratio_val/(1-ratio_train)
#     val_img, test_img  =train_test_split(middle_img,test_size=ratio, random_state=233)
#     print("NUMS of train:val:test = {}:{}:{}".format(len(train_img), len(val_img), len(test_img)))
#     return train_img, val_img, test_img

# def train_test_val_split_by_files(img_paths, root_dir):
#     # 根据文件 train.txt, val.txt, test.txt（里面写的都是对应集合的图片名字） 来定义训练集、验证集和测试集
#     phases = ['train', 'val', 'test']
#     img_split = []
#     for p in phases:
#         define_path = os.path.join(root_dir, f'{p}.txt')
#         print(f'Read {p} dataset definition from {define_path}')
#         assert os.path.exists(define_path)
#         with open(define_path, 'r') as f:
#             img_paths = f.readlines()
#             # img_paths = [os.path.split(img_path.strip())[1] for img_path in img_paths]  # NOTE 取消这句备注可以读取绝对地址。
#             img_split.append(img_paths)
#     return img_split[0], img_split[1], img_split[2]



def yolo2coco(arg):
    root_path = arg.root_dir
    print("Loading data from ", root_path)

    assert os.path.exists(root_path)
    originLabelsDir = os.path.join(root_path, 'labels')                                        
    originImagesDir = os.path.join(root_path, 'images')
    with open(os.path.join(root_path, 'classes.txt')) as f:
        classes = f.read().strip().split()
    
    # 初始化用于保存训练、验证集的字典
    train_dataset = {'categories': [], 'annotations': [], 'images': []}
    val_dataset = {'categories': [], 'annotations': [], 'images': []}

    # 建立类别标签和数字id的对应关系, 类别id从0开始。
    for i, cls in enumerate(classes):
        category = {'id': i, 'name': cls, 'supercategory': 'mark'}
        train_dataset['categories'].append(category)
        val_dataset['categories'].append(category)
    
    # 定义划分路径
    splits = {'train': train_dataset, 'val': val_dataset}
    ann_id_cnt = 0  # 标注的ID计数

    for split_name, dataset in splits.items():
        image_dir = os.path.join(originImagesDir, split_name)
        label_dir = os.path.join(originLabelsDir, split_name)
        if not os.path.exists(image_dir) or not os.path.exists(label_dir):
            print(f"Skipping {split_name} as the directory does not exist.")
            continue

        indexes = os.listdir(image_dir)  # 获取文件列表

        for k, index in enumerate(tqdm(indexes, desc=f"Processing {split_name}")):
            # 支持 png 和 jpg 格式的图片
            txtFile = index.replace('images', 'txt').replace('.jpg', '.txt').replace('.png', '.txt')

            # 读取图像的宽和高
            img_path = os.path.join(image_dir, index)
            im = cv2.imread(img_path)
            if im is None:
                print(f"Warning: Failed to read image {img_path}")
                continue
            height, width, _ = im.shape

            # 添加图像的信息
            dataset['images'].append({
                'file_name': os.path.join(split_name, index),
                'id': k,
                'width': width,
                'height': height
            })

            label_path = os.path.join(label_dir, txtFile)
            if not os.path.exists(label_path):
                continue

            with open(label_path, 'r') as fr:
                labelList = fr.readlines()
                for label in labelList:
                    label = label.strip().split()
                    x = float(label[1])
                    y = float(label[2])
                    w = float(label[3])
                    h = float(label[4])

                    # 转换 x, y, w, h 为 x1, y1, x2, y2
                    x1 = (x - w / 2) * width
                    y1 = (y - h / 2) * height
                    x2 = (x + w / 2) * width
                    y2 = (y + h / 2) * height

                    cls_id = int(label[0])
                    bbox_width = max(0, x2 - x1)
                    bbox_height = max(0, y2 - y1)
                    dataset['annotations'].append({
                        'area': bbox_width * bbox_height,
                        'bbox': [x1, y1, bbox_width, bbox_height],
                        'category_id': cls_id,
                        'id': ann_id_cnt,
                        'image_id': k,
                        'iscrowd': 0,
                        'segmentation': [[x1, y1, x2, y1, x2, y2, x1, y2]]
                    })
                    ann_id_cnt += 1

    # 保存结果
    folder = os.path.join(root_path, 'annotations')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    for split_name, dataset in splits.items():
        json_name = os.path.join(folder, f"{split_name}.json")
        with open(json_name, 'w') as f:
            json.dump(dataset, f)
            print(f'Save annotation to {json_name}')

if __name__ == "__main__":
    yolo2coco(arg)
