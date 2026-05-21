# 📸 照片整理工具 photo-organizer

纯 Python 标准库实现的照片整理工具，**无需任何第三方依赖**。

## 功能

- 🔍 **递归扫描** 目录下所有图片和视频
- 🆔 **MD5 去重** — 找出完全相同的文件，只保留一份
- 📅 **按年月分类** — 从文件名或修改时间提取日期
- 📂 **自动组织** — 创建 `2025/03/` 这样的文件夹结构
- 👁️ **预览模式** — 先看结果再动手
- 🚚 **移动/复制** — 可选移动或复制文件

## 用法

```bash
# 整理照片（默认复制）
python3 photo_organizer.py ~/Pictures

# 预览模式（不真做）
python3 photo_organizer.py ~/Pictures --dry-run

# 移动模式（而非复制）
python3 photo_organizer.py ~/Pictures --mode move

# 指定输出目录
python3 photo_organizer.py ~/Pictures --output ~/整理好的照片
```

## 工作原理

```
输入目录
    ↓
递归扫描图片/视频 (jpg/png/gif/bmp/tiff/webp/heic/mp4/mov/...)
    ↓
MD5 哈希计算 → 去重（重复文件只保留第一份）
    ↓
从文件名或修改时间提取拍摄日期
    ↓
按 年/月 创建文件夹 → 复制/移动文件
```

## 依赖

- Python 3.6+
- 零第三方依赖 🎉
