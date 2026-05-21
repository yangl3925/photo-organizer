#!/usr/bin/env python3
"""
📸 照片整理工具 — 按年月分类 + 删除完全相同照片（基于 MD5）

不需要任何第三方库，纯 Python 标准库实现。

用法：
  python3 photo_organizer.py <照片目录>
  python3 photo_organizer.py <照片目录> --dry-run    # 预览模式
  python3 photo_organizer.py <照片目录> --mode move   # 移动而非复制
  python3 photo_organizer.py <照片目录> --output ~/整理好的照片

工作原理：
  1. 递归扫描目录下的所有图片（jpg/png/gif/bmp/tiff/webp/heic）
  2. 计算每个文件的 MD5 哈希，找出完全相同的文件，只保留一份
  3. 从文件名或文件修改时间提取拍摄日期
  4. 按 年/月 创建文件夹并将文件整理进去
"""

import os
import sys
import shutil
import hashlib
import argparse
import re
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from stat import S_ISREG

# ── 支持的图片扩展名 ──
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.heic', '.heif'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.mts', '.m2ts'}


def md5_hash(filepath, chunk_size=65536):
    """计算文件 MD5 哈希。"""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def extract_date_from_filename(name):
    """从文件名提取日期。"""
    patterns = [
        # IMG_20250301_123456.jpg, 20250301_123456.jpg
        r'(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])',
        # 2025-03-01, 2025_03_01, 2025.03.01
        r'(20\d{2})[-_\.](0[1-9]|1[0-2])[-_\.](0[1-9]|[12]\d|3[01])',
        # 03-01-2025 (美式)
        r'(0[1-9]|1[0-2])[-_\.](0[1-9]|[12]\d|3[01])[-_\.](20\d{2})',
    ]
    for pat in patterns:
        m = re.search(pat, name)
        if m:
            groups = m.groups()
            try:
                if pat.startswith(r'(0[1-9]|1[0-2])'):  # 美式 MM-DD-YYYY
                    return datetime(int(groups[2]), int(groups[0]), int(groups[1]))
                else:
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
            except ValueError:
                continue
    return None


def get_file_date(filepath):
    """从文件获取日期：文件名 -> 文件修改时间。"""
    name = filepath.stem
    dt = extract_date_from_filename(name)
    if dt:
        return dt
    # 回退到文件修改时间
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime)


def collect_files(directory, extensions):
    """递归收集所有媒体文件。"""
    files = []
    for root, dirs, fnames in os.walk(directory):
        for fname in fnames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in extensions:
                files.append(Path(root) / fname)
    return sorted(files)


def format_size(bytes_val):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}TB"


def main():
    parser = argparse.ArgumentParser(
        description='📸 照片整理工具 — 按年月分类 + 删除完全相同照片',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 photo_organizer.py ~/Pictures                              # 预览
  python3 photo_organizer.py ~/Pictures --run                        # 执行整理
  python3 photo_organizer.py ~/Pictures --run --output ~/整理好的照片  # 输出到指定目录
  python3 photo_organizer.py ~/Pictures --run --mode move --include-video  # 移动+视频
        """
    )
    parser.add_argument('input_dir', help='照片目录路径')
    parser.add_argument('--output', '-o', default=None, help='输出目录（默认：在输入目录旁创建）')
    parser.add_argument('--mode', choices=['copy', 'move'], default='copy', help='复制还是移动')
    parser.add_argument('--run', action='store_true', help='执行整理（不加则只预览）')
    parser.add_argument('--include-video', action='store_true', help='同时整理视频')
    parser.add_argument('--no-cleanup', action='store_true', help='找出重复但不删除')

    args = parser.parse_args()

    # ------ 1. 扫描 ------
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"❌ 目录不存在: {input_dir}")
        sys.exit(1)

    exts = IMAGE_EXTS | (VIDEO_EXTS if args.include_video else set())
    files = collect_files(input_dir, exts)
    total = len(files)

    print(f"📂 扫描: {input_dir}")
    print(f"📁 输出: {args.output or f'{input_dir.parent}/{input_dir.name}_整理后'}")
    print(f"🔍 找到 {total} 个媒体文件")
    if not args.run:
        print("ℹ️  预览模式（加 --run 执行整理）")
    print()

    if total == 0:
        print("没有找到需要处理的文件。")
        return

    # ------ 2. MD5 去重 ------
    print("── 第一步：MD5 去重 ──")
    hash_map = defaultdict(list)
    for i, fp in enumerate(files):
        fp_hash = md5_hash(fp)
        hash_map[fp_hash].append(fp)
        if (i + 1) % 100 == 0:
            print(f"  ⏳ {i+1}/{total}...")

    dup_groups = {h: paths for h, paths in hash_map.items() if len(paths) > 1}

    dup_count = 0
    dup_size = 0
    group_num = 0
    print(f"\n  🔍 发现 {len(dup_groups)} 组重复文件：")
    print(f"  {'='*60}")
    for h, paths in sorted(dup_groups.items(), key=lambda x: -len(x[1])):
        group_num += 1
        keep = paths[0]
        for p in paths[1:]:
            dup_size += os.path.getsize(p)
        dup_count += len(paths) - 1
        print(f"\n  组 #{group_num}（{len(paths)} 个完全相同，{format_size(os.path.getsize(keep))}）:")
        for p in paths:
            if p == keep:
                print(f"     ✅ [保留] {p}")
            else:
                print(f"     🗑️ [删除] {os.path.dirname(p)}/")
                print(f"             {p.name}")

    print(f"\n  ───────────────────────────────")
    print(f"  去重前: {total} 个文件")
    print(f"  去重后: {total - dup_count} 个文件")
    print(f"  重复: {dup_count} 个, 可释放 {format_size(dup_size)}")

    if not args.run:
        print(f"\n── 预览结束（加 --run 执行整理）──")
        return

    # ------ 3. 执行整理 ------
    output_dir = Path(args.output).expanduser().resolve() if args.output else \
                 input_dir.parent / f"{input_dir.name}_整理后"

    print(f"\n── 第二步：按年月整理到 {output_dir} ──")

    # 去重后的文件
    unique_files = [paths[0] for paths in hash_map.values()]

    month_map = defaultdict(list)
    unknown = []
    for fp in unique_files:
        dt = get_file_date(fp)
        if dt:
            month_map[f"{dt.year}/{dt.month:02d}"].append(fp)
        else:
            unknown.append(fp)

    print(f"  按年月分类:")
    for key in sorted(month_map.keys()):
        print(f"    📅 {key}: {len(month_map[key])} 个文件")
    if unknown:
        print(f"    ❓ unknown: {len(unknown)} 个文件")

    copied = 0

    for key in sorted(month_map.keys()):
        target_dir = output_dir / key
        target_dir.mkdir(parents=True, exist_ok=True)
        for fp in month_map[key]:
            dest = target_dir / fp.name
            if dest.exists():
                stem, suffix = dest.stem, dest.suffix
                c = 1
                while (target_dir / f"{stem}_{c}{suffix}").exists():
                    c += 1
                dest = target_dir / f"{stem}_{c}{suffix}"
            if args.mode == 'copy':
                shutil.copy2(fp, dest)
            else:
                shutil.move(str(fp), str(dest))
            copied += 1

    if unknown:
        udir = output_dir / "unknown"
        udir.mkdir(exist_ok=True)
        for fp in unknown:
            dest = udir / fp.name
            if dest.exists():
                stem, suffix = dest.stem, dest.suffix
                c = 1
                while (udir / f"{stem}_{c}{suffix}").exists():
                    c += 1
                dest = udir / f"{stem}_{c}{suffix}"
            if args.mode == 'copy':
                shutil.copy2(fp, dest)
            else:
                shutil.move(str(fp), str(dest))
            copied += 1

    # 删除重复
    deleted = 0
    deleted_size = 0
    if not args.no_cleanup:
        for h, paths in dup_groups.items():
            for p in paths[1:]:
                if p.exists():
                    deleted_size += os.path.getsize(p)
                    os.remove(p)
                    deleted += 1

    # ------ 报告 ------
    print(f"\n── 整理完成 ──")
    print(f"  ✅ 已整理: {copied} 个文件")
    if deleted:
        print(f"  🗑️ 已删除重复: {deleted} 个（释放 {format_size(deleted_size)}）")
    print(f"  📁 输出位置: {output_dir}")

    # 写报告
    report = output_dir / "整理报告.txt"
    with open(report, 'w', encoding='utf-8') as f:
        f.write("📸 照片整理报告\n")
        f.write(f"{'='*40}\n\n")
        f.write(f"扫描目录: {input_dir}\n")
        f.write(f"输出目录: {output_dir}\n")
        f.write(f"模式: {args.mode}\n")
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"原始文件: {total}\n")
        f.write(f"去重文件: {copied}\n")
        f.write(f"删除重复: {deleted} ({format_size(deleted_size)})\n\n")
        f.write("按年月分布:\n")
        for key in sorted(month_map.keys()):
            f.write(f"  {key}: {len(month_map[key])} 个\n")
        if unknown:
            f.write(f"  unknown: {len(unknown)} 个\n")

    print(f"  📄 报告: {report}")
    print(f"\n🎉 完成！")


if __name__ == '__main__':
    main()
