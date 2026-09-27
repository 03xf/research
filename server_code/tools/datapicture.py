"""
目标检测数据集标注框大小分布分析脚本
支持 COCO、VOC 和 YOLO 格式
"""

import json
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import List, Tuple, Dict
import argparse
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体（如果需要显示中文）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class BBoxAnalyzer:
    """标注框分析器"""
    
    def __init__(self, dataset_name: str = "Custom Dataset"):
        """
        初始化分析器
        
        Args:
            dataset_name: 数据集名称，用于图表标题
        """
        self.dataset_name = dataset_name
        self.widths = []
        self.heights = []
        self.areas = []
        self.aspect_ratios = []
        
    def load_coco_annotations(self, annotation_path: str) -> None:
        """
        加载COCO格式标注文件
        
        Args:
            annotation_path: COCO标注JSON文件路径
        """
        print(f"正在加载COCO标注文件: {annotation_path}")
        with open(annotation_path, 'r') as f:
            data = json.load(f)
        
        # 创建id到图像信息的映射
        image_info = {img['id']: (img['width'], img['height']) 
                     for img in data['images']}
        
        # 提取所有标注框
        for ann in data['annotations']:
            x, y, w, h = ann['bbox']
            self._add_bbox(w, h)
        
        print(f"已加载 {len(self.widths)} 个标注框")
    
    def load_voc_annotations(self, annotations_dir: str) -> None:
        """
        加载VOC格式标注文件
        
        Args:
            annotations_dir: VOC标注XML文件目录
        """
        print(f"正在加载VOC标注文件从目录: {annotations_dir}")
        annotations_dir = Path(annotations_dir)
        
        xml_files = list(annotations_dir.glob("*.xml"))
        if not xml_files:
            raise ValueError(f"在 {annotations_dir} 中未找到XML文件")
        
        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # 获取图像尺寸
                size_elem = root.find('size')
                if size_elem is not None:
                    img_width = int(size_elem.find('width').text)
                    img_height = int(size_elem.find('height').text)
                else:
                    continue
                
                # 提取所有目标框
                for obj in root.findall('object'):
                    bbox = obj.find('bndbox')
                    if bbox is not None:
                        xmin = float(bbox.find('xmin').text)
                        ymin = float(bbox.find('ymin').text)
                        xmax = float(bbox.find('xmax').text)
                        ymax = float(bbox.find('ymax').text)
                        
                        w = xmax - xmin
                        h = ymax - ymin
                        self._add_bbox(w, h)
                        
            except Exception as e:
                print(f"解析文件 {xml_file} 时出错: {e}")
        
        print(f"已加载 {len(self.widths)} 个标注框")
    
    def load_yolo_annotations(self, annotations_dir: str, images_dir: str = None, 
                            img_size: Tuple[int, int] = (640, 640)) -> None:
        """
        加载YOLO格式标注文件
        
        Args:
            annotations_dir: YOLO标注TXT文件目录
            images_dir: 图像文件目录（用于获取实际图像尺寸）
            img_size: 默认图像尺寸 (width, height)，如果无法获取实际尺寸时使用
        """
        print(f"正在加载YOLO标注文件从目录: {annotations_dir}")
        annotations_dir = Path(annotations_dir)
        
        txt_files = list(annotations_dir.glob("*.txt"))
        if not txt_files:
            raise ValueError(f"在 {annotations_dir} 中未找到TXT文件")
        
        # 如果提供了图像目录，尝试获取实际图像尺寸
        img_sizes = {}
        if images_dir:
            images_dir = Path(images_dir)
            for img_file in images_dir.glob("*.*"):
                if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
                    # 这里简化处理，实际使用时可能需要PIL等库获取尺寸
                    img_sizes[img_file.stem] = img_size
        
        for txt_file in txt_files:
            try:
                with open(txt_file, 'r') as f:
                    lines = f.readlines()
                
                # 尝试获取对应图像尺寸
                img_key = txt_file.stem
                img_w, img_h = img_sizes.get(img_key, img_size)
                
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 5:  # 至少包含class_id, x_center, y_center, width, height
                        _, x_center, y_center, w_rel, h_rel = map(float, parts[:5])
                        
                        # 将相对坐标转换为绝对坐标
                        w = w_rel * img_w
                        h = h_rel * img_h
                        self._add_bbox(w, h)
                        
            except Exception as e:
                print(f"解析文件 {txt_file} 时出错: {e}")
        
        print(f"已加载 {len(self.widths)} 个标注框")
    
    def _add_bbox(self, width: float, height: float) -> None:
        """添加一个边界框到统计数据中"""
        if width > 0 and height > 0:
            self.widths.append(width)
            self.heights.append(height)
            self.areas.append(width * height)
            self.aspect_ratios.append(height / width if width > 0 else 0)
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        if not self.widths:
            return {}
        
        stats_dict = {
            'total_boxes': len(self.widths),
            'width_mean': np.mean(self.widths),
            'width_std': np.std(self.widths),
            'width_min': np.min(self.widths),
            'width_max': np.max(self.widths),
            'height_mean': np.mean(self.heights),
            'height_std': np.std(self.heights),
            'height_min': np.min(self.heights),
            'height_max': np.max(self.heights),
            'area_mean': np.mean(self.areas),
            'area_std': np.std(self.areas),
            'area_min': np.min(self.areas),
            'area_max': np.max(self.areas),
            'aspect_ratio_mean': np.mean(self.aspect_ratios),
            'aspect_ratio_std': np.std(self.aspect_ratios),
            'small_objects': sum(1 for area in self.areas if area < 32*32),
            'medium_objects': sum(1 for area in self.areas if 32*32 <= area <= 96*96),
            'large_objects': sum(1 for area in self.areas if area > 96*96),
        }
        
        return stats_dict
    
    def plot_size_distribution(self, save_path: str = None, 
                             figsize: Tuple[int, int] = (12, 10)) -> None:
        """
        绘制标注框大小分布图
        
        Args:
            save_path: 保存图像的路径，如果为None则不保存
            figsize: 图像尺寸 (width, height)
        """
        if not self.widths:
            print("没有数据可绘制！")
            return
        
        # 创建子图
        fig = plt.figure(figsize=figsize)
        
        # 1. 散点图（主图）
        ax1 = plt.subplot(2, 2, 1)
        scatter = ax1.scatter(self.widths, self.heights, alpha=0.3, s=5, 
                            c=self.areas, cmap='viridis', edgecolors='none')
        
        # 添加对角线（正方形参考线）
        max_val = max(max(self.widths), max(self.heights))
        ax1.plot([0, max_val], [0, max_val], 'r--', alpha=0.5, linewidth=1.5, 
                label='宽高相等线 (h=w)')
        
        # 添加平均点
        mean_width = np.mean(self.widths)
        mean_height = np.mean(self.heights)
        ax1.scatter(mean_width, mean_height, color='red', s=100, 
                   marker='X', label=f'平均值 ({mean_width:.1f}, {mean_height:.1f})', 
                   edgecolors='black', linewidth=1.5)
        
        ax1.set_xlabel('宽度 (pixels)', fontsize=12)
        ax1.set_ylabel('高度 (pixels)', fontsize=12)
        ax1.set_title(f'{self.dataset_name} - 标注框大小分布', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right')
        
        # 添加颜色条
        cbar = plt.colorbar(scatter, ax=ax1)
        cbar.set_label('标注框面积 (pixel²)', fontsize=10)
        
        # 2. 宽度分布直方图
        ax2 = plt.subplot(2, 2, 2)
        ax2.hist(self.widths, bins=50, alpha=0.7, color='skyblue', edgecolor='black')
        ax2.axvline(mean_width, color='red', linestyle='--', linewidth=2, 
                   label=f'均值: {mean_width:.1f}')
        ax2.set_xlabel('宽度 (pixels)', fontsize=11)
        ax2.set_ylabel('频数', fontsize=11)
        ax2.set_title('宽度分布直方图', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # 3. 高度分布直方图
        ax3 = plt.subplot(2, 2, 3)
        ax3.hist(self.heights, bins=50, alpha=0.7, color='lightgreen', edgecolor='black')
        ax3.axvline(mean_height, color='red', linestyle='--', linewidth=2, 
                   label=f'均值: {mean_height:.1f}')
        ax3.set_xlabel('高度 (pixels)', fontsize=11)
        ax3.set_ylabel('频数', fontsize=11)
        ax3.set_title('高度分布直方图', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.legend()
        
        # 4. 宽高比分布
        ax4 = plt.subplot(2, 2, 4)
        
        # 计算宽高比
        aspect_ratios = np.array(self.aspect_ratios)
        
        # 对数变换以便更好显示
        log_ratios = np.log10(aspect_ratios)
        ax4.hist(log_ratios, bins=50, alpha=0.7, color='orange', edgecolor='black')
        
        # 添加参考线
        ax4.axvline(0, color='red', linestyle='--', linewidth=2, 
                   label='h=w (正方形)')
        
        # 设置x轴刻度为实际比例
        tick_positions = [-1, -0.5, 0, 0.5, 1]  # log10值
        tick_labels = ['0.1', '0.3', '1', '3', '10']  # 实际比例值
        ax4.set_xticks(tick_positions)
        ax4.set_xticklabels(tick_labels)
        
        ax4.set_xlabel('高宽比 (h/w)', fontsize=11)
        ax4.set_ylabel('频数', fontsize=11)
        ax4.set_title('宽高比分布 (对数刻度)', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3)
        ax4.legend()
        
        plt.suptitle(f'{self.dataset_name} - 标注框统计分析', fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存至: {save_path}")
        
        plt.show()
        
        # 打印统计信息
        stats = self.get_statistics()
        print("\n" + "="*60)
        print("数据集统计摘要:")
        print("="*60)
        print(f"总标注框数量: {stats['total_boxes']:,}")
        print(f"\n宽度统计:")
        print(f"  平均值: {stats['width_mean']:.1f} ± {stats['width_std']:.1f} pixels")
        print(f"  范围: [{stats['width_min']:.1f}, {stats['width_max']:.1f}]")
        print(f"\n高度统计:")
        print(f"  平均值: {stats['height_mean']:.1f} ± {stats['height_std']:.1f} pixels")
        print(f"  范围: [{stats['height_min']:.1f}, {stats['height_max']:.1f}]")
        print(f"\n面积统计:")
        print(f"  平均值: {stats['area_mean']:.1f} ± {stats['area_std']:.1f} pixel²")
        print(f"  范围: [{stats['area_min']:.1f}, {stats['area_max']:.1f}]")
        print(f"\n目标尺度分布 (COCO标准):")
        print(f"  小目标 (area < 32×32): {stats['small_objects']:,} ({stats['small_objects']/stats['total_boxes']*100:.1f}%)")
        print(f"  中目标 (32×32 ≤ area ≤ 96×96): {stats['medium_objects']:,} ({stats['medium_objects']/stats['total_boxes']*100:.1f}%)")
        print(f"  大目标 (area > 96×96): {stats['large_objects']:,} ({stats['large_objects']/stats['total_boxes']*100:.1f}%)")
        print(f"\n宽高比统计:")
        print(f"  平均值: {stats['aspect_ratio_mean']:.2f} ± {stats['aspect_ratio_std']:.2f}")
        print("="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='目标检测数据集标注框大小分布分析')
    parser.add_argument('--format', type=str, required=True,
                       choices=['coco', 'voc', 'yolo'],
                       help='标注文件格式: coco, voc, yolo')
    parser.add_argument('--path', type=str, required=True,
                       help='标注文件或目录路径')
    parser.add_argument('--name', type=str, default='Custom Dataset',
                       help='数据集名称')
    parser.add_argument('--output', type=str, default='bbox_distribution.png',
                       help='输出图像路径')
    parser.add_argument('--img-dir', type=str, 
                       help='图像目录路径（仅YOLO格式需要）')
    parser.add_argument('--img-size', type=int, nargs=2, default=[640, 640],
                       help='默认图像尺寸 width height（仅YOLO格式需要）')
    
    args = parser.parse_args()
    
    # 创建分析器
    analyzer = BBoxAnalyzer(args.name)
    
    # 根据格式加载数据
    try:
        if args.format == 'coco':
            analyzer.load_coco_annotations(args.path)
        elif args.format == 'voc':
            analyzer.load_voc_annotations(args.path)
        elif args.format == 'yolo':
            analyzer.load_yolo_annotations(
                args.path, 
                args.img_dir,
                tuple(args.img_size)
            )
    except Exception as e:
        print(f"加载数据时出错: {e}")
        return
    
    # 绘制图表
    analyzer.plot_size_distribution(args.output)
    
    # 可选：保存统计信息到文件
    stats = analyzer.get_statistics()
    stats_file = Path(args.output).with_suffix('.txt')
    with open(stats_file, 'w') as f:
        f.write(f"数据集: {args.name}\n")
        f.write(f"标注格式: {args.format}\n")
        f.write(f"总标注框数: {stats['total_boxes']}\n\n")
        for key, value in stats.items():
            if key != 'total_boxes':
                f.write(f"{key}: {value}\n")
    print(f"统计信息已保存至: {stats_file}")


# 直接使用的示例
def example_usage():
    """使用示例"""
    
    # 示例1: 使用COCO格式
    print("示例1: 分析COCO格式数据集")
    analyzer = BBoxAnalyzer("COCO森林烟雾数据集")
    analyzer.load_coco_annotations("path/to/your/annotations.json")
    analyzer.plot_size_distribution("coco_bbox_distribution.png")
    
    # 示例2: 使用VOC格式
    print("\n示例2: 分析VOC格式数据集")
    analyzer = BBoxAnalyzer("VOC森林烟雾数据集")
    analyzer.load_voc_annotations("path/to/voc/annotations/")
    analyzer.plot_size_distribution("voc_bbox_distribution.png")
    
    # 示例3: 使用YOLO格式
    print("\n示例3: 分析YOLO格式数据集")
    analyzer = BBoxAnalyzer("YOLO森林烟雾数据集")
    analyzer.load_yolo_annotations(
        annotations_dir="path/to/yolo/labels/",
        images_dir="path/to/images/",
        img_size=(640, 640)
    )
    analyzer.plot_size_distribution("yolo_bbox_distribution.png")


if __name__ == "__main__":
    # 使用命令行参数
    # main()
    
    # 或者直接运行示例
    print("请先配置正确的文件路径，然后取消注释下面的代码行运行:")
    print("# example_usage()")
    
    # 最简单的测试方式：创建模拟数据
    print("\n生成模拟数据示例:")
    analyzer = BBoxAnalyzer("模拟森林烟雾数据集")
    
    # 生成模拟数据（小目标居多）
    np.random.seed(42)
    n_samples = 1000
    
    # 模拟小目标 (10-100像素)
    small_w = np.random.uniform(10, 100, int(n_samples * 0.6))
    small_h = np.random.uniform(10, 120, int(n_samples * 0.6))
    
    # 模拟中目标 (100-300像素)
    medium_w = np.random.uniform(100, 300, int(n_samples * 0.3))
    medium_h = np.random.uniform(100, 350, int(n_samples * 0.3))
    
    # 模拟大目标 (300-500像素)
    large_w = np.random.uniform(300, 500, int(n_samples * 0.1))
    large_h = np.random.uniform(300, 550, int(n_samples * 0.1))
    
    # 合并所有数据
    all_widths = np.concatenate([small_w, medium_w, large_w])
    all_heights = np.concatenate([small_h, medium_h, large_h])
    
    for w, h in zip(all_widths, all_heights):
        analyzer._add_bbox(w, h)
    
    analyzer.plot_size_distribution("simulated_bbox_distribution.png")