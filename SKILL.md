---
name: pdf-image-reader
description: 解析 PDF 文件（文字版和扫描版），提取文字内容并渲染每一页为图片，供 Claude 多模态视觉识别。支持 OCR、自动拆分大文件、页面渲染。
metadata:
  author: Claude
  version: "2.0.0"
  argument-hint: <pdf-file>
---

# PDF Image Reader

解析 PDF 文件，提取文字 + 将每页渲染为图片，让 Claude 直接「看懂」PDF 里的内容。

## 工作流程

```
你的 PDF 文件
    │
    ├─ 自动检测类型 ── 扫描版 → OCR（MinerU 拆分+识别）
    │                 ── 文字版 → MinerU 提取 Markdown
    │
    ├─ PyMuPDF 渲染每页为 PNG 图片（可调节 DPI）
    │
    └─ 输出 JSON 清单（文字 + 页面图片路径）
             │
             └─ Claude 用 Read 工具看图 → 分析内容
```

## 使用方法

```bash
# 基础用法（自动检测 PDF 类型）
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/

# 扫描版 PDF 强制 OCR
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/ --ocr

# 只渲染前 10 页（速度快）
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/ --max-pages 10

# 用更高清晰度渲染（200 DPI）
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/ --dpi 200

# 只提取文字，不渲染图片
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/ --no-render
```

## 输出目录结构

```
output/
├── 文档名.md            ← 提取的文字 / OCR 结果
├── pages/              ← 渲染的页面图片（Claude 可直接识别）
│   ├── page_0001.png
│   ├── page_0002.png
│   └── ...
└── ocr_markdown/       ← OCR 中间文件
```

## 输出 JSON 字段

| 字段 | 说明 |
|------|------|
| `pdf` | PDF 路径 |
| `type` | PDF 类型: text / scanned / unknown |
| `output_dir` | 输出目录 |
| `markdown_path` | 提取文字的 Markdown 文件路径 |
| `text_length` | 提取的文字长度 |
| `pages_rendered` | 渲染的图片数量 |
| `page_images` | 每页图片的路径、尺寸、大小 |
| `embedded_images` | PDF 中嵌入的图片引用 |
| `has_content` | 是否有内容 |

## 功能特性

- **自动检测 PDF 类型**：区分扫描版和文字版 PDF
- **大文件自动拆分**：超过免费 API 限制时自动拆分处理
- **OCR 识别**：扫描版 PDF 自动 OCR（中文支持）
- **页面渲染**：PyMuPDF 渲染每页为 PNG，Claude 可直接识别
- **可调清晰度**：通过 `--dpi` 控制渲染质量

## 依赖

- Python 3.8+
- PyMuPDF (`pip install pymupdf`)
- MinerU skill（用于文字提取/OCR）
- pypdf（用于 PDF 拆分）
