#!/usr/bin/env python3
"""
📸 照片整理工具 — MD5去重 + 按年月分类 + GUI 界面
纯 Python 标准库实现，无需任何第三方依赖。
"""

import os
import sys
import shutil
import hashlib
import re
import time
import threading
import queue
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from tkinter import Tk, filedialog, messagebox
from tkinter import ttk

# ── 支持的扩展名 ──
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.heic', '.heif'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.mts', '.m2ts'}


# ══════════════════════════════════════
# 核心功能（与 CLI 共用）
# ══════════════════════════════════════

def md5_hash(filepath, chunk_size=65536):
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def extract_date_from_filename(name):
    patterns = [
        r'(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])',
        r'(20\d{2})[-_\.](0[1-9]|1[0-2])[-_\.](0[1-9]|[12]\d|3[01])',
        r'(0[1-9]|1[0-2])[-_\.](0[1-9]|[12]\d|3[01])[-_\.](20\d{2})',
    ]
    for pat in patterns:
        m = re.search(pat, name)
        if m:
            groups = m.groups()
            try:
                if pat.startswith(r'(0[1-9]|1[0-2])'):
                    return datetime(int(groups[2]), int(groups[0]), int(groups[1]))
                else:
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
            except ValueError:
                continue
    return None


def get_file_date(filepath):
    name = filepath.stem
    dt = extract_date_from_filename(name)
    if dt:
        return dt
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime)


def collect_files(directory, extensions):
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


def generate_report(input_dir, output_dir, total, copied, deleted, deleted_size,
                    month_map, unknown, mode, elapsed):
    """生成整理报告文本"""
    lines = []
    lines.append("📸 照片整理报告")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"扫描目录: {input_dir}")
    lines.append(f"输出目录: {output_dir}")
    lines.append(f"模式: {'移动' if mode == 'move' else '复制'}")
    lines.append(f"耗时: {elapsed:.1f} 秒")
    lines.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"原始文件: {total}")
    lines.append(f"去重后: {total - deleted}")
    lines.append(f"已整理: {copied}")
    lines.append(f"删除重复: {deleted} ({format_size(deleted_size)})")
    lines.append("")
    lines.append("按年月分布:")
    for key in sorted(month_map.keys()):
        lines.append(f"  📅 {key}: {len(month_map[key])} 个文件")
    if unknown:
        lines.append(f"  ❓ unknown: {len(unknown)} 个文件")
    lines.append("")
    lines.append("─" * 40)
    return "\n".join(lines)


# ══════════════════════════════════════
# 命令行入口
# ══════════════════════════════════════

def run_cli():
    import argparse

    parser = argparse.ArgumentParser(
        description='📸 照片整理工具 — 按年月分类 + 删除完全相同照片',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('input_dir', nargs='?', help='照片目录路径（留空则打开 GUI）')
    parser.add_argument('--output', '-o', default=None, help='输出目录')
    parser.add_argument('--mode', choices=['copy', 'move'], default='copy')
    parser.add_argument('--run', action='store_true', help='执行整理')
    parser.add_argument('--include-video', action='store_true', help='同时整理视频')
    parser.add_argument('--no-cleanup', action='store_true', help='找出重复但不删除')
    parser.add_argument('--gui', action='store_true', help='强制启动 GUI 界面')

    args = parser.parse_args()

    # 无参数或指定 --gui 时启动 GUI
    if args.gui or args.input_dir is None:
        run_gui()
        return

    # ------ CLI 模式 ------
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"❌ 目录不存在: {input_dir}")
        sys.exit(1)

    exts = IMAGE_EXTS | (VIDEO_EXTS if args.include_video else set())
    files = collect_files(input_dir, exts)
    total = len(files)

    print(f"📂 扫描: {input_dir}")
    output_dir = Path(args.output).expanduser().resolve() if args.output else \
                 input_dir.parent / f"{input_dir.name}_整理后"
    print(f"📁 输出: {output_dir}")
    print(f"🔍 找到 {total} 个媒体文件")
    if not args.run:
        print("ℹ️  预览模式（加 --run 执行整理）")
    print()

    if total == 0:
        print("没有找到需要处理的文件。")
        return

    # MD5 去重
    print("── 第一步：MD5 去重 ──")
    t0 = time.time()
    hash_map = defaultdict(list)
    for i, fp in enumerate(files):
        fp_hash = md5_hash(fp)
        hash_map[fp_hash].append(fp)
        if (i + 1) % 100 == 0:
            print(f"  ⏳ {i+1}/{total}...")

    dup_groups = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    dup_count = sum(len(v) - 1 for v in dup_groups.values())
    dup_size = 0
    for h, paths in dup_groups.items():
        for p in paths[1:]:
            dup_size += os.path.getsize(p)

    print(f"\n  🔍 发现 {len(dup_groups)} 组重复文件")
    print(f"  ⏏️  可释放: {format_size(dup_size)}")

    if not args.run:
        print(f"\n── 预览结束（加 --run 执行整理）──")
        return

    # 执行整理
    output_dir.mkdir(parents=True, exist_ok=True)
    unique_files = [paths[0] for paths in hash_map.values()]

    month_map = defaultdict(list)
    unknown = []
    for fp in unique_files:
        dt = get_file_date(fp)
        if dt:
            month_map[f"{dt.year}/{dt.month:02d}"].append(fp)
        else:
            unknown.append(fp)

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

    deleted = 0
    deleted_size = 0
    if not args.no_cleanup:
        for h, paths in dup_groups.items():
            for p in paths[1:]:
                if p.exists():
                    deleted_size += os.path.getsize(p)
                    os.remove(p)
                    deleted += 1

    elapsed = time.time() - t0
    report = generate_report(input_dir, output_dir, total, copied,
                             deleted, deleted_size, month_map, unknown,
                             args.mode, elapsed)

    # 写报告
    report_path = output_dir / "整理报告.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n{report}")
    print(f"\n📄 报告: {report_path}")
    print(f"\n🎉 完成！")


# ══════════════════════════════════════
# GUI 界面（tkinter）
# ══════════════════════════════════════

class PhotoOrganizerGUI:
    """照片整理工具 GUI 界面"""

    def __init__(self, root):
        self.root = root
        self.root.title("📸 照片整理工具")
        self.root.geometry("780x620")
        self.root.resizable(False, False)
        self.root.configure(bg="#1A1B2F")

        self.input_dir = None
        self.output_dir = None
        self.running = False

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")

    def _set_style(self, widget, bg="#24243D", fg="#CCCCDD", font=("Microsoft YaHei", 10)):
        widget.configure(bg=bg, fg=fg, font=font)

    def _build_ui(self):
        # ── 标题 ──
        title = ttk.Label(self.root, text="📸 照片整理工具",
                          font=("Microsoft YaHei", 18, "bold"),
                          foreground="#FFFFFF", background="#1A1B2F")
        title.pack(pady=(20, 5))

        subtitle = ttk.Label(self.root, text="MD5 去重 · 按年月分类 · 自动生成报告",
                             font=("Microsoft YaHei", 10),
                             foreground="#888899", background="#1A1B2F")
        subtitle.pack(pady=(0, 20))

        # ── 主面板 ──
        frame = ttk.Frame(self.root)
        frame.configure(bg="#1A1B2F")
        frame.pack(fill="both", padx=30, pady=5)

        def make_card(parent):
            card = ttk.Frame(parent, borderwidth=0)
            card.configure(bg="#24243D")
            card.pack(fill="x", pady=6)
            return card

        # ── 输入目录 ──
        card1 = make_card(frame)
        ttk.Label(card1, text="📂 要整理的文件夹",
                  font=("Microsoft YaHei", 10, "bold"),
                  foreground="#06D6A0", background="#24243D").pack(anchor="w", padx=15, pady=(10, 5))

        input_row = ttk.Frame(card1)
        input_row.configure(bg="#24243D")
        input_row.pack(fill="x", padx=15, pady=(0, 10))

        self.input_var = ttk.Entry(input_row, font=("Microsoft YaHei", 10),
                                   foreground="#CCCCDD", background="#1E1F35")
        self.input_var.configure(style="TEntry")
        self.input_var.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        ttk.Button(input_row, text="选择文件夹",
                   command=self._pick_input).pack(side="right")

        # ── 输出目录 ──
        card2 = make_card(frame)
        ttk.Label(card2, text="📁 输出位置（可选）",
                  font=("Microsoft YaHei", 10, "bold"),
                  foreground="#7C3AED", background="#24243D").pack(anchor="w", padx=15, pady=(10, 5))

        output_row = ttk.Frame(card2)
        output_row.configure(bg="#24243D")
        output_row.pack(fill="x", padx=15, pady=(0, 10))

        self.output_var = ttk.Entry(output_row, font=("Microsoft YaHei", 10),
                                    foreground="#CCCCDD", background="#1E1F35")
        self.output_var.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        ttk.Button(output_row, text="选择文件夹",
                   command=self._pick_output).pack(side="right")

        # ── 选项 ──
        card3 = make_card(frame)
        ttk.Label(card3, text="⚙️ 选项",
                  font=("Microsoft YaHei", 10, "bold"),
                  foreground="#F79625", background="#24243D").pack(anchor="w", padx=15, pady=(10, 5))

        opts_row = ttk.Frame(card3)
        opts_row.configure(bg="#24243D")
        opts_row.pack(fill="x", padx=15, pady=(0, 12))

        self.mode_var = ttk.Combobox(opts_row, values=["复制 (copy)", "移动 (move)"],
                                     state="readonly", width=16,
                                     font=("Microsoft YaHei", 10))
        self.mode_var.set("复制 (copy)")
        self.mode_var.pack(side="left", padx=(0, 20))

        self.video_var = ttk.Checkbutton(opts_row, text="同时整理视频",
                                         style="TCheckbutton")
        self.video_var.pack(side="left", padx=(0, 20))

        self.cleanup_var = ttk.Checkbutton(opts_row, text="删除重复文件",
                                           style="TCheckbutton")
        self.cleanup_var.state(["selected"])
        self.cleanup_var.pack(side="left")

        # ── 操作按钮 ──
        btn_row = ttk.Frame(self.root)
        btn_row.configure(bg="#1A1B2F")
        btn_row.pack(pady=12)

        self.preview_btn = ttk.Button(btn_row, text="👁️ 预览",
                                      command=self._run_preview, width=14)
        self.preview_btn.pack(side="left", padx=5)

        self.run_btn = ttk.Button(btn_row, text="🚀 开始整理",
                                  command=self._run_organize, width=14)
        self.run_btn.pack(side="left", padx=5)

        # ── 日志区 ──
        log_card = ttk.Frame(self.root)
        log_card.configure(bg="#24243D")
        log_card.pack(fill="both", expand=True, padx=30, pady=(5, 15))

        ttk.Label(log_card, text="📋 执行日志",
                  font=("Microsoft YaHei", 10, "bold"),
                  foreground="#06D6A0", background="#24243D").pack(anchor="w", padx=15, pady=(8, 2))

        log_frame = ttk.Frame(log_card)
        log_frame.configure(bg="#1E1F35")
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")

        tk_text = ttk.Text(
            log_frame, font=("Menlo", 9),
            background="#1E1F35", foreground="#CCCCDD",
            wrap="word", state="disabled",
            yscrollcommand=scrollbar.set,
            borderwidth=0, padx=10, pady=10
        )
        tk_text.pack(fill="both", expand=True)
        scrollbar.config(command=tk_text.yview)

        # 进度条
        self.progress = ttk.Progressbar(self.root, mode="indeterminate", length=720)
        self.progress.pack(pady=(0, 10))

        # ── 样式配置 ──
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Microsoft YaHei", 10),
                        background="#7C3AED", foreground="#FFFFFF",
                        borderwidth=0, focusthickness=3, focuscolor="none")
        style.map("TButton",
                  background=[("active", "#6A2FD1"), ("pressed", "#5A27B8")])
        style.configure("TEntry", fieldbackground="#1E1F35",
                        foreground="#CCCCDD", borderwidth=0)
        style.configure("TCheckbutton", background="#24243D",
                        foreground="#CCCCDD", font=("Microsoft YaHei", 10))
        style.map("TCheckbutton",
                  background=[("active", "#24243D")])
        style.configure("TCombobox", fieldbackground="#1E1F35",
                        foreground="#CCCCDD", arrowcolor="#CCCCDD",
                        background="#24243D")
        style.configure("Horizontal.TProgressbar",
                        background="#06D6A0", troughcolor="#1E1F35",
                        borderwidth=0)

    def _log(self, text, color="#CCCCDD"):
        self.log_text.configure(state="normal")
        tag = f"color_{len(self.log_text.tag_names())}"
        self.log_text.tag_config(tag, foreground=color, font=("Menlo", 9))
        self.log_text.insert("end", text + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.root.update_idletasks()

    def _pick_input(self):
        d = filedialog.askdirectory(title="选择要整理的照片文件夹")
        if d:
            self.input_var.delete(0, "end")
            self.input_var.insert(0, d)

    def _pick_output(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_var.delete(0, "end")
            self.output_var.insert(0, d)

    def _get_mode(self):
        m = self.mode_var.get()
        return "move" if "move" in m.lower() else "copy"

    def _get_config(self):
        input_path = self.input_var.get().strip()
        if not input_path:
            messagebox.showwarning("提示", "请先选择要整理的照片文件夹")
            return None

        inp = Path(input_path).expanduser().resolve()
        if not inp.is_dir():
            messagebox.showerror("错误", f"目录不存在:\n{inp}")
            return None

        out = self.output_var.get().strip()
        output_dir = Path(out).expanduser().resolve() if out else \
                     inp.parent / f"{inp.name}_整理后"

        exts = IMAGE_EXTS | (VIDEO_EXTS if self.video_var.instate(["selected"]) else set())

        return {
            'input_dir': inp,
            'output_dir': output_dir,
            'exts': exts,
            'mode': self._get_mode(),
            'cleanup': self.cleanup_var.instate(["selected"]),
        }

    def _run_preview(self):
        config = self._get_config()
        if not config:
            return

        self._set_buttons_disabled(True)
        self._log("👁️ 预览模式 ── 仅扫描，不做任何修改\n", "#F79625")
        t = threading.Thread(target=self._do_preview, args=(config,), daemon=True)
        t.start()

    def _run_organize(self):
        config = self._get_config()
        if not config:
            return

        ok = messagebox.askyesno("确认",
                                  "将执行照片整理操作：\n"
                                  f"  输入: {config['input_dir']}\n"
                                  f"  输出: {config['output_dir']}\n"
                                  f"  模式: {'移动' if config['mode']=='move' else '复制'}\n\n"
                                  "确认执行？")
        if not ok:
            return

        self._set_buttons_disabled(True)
        self._log("🚀 开始整理 ...\n", "#06D6A0")
        t = threading.Thread(target=self._do_organize, args=(config,), daemon=True)
        t.start()

    def _set_buttons_disabled(self, disabled):
        state = "disabled" if disabled else "normal"
        self.preview_btn.configure(state=state)
        self.run_btn.configure(state=state)
        self.running = disabled

    def _do_preview(self, config):
        self.progress.start()
        t0 = time.time()
        try:
            files = collect_files(config['input_dir'], config['exts'])
            total = len(files)
            self._log(f"📂 扫描: {config['input_dir']}", "#FFFFFF")
            self._log(f"🔍 找到 {total} 个媒体文件", "#CCCCDD")

            if total == 0:
                self._log("没有找到需要处理的文件。", "#E94D4B")
                return

            self._log("", "")
            self._log("── 计算 MD5 哈希 ──", "#7C3AED")
            hash_map = defaultdict(list)
            for i, fp in enumerate(files):
                fp_hash = md5_hash(fp)
                hash_map[fp_hash].append(fp)
                if (i + 1) % 50 == 0:
                    self._log(f"  ⏳ {i+1}/{total}...", "#888899")

            dup_groups = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
            dup_count = sum(len(v) - 1 for v in dup_groups.values())
            dup_size = 0
            for h, paths in dup_groups.items():
                for p in paths[1:]:
                    dup_size += os.path.getsize(p)

            self._log(f"", "")
            self._log(f"🔍 发现 {len(dup_groups)} 组重复文件", "#F79625")
            for h, paths in sorted(dup_groups.items(), key=lambda x: -len(x[1])):
                self._log(f"  组: {len(paths)} 个完全相同 ({format_size(os.path.getsize(paths[0]))})",
                         "#888899")

            self._log(f"", "")
            self._log(f"  📊 预览结果", "#06D6A0")
            self._log(f"  文件总数: {total}", "#CCCCDD")
            self._log(f"  去重后:   {total - dup_count}", "#CCCCDD")
            self._log(f"  重复:     {dup_count} 个 ({format_size(dup_size)})", "#E94D4B")
            self._log(f"  耗时:     {time.time()-t0:.1f} 秒", "#888899")
            self._log(f"\n✅ 预览完成（可点击「开始整理」执行）", "#06D6A0")

        except Exception as e:
            self._log(f"❌ 错误: {e}", "#E94D4B")
        finally:
            self.progress.stop()
            self._set_buttons_disabled(False)

    def _do_organize(self, config):
        self.progress.start()
        t0 = time.time()
        try:
            inp = config['input_dir']
            out = config['output_dir']
            mode = config['mode']
            exts = config['exts']
            cleanup = config['cleanup']

            # 扫描
            self._log(f"📂 输入: {inp}", "#FFFFFF")
            files = collect_files(inp, exts)
            total = len(files)
            self._log(f"🔍 找到 {total} 个文件", "#CCCCDD")

            if total == 0:
                self._log("没有需要处理的文件。", "#E94D4B")
                return

            # MD5
            self._log(f"\n── MD5 去重 ──", "#7C3AED")
            hash_map = defaultdict(list)
            for i, fp in enumerate(files):
                fp_hash = md5_hash(fp)
                hash_map[fp_hash].append(fp)
                if (i + 1) % 50 == 0:
                    self._log(f"  ⏳ {i+1}/{total}...", "#888899")

            dup_groups = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
            dup_count = sum(len(v) - 1 for v in dup_groups.values())
            dup_size = 0
            for h, paths in dup_groups.items():
                for p in paths[1:]:
                    dup_size += os.path.getsize(p)

            self._log(f"  重复: {len(dup_groups)} 组, {dup_count} 个文件, {format_size(dup_size)}", "#F79625")

            # 分类
            self._log(f"\n── 按年月分类 ──", "#7C3AED")
            unique_files = [paths[0] for paths in hash_map.values()]
            out.mkdir(parents=True, exist_ok=True)

            month_map = defaultdict(list)
            unknown = []
            for fp in unique_files:
                dt = get_file_date(fp)
                if dt:
                    month_map[f"{dt.year}/{dt.month:02d}"].append(fp)
                else:
                    unknown.append(fp)

            for key in sorted(month_map.keys()):
                self._log(f"  📅 {key}: {len(month_map[key])} 个", "#CCCCDD")
            if unknown:
                self._log(f"  ❓ unknown: {len(unknown)} 个", "#888899")

            # 复制/移动
            self._log(f"\n── {'复制' if mode=='copy' else '移动'}到 {out} ──", "#7C3AED")
            copied = 0
            total_to_copy = len(unique_files)
            for key in sorted(month_map.keys()):
                target_dir = out / key
                target_dir.mkdir(parents=True, exist_ok=True)
                for fp in month_map[key]:
                    dest = target_dir / fp.name
                    if dest.exists():
                        stem, suffix = dest.stem, dest.suffix
                        c = 1
                        while (target_dir / f"{stem}_{c}{suffix}").exists():
                            c += 1
                        dest = target_dir / f"{stem}_{c}{suffix}"
                    if mode == 'copy':
                        shutil.copy2(fp, dest)
                    else:
                        shutil.move(str(fp), str(dest))
                    copied += 1
                    if copied % 50 == 0:
                        self._log(f"  ⏳ {copied}/{total_to_copy}...", "#888899")

            if unknown:
                udir = out / "unknown"
                udir.mkdir(exist_ok=True)
                for fp in unknown:
                    dest = udir / fp.name
                    if dest.exists():
                        stem, suffix = dest.stem, dest.suffix
                        c = 1
                        while (udir / f"{stem}_{c}{suffix}").exists():
                            c += 1
                        dest = udir / f"{stem}_{c}{suffix}"
                    if mode == 'copy':
                        shutil.copy2(fp, dest)
                    else:
                        shutil.move(str(fp), str(dest))
                    copied += 1

            # 删除重复
            deleted = 0
            deleted_size = 0
            if cleanup:
                self._log(f"\n── 删除重复文件 ──", "#E94D4B")
                for h, paths in dup_groups.items():
                    for p in paths[1:]:
                        if p.exists():
                            deleted_size += os.path.getsize(p)
                            os.remove(p)
                            deleted += 1
                self._log(f"  已删除 {deleted} 个重复文件, 释放 {format_size(deleted_size)}", "#06D6A0")

            elapsed = time.time() - t0

            # 报告
            report = generate_report(inp, out, total, copied,
                                     deleted, deleted_size, month_map,
                                     unknown, mode, elapsed)
            report_path = out / "整理报告.txt"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)

            # 输出结果
            self._log(f"\n{'='*40}", "#06D6A0")
            self._log(f"✅ 整理完成！", "#06D6A0")
            self._log(f"  原始文件: {total}", "#CCCCDD")
            self._log(f"  已整理:   {copied} 个文件", "#CCCCDD")
            if deleted:
                self._log(f"  删除重复: {deleted} 个（{format_size(deleted_size)}）", "#CCCCDD")
            self._log(f"  耗时:     {elapsed:.1f} 秒", "#CCCCDD")
            self._log(f"  输出:     {out}", "#06D6A0")
            self._log(f"  报告:     {report_path}", "#06D6A0")
            self._log(f"{'='*40}", "#06D6A0")

            # 弹窗提示
            dedup_msg = f"删除重复: {deleted} 个\n" if deleted else ""
            self.root.after(0, lambda: messagebox.showinfo(
                "整理完成",
                f"✅ 完成！\n\n已整理: {copied} 个文件\n"
                f"{dedup_msg}"
                f"输出位置: {out}\n"
                f"报告: {report_path}"
            ))

        except Exception as e:
            self._log(f"❌ 错误: {e}", "#E94D4B")
            import traceback
            self._log(traceback.format_exc(), "#888899")
        finally:
            self.progress.stop()
            self._set_buttons_disabled(False)


def run_gui():
    root = Tk()
    root.configure(bg="#1A1B2F")
    app = PhotoOrganizerGUI(root)
    root.mainloop()


# ══════════════════════════════════════
# 入口
# ══════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()
