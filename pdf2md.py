#!/usr/bin/env python3
"""PDF to Markdown extractor — instant, no LLM required.

Extracts text from PDFs and saves as Markdown with frontmatter.
Supports TOC navigation, page/chapter selection, and PDF info display.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber

from pdf_utils import (
    INPUT_DIR, OUTPUT_DIR, get_pdf_files, get_pdf_info, get_toc,
    filter_toc_by_depth, print_toc, print_info,
    parse_page_ranges, parse_chapter_selection, format_page_ranges,
    extract_pdf,
)


def save_markdown(source: str, pages: list[str], total_pages: int,
                  pages_selected: str | None = None) -> Path:
    """Save extracted text as Markdown with frontmatter."""
    stem = Path(source).stem
    output_path = OUTPUT_DIR / f"{stem}.md"

    lines = [
        "---",
        f'source: "{source}"',
        f"pages: {total_pages}",
        f"extracted: {datetime.now().isoformat()}",
    ]

    if pages_selected:
        lines.append(f'pages_selected: "{pages_selected}"')

    lines.append("---")
    lines.append("")
    lines.append("\n\n".join(pages))

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Extract PDF text to Markdown — instant, no LLM required",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf2md.py                          # Extract all PDFs in input/
  python pdf2md.py doc.pdf                  # Extract specific file
  python pdf2md.py doc.pdf --toc            # Show chapters (depth 2)
  python pdf2md.py doc.pdf --toc-depth 1    # Only main chapters
  python pdf2md.py doc.pdf --chapters 1-4   # Chapters 1,2,3,4
  python pdf2md.py doc.pdf --chapters 1-4,8-10  # Multiple ranges
  python pdf2md.py doc.pdf --pages 1-50,80-100  # Page ranges
  python pdf2md.py doc.pdf --info           # Show PDF info
        """,
    )
    parser.add_argument("file", nargs="?", help="Specific PDF file to process")
    parser.add_argument("--pages", help="Page ranges (e.g., '1-50' or '1-20,50-60')")
    parser.add_argument("--chapters", help="Chapter indices (e.g., '1-4' or '1-4,8-10')")
    parser.add_argument("--toc", action="store_true", help="Show table of contents")
    parser.add_argument("--toc-depth", type=int, default=2, help="TOC depth: 1=main, 2=+subsections (default: 2)")
    parser.add_argument("--info", action="store_true", help="Show PDF info without processing")
    args = parser.parse_args()

    # Ensure directories exist
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Handle --info
    if args.info:
        if not args.file:
            print("Error: --info requires a specific PDF file")
            print("Usage: python pdf2md.py doc.pdf --info")
            return 1
        pdf_path = Path(args.file)
        if not pdf_path.exists():
            pdf_path = INPUT_DIR / args.file
        if not pdf_path.exists():
            print(f"Error: File not found: {args.file}")
            return 1
        print_info(get_pdf_info(pdf_path))
        return 0

    # Handle --toc
    if args.toc:
        if not args.file:
            print("Error: --toc requires a specific PDF file")
            print("Usage: python pdf2md.py doc.pdf --toc")
            return 1
        pdf_path = Path(args.file)
        if not pdf_path.exists():
            pdf_path = INPUT_DIR / args.file
        if not pdf_path.exists():
            print(f"Error: File not found: {args.file}")
            return 1
        toc = get_toc(pdf_path)
        if toc:
            depth = args.toc_depth
            print_toc(toc, show_usage=True, depth=depth, filename=pdf_path.name)
            display_toc = filter_toc_by_depth(toc, depth)
            top_level = [e for e in display_toc if e.get("level", 0) == 0]
            if len(top_level) < 3:
                print(f"\nWarning: Only {len(top_level)} top-level chapters detected.")
                print("TOC parsing may be incomplete. Consider using --pages instead.")
        else:
            print(f"\nNo chapters detected in {pdf_path.name}")
            print("Use --pages to select specific page ranges.")
            info = get_pdf_info(pdf_path)
            print(f"Total pages: {info['pages']}")
        return 0

    # Get files to process
    pdf_files = get_pdf_files(args.file)
    if not pdf_files:
        return 1

    # Validate flags
    if args.pages and len(pdf_files) > 1:
        print("Error: --pages can only be used with a single PDF file")
        return 1
    if args.chapters and len(pdf_files) > 1:
        print("Error: --chapters can only be used with a single PDF file")
        return 1
    if args.chapters and args.pages:
        print("Error: Cannot use both --chapters and --pages")
        return 1

    # Convert --chapters to page ranges
    pages_str = args.pages
    if args.chapters and pdf_files:
        pdf_path = pdf_files[0]
        toc = get_toc(pdf_path)
        if not toc:
            print(f"Error: No chapters detected in {pdf_path.name}")
            print("Use --pages to select specific page ranges, or --toc to check structure.")
            return 1

        depth = args.toc_depth
        display_toc = filter_toc_by_depth(toc, depth)

        page_indices = parse_chapter_selection(args.chapters, toc, depth)
        if not page_indices:
            print(f"Error: Invalid chapter selection '{args.chapters}'")
            print(f"Available indices: 1-{len(display_toc)} (use --toc to see list)")
            return 1

        pages_str = format_page_ranges(page_indices)

        # Show which chapters will be processed
        selected_indices = []
        for part in args.chapters.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                selected_indices.extend(range(int(start), int(end) + 1))
            else:
                selected_indices.append(int(part))

        chapter_names = []
        for idx in selected_indices:
            if 1 <= idx <= len(display_toc):
                entry = display_toc[idx - 1]
                title = entry["title"][:40]
                if entry.get("numbering") and not title.startswith(entry["numbering"]):
                    title = f"{entry['numbering']}. {title}"
                chapter_names.append(title)

        print(f"Selected: {', '.join(chapter_names)}")

    # Process each PDF
    for pdf_path in pdf_files:
        try:
            # Get total pages for range parsing
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

            # Parse page ranges
            page_indices = None
            if pages_str:
                page_indices = parse_page_ranges(pages_str, total_pages)
                if not page_indices:
                    print(f"Error: Invalid page range '{pages_str}'")
                    continue

            # Extract
            pages, selected_count, total_count = extract_pdf(pdf_path, page_indices)

            if page_indices is not None:
                ranges = format_page_ranges(page_indices)
                print(f"Extracting {pdf_path.name}: pages {ranges} ({selected_count} of {total_count})")
            else:
                print(f"Extracting {pdf_path.name}: {total_count} pages")

            # Progress
            for i in range(len(pages)):
                print(f"\r  Extracting page {i + 1}/{len(pages)}...", end="", flush=True)
            print(f"\r  Extracted {len(pages)} pages.          ")

            # Save
            pages_selected = format_page_ranges(page_indices) if page_indices else None
            output_path = save_markdown(pdf_path.name, pages, total_count, pages_selected)
            print(f"  Output: {output_path}")

        except Exception as e:
            print(f"\nError processing {pdf_path.name}: {e}")
            continue

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
