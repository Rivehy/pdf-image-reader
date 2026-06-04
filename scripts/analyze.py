#!/usr/bin/env python3
"""PDF Analyzer — Parse PDFs (text or scanned) to extract text + page images.

For scanned PDFs: renders each page as an image using PyMuPDF, uses MinerU for OCR.
For text PDFs: uses MinerU to extract Markdown, then scans for image references.
All page images are saved for Claude's visual analysis.

Outputs JSON with:
  - text: OCR/Markdown extracted text
  - pages: list of rendered page images with paths
  - images: embedded image references (from text PDFs)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IMG_REF = re.compile(r'(!\[([^\]]*)\])\s*\(\s*([^)\s]+)\s*\)')
DATA_URI = re.compile(r'data:image/(png|jpeg|jpg|gif|webp|bmp);base64,')
IMG_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.svg'}


def find_mineru() -> Path:
    script = Path(__file__).resolve().parent.parent.parent / "mineru" / "scripts" / "mineru.py"
    if script.exists():
        return script
    for p in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(p) / "mineru.py"
        if candidate.exists():
            return candidate
    print("Warning: mineru.py not found — OCR/extraction will be skipped.", file=sys.stderr)
    return None


def detect_pdf_type(pdf_path: Path) -> str:
    """Detect whether a PDF is scanned (image-based) or text-based."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        total_text = 0
        total_images = 0
        for page in reader.pages[:5]:
            total_text += len(page.extract_text() or "")
            total_images += len(page.images)
        if total_text > 100:
            return "text"
        elif total_images > 10:
            return "scanned"
        else:
            return "unknown"
    except Exception:
        return "unknown"


def render_pages(pdf_path: Path, output_dir: Path, max_pages: int = 0,
                 dpi: int = 150) -> list[dict]:
    """Render PDF pages as PNG images using PyMuPDF. Returns list of page info."""
    try:
        import fitz
    except ImportError:
        print("Error: PyMuPDF not installed. Install with: pip install pymupdf", file=sys.stderr)
        return []

    doc = fitz.open(str(pdf_path))
    total = doc.page_count
    if max_pages > 0:
        total = min(total, max_pages)

    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    scale = dpi / 72  # 72 is default PDF DPI
    matrix = fitz.Matrix(scale, scale)

    page_list = []
    for i in range(total):
        page = doc[i]
        pix = page.get_pixmap(matrix=matrix)
        fname = f"page_{i+1:04d}.png"
        path = pages_dir / fname
        pix.save(str(path))
        size_kb = os.path.getsize(path) / 1024
        page_list.append({
            "page": i + 1,
            "path": str(path.resolve()),
            "size_kb": round(size_kb, 1),
            "width": pix.width,
            "height": pix.height,
        })

    doc.close()
    return page_list


def split_and_ocr(pdf_path: Path, output_dir: Path, mineru: Path,
                  lang: str = "ch", chunk_pages: int = 5) -> str:
    """Split PDF into small chunks and run MinerU OCR on each."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)

    md_dir = output_dir / "ocr_markdown"
    md_dir.mkdir(parents=True, exist_ok=True)

    all_text_parts = []

    for start in range(0, total, chunk_pages):
        end = min(start + chunk_pages, total)
        writer = PdfWriter()
        for p in range(start, end):
            writer.add_page(reader.pages[p])

        chunk_name = f"chunk_{start+1}-{end}"
        chunk_path = md_dir / f"{chunk_name}.pdf"
        with open(str(chunk_path), "wb") as f:
            writer.write(f)

        # Check file size (Agent API limit: 10 MB)
        fsize_mb = os.path.getsize(chunk_path) / (1024 * 1024)
        if fsize_mb > 9:
            print(f"  [WARN] {chunk_name} is {fsize_mb:.1f}MB — reducing chunk size", file=sys.stderr)
            continue

        print(f"  OCR: {chunk_name} ({end-start}pages, {fsize_mb:.1f}MB) …", file=sys.stderr)
        cmd = [sys.executable, str(mineru), str(chunk_path), "--ocr", "--lang", lang, "--stdout"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if proc.returncode == 0 and proc.stdout.strip():
            all_text_parts.append(f"\n\n## Pages {start+1}-{end}\n\n{proc.stdout.strip()}")
        else:
            err = proc.stderr.strip() or "no output"
            print(f"  [WARN] {chunk_name} OCR failed: {err[:200]}", file=sys.stderr)
            all_text_parts.append(f"\n\n## Pages {start+1}-{end}\n\n[OCR failed: {err[:100]}]")

        # Clean up chunk file
        try:
            chunk_path.unlink()
        except OSError:
            pass

    merged = "\n\n---\n\n".join(all_text_parts)
    return merged


def run_mineru_extract(pdf_path: Path, output_dir: Path, mineru: Path,
                       lang: str = "ch", ocr: bool = False) -> str | None:
    """Run MinerU to extract text from a text-based PDF."""
    cmd = [sys.executable, str(mineru), str(pdf_path), "--output", str(output_dir),
           "--lang", lang, "--stdout"]
    if ocr:
        cmd.append("--ocr")

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()

    # Check stderr
    stderr = proc.stderr or ""
    if "Pages exceed Agent API 20-page limit" in stderr or "File exceeds Agent API 10 MB limit" in stderr:
        print(f"  MinerU: file too large for free API, trying split+OCR …", file=sys.stderr)
        return split_and_ocr(pdf_path, output_dir, mineru, lang=lang)

    print(f"  MinerU: failed — {stderr[:300]}", file=sys.stderr)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze PDF: extract text + render pages as images for Claude's visual analysis."
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--output", "-o", help="Output directory (default: temp dir)")
    parser.add_argument("--ocr", action="store_true", help="Force OCR mode")
    parser.add_argument("--lang", default="ch", help="Document language (default: ch)")
    parser.add_argument("--max-pages", type=int, default=0,
                        help="Max pages to process (0 = all)")
    parser.add_argument("--dpi", type=int, default=150,
                        help="DPI for page rendering (default: 150)")
    parser.add_argument("--no-render", action="store_true",
                        help="Skip page rendering (text only)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Output directory
    out_dir = Path(args.output).resolve() if args.output else Path(
        tempfile.mkdtemp(prefix="pdf_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    mineru = find_mineru()
    stem = pdf_path.stem

    # Step 1 — Detect PDF type
    pdf_type = detect_pdf_type(pdf_path)
    print(f"[Detect] PDF type: {pdf_type}", file=sys.stderr)

    if args.ocr:
        pdf_type = "scanned"

    # Step 2 — Extract text
    extracted_text = ""
    if mineru:
        print(f"[1/4] Extracting text …", file=sys.stderr)
        if pdf_type in ("scanned", "unknown"):
            extracted_text = split_and_ocr(pdf_path, out_dir, mineru, lang=args.lang)
        else:
            result = run_mineru_extract(pdf_path, out_dir, mineru, lang=args.lang)
            if result:
                extracted_text = result

    if extracted_text:
        md_path = out_dir / f"{stem}.md"
        md_path.write_text(extracted_text, encoding="utf-8")
        print(f"  ✓ Text saved to: {md_path}", file=sys.stderr)
    else:
        print(f"  ⚠ No text extracted", file=sys.stderr)

    # Step 3 — Render pages as images
    page_images = []
    if not args.no_render:
        print(f"[2/4] Rendering pages as images …", file=sys.stderr)
        page_images = render_pages(pdf_path, out_dir, max_pages=args.max_pages, dpi=args.dpi)
        print(f"  ✓ Rendered {len(page_images)} pages", file=sys.stderr)

    # Step 4 — Scan Markdown for embedded image references
    embedded_images = []
    if extracted_text:
        print(f"[3/4] Scanning for embedded images …", file=sys.stderr)
        lines = extracted_text.split("\n")
        for i, line in enumerate(lines):
            for match in IMG_REF.finditer(line):
                alt_text = match.group(2).strip()
                img_ref = match.group(3).strip()
                embedded_images.append({
                    "alt": alt_text,
                    "reference": img_ref,
                    "line": i,
                })

    # Step 5 — Output JSON summary
    print(f"[4/4] Summary output …", file=sys.stderr)

    output = {
        "pdf": str(pdf_path),
        "type": pdf_type,
        "output_dir": str(out_dir.resolve()),
        "markdown_path": str((out_dir / f"{stem}.md").resolve()) if extracted_text else None,
        "text_length": len(extracted_text) if extracted_text else 0,
        "pages_rendered": len(page_images),
        "page_images": page_images,
        "embedded_images": embedded_images,
        "has_content": len(extracted_text) > 0 or len(page_images) > 0,
        "note": ("Use Claude's Read tool on the page_images paths; "
                 "Claude can directly understand the image content"),
    }

    json_text = json.dumps(output, ensure_ascii=False, indent=2)
    print(json_text)


if __name__ == "__main__":
    main()
