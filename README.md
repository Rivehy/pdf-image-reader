# PDF Image Reader — Claude Skill

**PDF Image Reader** is a [Claude Code](https://claude.ai/code) skill that extracts text and images from PDF files, enabling Claude to visually understand PDF content through its multimodal capabilities.

## Features

- 🔍 **Auto-detect PDF type** — distinguishes scanned vs. text-based PDFs
- 📝 **OCR for scanned PDFs** — automatically splits large files and OCRs via MinerU
- 🖼️ **Render pages as images** — uses PyMuPDF to render each page as PNG
- 🤖 **Claude-native visual analysis** — Claude reads the rendered images directly
- ⚙️ **Adjustable quality** — control rendering DPI (150/200/300)
- 📦 **JSON output** — structured summary for easy programmatic use

## How It Works

```
Your PDF
   │
   ├─ Detect type ── Scanned → OCR (MinerU split + recognize)
   │                ── Text   → MinerU extract Markdown
   │
   ├─ PyMuPDF renders each page as PNG
   │
   └─ Output JSON manifest (text + page image paths)
            │
            └─ Claude reads images directly via Read tool
```

## Installation

### Prerequisites
- Claude Code
- Python 3.8+
- [MinerU skill](https://mineru.net) (for OCR/text extraction)

### Install as a Claude Skill

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/pdf-image-reader.git
# Copy to Claude skills directory
cp -r pdf-image-reader ~/.claude/skills/
# Install Python dependencies
pip install pymupdf pypdf
```

Or via the skill-install command in Claude Code.

## Usage

```bash
# Basic: auto-detect PDF type, render pages
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/

# Scanned PDF with OCR
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/ --ocr

# First 10 pages only (faster)
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/ --max-pages 10

# Higher quality (200 DPI)
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/ --dpi 200

# Text only, no image rendering
python "${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py" ./document.pdf --output ./output/ --no-render
```

## Output

```
output/
├── document.md           ← Extracted text / OCR result
├── pages/               ← Rendered page images
│   ├── page_0001.png
│   ├── page_0002.png
│   └── ...
└── ocr_markdown/        ← OCR intermediate files
```

The script outputs a JSON manifest with paths to all page images. Use Claude's `Read` tool to view any page image — Claude will understand the content directly.

## Dependencies

- `pymupdf` — page rendering
- `pypdf` — PDF splitting
- MinerU skill — OCR/text extraction (free API available)

## License

MIT
