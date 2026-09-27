import cv2
import os

# 设置包含子文件夹train和val的目录路径
parent_directory = '/home/member/xmy/xmy/datasets/smoke/datasets_yolo/images'

# 要处理的子文件夹名称列表
subfolders = ['train', 'val']

# 遍历每个子文件夹
for subfolder in subfolders:
    # 构造子文件夹的完整路径
    directory = os.path.join(parent_directory, subfolder)
    
    # 遍历子文件夹中的所有文件
    for filename in os.listdir(directory):
        # 检查文件扩展名是否为.jpeg或.jpg
        if filename.lower().endswith(('.jpeg', '.jpg')):
            # 构造文件的完整路径
            file_path = os.path.join(directory, filename)
            
            # 使用imread读取图像
            image = cv2.imread(file_path)
            
            # 检查图像是否正确读取
            if image is not None:
                # 使用imwrite将图像写回到同一路径
                cv2.imwrite(file_path, image)
                print(f'Processed {subfolder}/{filename}')
            else:
                print(f'Failed to read {subfolder}/{filename}')