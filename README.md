# 📸📄 文件整理工具 file-organizer

纯 Python 标准库实现的文件整理工具，**无需任何第三方依赖**。
支持照片按年月分类、文档按类型分类、MD5 去重、GUI 图形界面。

---

## ✨ 功能

### 🔧 双模式

| 模式 | 适用文件 | 分类方式 |
|------|----------|----------|
| 📸 **照片整理** | 图片 (jpg/png/gif/bmp/webp/heic) + 可选视频 | 按日期 → `2026/05/` 文件夹 |
| 📄 **文档整理** | PDF/Word/Excel/PPT/文本/数据文件 | 按类型 → `PDF/`、`Word/`、`Excel/` 等 |

### 🎯 核心能力

- 🔍 **递归扫描** 目录下所有文件
- 🆔 **MD5 去重** — 完全相同文件只保留一份，释放磁盘空间
- 📂 **自动分类** — 照片按年月、文档按类型自动归类
- 👁️ **预览模式** — 先看结果再动手，安全放心
- 🚚 **复制/移动** — 可选保留原文件或直接移动
- 🖥️ **GUI 界面** — 深色主题，双击即用
- 📋 **自动报告** — 整理完成后生成 `整理报告.txt`

### 📄 支持的文档格式

| 分类 | 扩展名 |
|------|--------|
| PDF | `.pdf` |
| Word | `.doc` `.docx` `.rtf` `.odt` |
| Excel | `.xls` `.xlsx` `.csv` `.ods` |
| PPT | `.ppt` `.pptx` `.odp` |
| 文本 | `.txt` `.md` |
| 数据 | `.json` `.xml` `.yaml` `.yml` |

---

## 🚀 用法

### GUI 界面（推荐）

```bash
# 双击运行，或
python3 file_organizer.py
```

弹出窗口后：
1. 顶部下拉选择 **照片整理** 或 **文档整理**
2. 点击「选择文件夹」选源目录
3. 可选输出位置（不选自动创建）
4. 点 **👁️ 预览** 看看结果
5. 满意后点 **🚀 开始整理**

### 命令行

```bash
# ── 照片整理 ──

# 预览（不执行）
python3 file_organizer.py ~/Pictures -t photo

# 执行整理（复制模式，默认）
python3 file_organizer.py ~/Pictures -t photo --run

# 移动模式 + 同时整理视频
python3 file_organizer.py ~/Pictures -t photo --run --mode move --include-video

# 指定输出目录
python3 file_organizer.py ~/Pictures -t photo --run --output ~/整理好的照片


# ── 文档整理 ──

# 预览
python3 file_organizer.py ~/Downloads -t doc

# 执行整理
python3 file_organizer.py ~/Downloads -t doc --run

# 移动模式
python3 file_organizer.py ~/Downloads -t doc --run --mode move
```

---

## ⚙️ 命令行参数

| 参数 | 说明 |
|------|------|
| `input_dir` | 要整理的目录（留空启动 GUI） |
| `-t / --type` | 整理类型：`photo`（默认）或 `doc` |
| `--run` | 执行整理（不加则仅预览） |
| `-o / --output` | 输出目录（默认自动创建） |
| `--mode` | `copy`（默认）或 `move` |
| `--include-video` | 照片模式同时整理视频 |
| `--no-cleanup` | 找出重复但不删除 |
| `--gui` | 强制启动 GUI 界面 |

---

## 📂 输出结构示例

### 照片模式
```
📁 输入文件夹_照片整理/
├── 📅 2024/
│   ├── 10/  ← 2024年10月的照片
│   └── 11/  ← 2024年11月的照片
├── 📅 2025/
│   ├── 01/
│   └── 03/
├── ❓ unknown/  ← 无法确定日期的文件
└── 📄 整理报告.txt
```

### 文档模式
```
📁 输入文件夹_文档整理/
├── 📄 PDF/       ← 所有 .pdf 文件
├── 📄 Word/      ← .doc .docx .rtf
├── 📄 Excel/     ← .xls .xlsx .csv
├── 📄 PPT/       ← .ppt .pptx
├── 📄 文本/      ← .txt .md
├── 📄 数据/      ← .json .xml .yaml
└── 📄 整理报告.txt
```

---

## 📊 整理报告示例

```
📸 照片整理报告
═══════════════════════════════════════

扫描目录: /Volumes/U盘/生日会
输出目录: ~/Desktop/生日会_整理后
模式: 复制
耗时: 8.3 秒
时间: 2026-05-20 22:30:00

原始文件: 179
去重后: 168
已整理: 168
删除重复: 11 (78.1MB)

按年月分布:
  📅 2024/10: 161 个文件
  📅 2024/11: 27 个文件
```

---

## 🛠️ 技术细节

- **语言**: Python 3.6+
- **依赖**: 零第三方依赖（仅用标准库：`os` `hashlib` `shutil` `tkinter` 等）
- **去重算法**: MD5 分块哈希（每块 64KB），高效处理大文件
- **日期提取**: 先从文件名正则匹配（支持多种日期格式），失败则用文件修改时间
- **GUI**: tkinter 原生界面，深色主题

---

## 📦 文件清单

| 文件 | 说明 |
|------|------|
| `file_organizer.py` | 主程序（含 GUI + CLI，双模式） |
| `photo_organizer.py` | 旧版单模式（保留兼容） |
| `README.md` | 本说明文档 |
| `.gitignore` | Git 忽略规则 |
