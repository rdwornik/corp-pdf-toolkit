#!/usr/bin/env python3
"""PDF Anonymizer CLI - Anonymize PDFs using local Ollama LLM.

Optimized for CPU with 32GB RAM:
- Parallel chunk processing (3 concurrent)
- Model preloading to avoid cold starts
- Larger chunks to reduce LLM calls
"""

import argparse
import asyncio
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import httpx
import pdfplumber

# Global API keys (Documents/.secrets/.env)
_global_env = Path.home() / "Documents" / ".secrets" / ".env"
if _global_env.exists():
    load_dotenv(_global_env, override=False)

# Local .env (project-specific vars only)
load_dotenv(override=False)

from pdf_utils import (
    INPUT_DIR,
    OUTPUT_DIR,
    ARCHIVE_DIR,
    get_pdf_info,
    get_toc,
    filter_toc_by_depth,
    print_toc,
    print_info,
    parse_page_ranges,
    parse_chapter_selection,
    format_page_ranges,
    extract_pdf,
    get_pdf_files,
)

# Defaults
DEFAULT_MODEL = "qwen2.5:7b"
OLLAMA_URL = "http://localhost:11434"
CHUNK_SIZE = 3500  # Larger chunks = fewer LLM calls
TIMEOUT = 300.0
PARALLEL_CHUNKS = 3  # Process 3 chunks concurrently
KEEP_ALIVE = "60m"  # Keep model in RAM

SYSTEM_PROMPT = """You are a document anonymization expert. Your job is to replace sensitive information while preserving educational content.

REPLACE these with placeholders:
- Company names → [COMPANY], [CLIENT], [VENDOR], [PARTNER]
- Product/solution names → [PRODUCT], [SOLUTION], [PLATFORM]
- Person names → [PERSON], [EXECUTIVE], [MANAGER]
- Prices, costs, amounts → [PRICE], [COST], [AMOUNT]
- Revenue, financial figures → [REVENUE], [FINANCIAL]
- Percentages (if business-sensitive) → [PERCENTAGE]
- Specific dates → [DATE]
- Locations/addresses → [LOCATION]
- Email addresses → [EMAIL]
- Phone numbers → [PHONE]
- URLs, domains → [URL], [DOMAIN]

KEEP these intact:
- Technical definitions and terminology
- Process descriptions and methodologies
- Feature descriptions (make generic if needed)
- Architectural concepts
- Industry-standard terms
- Best practices
- Workflow explanations

Output ONLY the anonymized text. Keep the original structure and formatting."""

PLACEHOLDERS = {
    "[COMPANY]": "company/organization name",
    "[CLIENT]": "client company name",
    "[VENDOR]": "vendor/supplier name",
    "[PARTNER]": "partner company name",
    "[PRODUCT]": "product/solution name",
    "[SOLUTION]": "solution/service name",
    "[PLATFORM]": "platform name",
    "[PERSON]": "person name",
    "[EXECUTIVE]": "executive/leader name",
    "[MANAGER]": "manager name",
    "[PRICE]": "price/cost amount",
    "[COST]": "cost/expense amount",
    "[AMOUNT]": "monetary amount",
    "[REVENUE]": "revenue figure",
    "[FINANCIAL]": "financial data",
    "[PERCENTAGE]": "percentage value",
    "[DATE]": "specific date",
    "[LOCATION]": "location/address",
    "[EMAIL]": "email address",
    "[PHONE]": "phone number",
    "[URL]": "URL/web address",
    "[DOMAIN]": "domain name",
}


def get_chunks(pages: list[str], chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split pages into LLM-processable chunks."""
    chunks = []
    current = ""

    for page in pages:
        paragraphs = page.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) + 2 > chunk_size:
                if current:
                    chunks.append(current.strip())
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para

    if current:
        chunks.append(current.strip())

    return chunks


async def preload_model(client: httpx.AsyncClient, model: str) -> bool:
    """Preload model into RAM with keep_alive to avoid cold starts."""
    print(f"Preloading model {model} (keep_alive={KEEP_ALIVE})...", end=" ", flush=True)
    try:
        payload = {
            "model": model,
            "prompt": "",
            "keep_alive": KEEP_ALIVE,
        }
        response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        response.raise_for_status()
        print("ready")
        return True
    except Exception as e:
        print(f"warning: {e}")
        return False


async def anonymize_chunk(
    client: httpx.AsyncClient,
    chunk: str,
    model: str,
    chunk_idx: int,
    semaphore: asyncio.Semaphore,
) -> tuple[int, str]:
    """Anonymize a single text chunk via Ollama (with concurrency control)."""
    async with semaphore:
        prompt = f"""Anonymize the following text. Replace sensitive information with appropriate placeholders.

TEXT:
{chunk}

ANONYMIZED TEXT:"""

        payload = {
            "model": model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
        }

        response = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        response.raise_for_status()
        return chunk_idx, response.json()["response"]


async def process_pdf(
    pdf_path: Path,
    model: str,
    chunk_size: int,
    parallel: int,
    pages_str: str | None = None,
) -> dict:
    """Process a single PDF file with parallel chunk processing."""
    print(f"\n{'=' * 60}")
    print(f"Processing: {pdf_path.name}")
    print(f"Model: {model} | Chunk size: {chunk_size} | Parallel: {parallel}")
    print(f"{'=' * 60}")

    # Get total page count first for range parsing
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

    # Parse page ranges if specified
    page_indices = None
    if pages_str:
        page_indices = parse_page_ranges(pages_str, total_pages)
        if not page_indices:
            print(f"Error: Invalid page range '{pages_str}'")
            return None

    # Extract text
    pages, selected_count, total_count = extract_pdf(pdf_path, page_indices)

    if pages_str:
        # Show which pages are being processed
        ranges = format_page_ranges(page_indices)
        print(f"Processing pages {ranges} ({selected_count} of {total_count} total)")
    else:
        print(f"Pages: {total_count}")

    # Chunk text
    chunks = get_chunks(pages, chunk_size)
    total_chunks = len(chunks)
    print(f"Chunks: {total_chunks}")
    print()

    # Setup for parallel processing
    timeout = httpx.Timeout(TIMEOUT, connect=10.0)
    semaphore = asyncio.Semaphore(parallel)
    results: dict[int, str] = {}
    completed = 0

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Preload model
        await preload_model(client, model)

        # Create all tasks
        tasks = [
            anonymize_chunk(client, chunk, model, idx, semaphore)
            for idx, chunk in enumerate(chunks)
        ]

        # Process with progress reporting
        for coro in asyncio.as_completed(tasks):
            try:
                idx, result = await coro
                results[idx] = result
                completed += 1

                # Show which chunks are in progress
                in_progress = [
                    i + 1
                    for i in range(total_chunks)
                    if i not in results and i < completed + parallel
                ]
                if in_progress:
                    progress_str = (
                        f"{in_progress[0]}-{in_progress[-1]}"
                        if len(in_progress) > 1
                        else str(in_progress[0])
                    )
                    print(
                        f"  Chunk {progress_str}/{total_chunks} processing... ({completed} done)"
                    )
                else:
                    print(f"  Completed {completed}/{total_chunks}")

            except Exception as e:
                print(f"  ERROR: {e}")
                # Find which chunk failed and store error
                for idx, chunk in enumerate(chunks):
                    if idx not in results:
                        results[idx] = f"[ERROR PROCESSING CHUNK {idx + 1}]\n{chunk}"
                        break

    # Reassemble in order
    anonymized_chunks = [results[i] for i in range(total_chunks)]
    anonymized_text = "\n\n".join(anonymized_chunks)

    # Detect which placeholders were actually used
    used_placeholders = {k: v for k, v in PLACEHOLDERS.items() if k in anonymized_text}

    return {
        "source": pdf_path.name,
        "pages": selected_count,
        "total_pages": total_count,
        "pages_range": pages_str,
        "chunks": total_chunks,
        "model": model,
        "text": anonymized_text,
        "placeholders": used_placeholders,
    }


def save_output(result: dict) -> Path:
    """Save anonymized content as MD with YAML frontmatter."""
    stem = Path(result["source"]).stem
    output_path = OUTPUT_DIR / f"{stem}_anonymized.md"

    # Build YAML frontmatter
    lines = [
        "---",
        f'source: "{result["source"]}"',
        f"pages: {result['pages']}",
        f"model: {result['model']}",
        f"processed: {datetime.now().isoformat()}",
    ]

    # Add placeholders if any were used
    if result["placeholders"]:
        lines.append("placeholders:")
        for key, desc in result["placeholders"].items():
            # Remove brackets from key for cleaner YAML
            clean_key = key.strip("[]")
            lines.append(f"  {clean_key}: {desc}")

    lines.append("---")
    lines.append("")
    lines.append(result["text"])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


async def main():
    parser = argparse.ArgumentParser(
        description="Anonymize PDFs using local Ollama LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python anonymize.py                         # Process all PDFs in input/
  python anonymize.py doc.pdf                 # Process specific file
  python anonymize.py doc.pdf --toc           # Show chapters (depth 2)
  python anonymize.py doc.pdf --toc-depth 1   # Only main chapters
  python anonymize.py doc.pdf --chapters 1-4  # Chapters 1,2,3,4
  python anonymize.py doc.pdf --chapters 1-4,8-10  # Multiple ranges
  python anonymize.py doc.pdf --chapters 1,3,5-8   # Mix single and ranges
  python anonymize.py doc.pdf --pages 1-50,80-100  # Page ranges
  python anonymize.py doc.pdf --info          # Show PDF info
        """,
    )
    parser.add_argument("file", nargs="?", help="Specific PDF file to process")
    parser.add_argument("--pages", help="Page ranges (e.g., '1-50' or '1-20,50-60')")
    parser.add_argument(
        "--chapters", help="Chapter indices (e.g., '1-4' or '1-4,8-10' or '1,3,5-8')"
    )
    parser.add_argument("--toc", action="store_true", help="Show table of contents")
    parser.add_argument(
        "--toc-depth",
        type=int,
        default=2,
        help="TOC depth: 1=main, 2=+subsections (default: 2)",
    )
    parser.add_argument(
        "--info", action="store_true", help="Show PDF info without processing"
    )
    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULT_MODEL,
        help=f"Ollama model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--chunk-size",
        "-c",
        type=int,
        default=CHUNK_SIZE,
        help=f"Characters per chunk (default: {CHUNK_SIZE})",
    )
    parser.add_argument(
        "--parallel",
        "-p",
        type=int,
        default=PARALLEL_CHUNKS,
        help=f"Parallel chunks (default: {PARALLEL_CHUNKS})",
    )
    args = parser.parse_args()

    # Ensure directories exist
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Handle --info flag (no Ollama needed)
    if args.info:
        if not args.file:
            print("Error: --info requires a specific PDF file")
            print("Usage: python anonymize.py doc.pdf --info")
            return 1
        pdf_path = Path(args.file)
        if not pdf_path.exists():
            pdf_path = INPUT_DIR / args.file
        if not pdf_path.exists():
            print(f"Error: File not found: {args.file}")
            return 1
        info = get_pdf_info(pdf_path)
        print_info(info)
        return 0

    # Handle --toc flag (no Ollama needed)
    if args.toc:
        if not args.file:
            print("Error: --toc requires a specific PDF file")
            print("Usage: python anonymize.py doc.pdf --toc")
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
            # Show warning if few chapters detected
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

    # Check Ollama connection (only needed for processing)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            if args.model not in models:
                print(
                    f"Warning: Model '{args.model}' not found. Available: {', '.join(models)}"
                )
    except Exception:
        print(f"Error: Cannot connect to Ollama at {OLLAMA_URL}")
        print("Make sure Ollama is running: ollama serve")
        return 1

    # Get files to process
    pdf_files = get_pdf_files(args.file)
    if not pdf_files:
        return 1

    # Validate --pages and --chapters only work with single file
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
    pages_to_process = args.pages
    if args.chapters and pdf_files:
        pdf_path = pdf_files[0]
        toc = get_toc(pdf_path)
        if not toc:
            print(f"Error: No chapters detected in {pdf_path.name}")
            print(
                "Use --pages to select specific page ranges, or --toc to check structure."
            )
            return 1

        depth = args.toc_depth
        display_toc = filter_toc_by_depth(toc, depth)

        page_indices = parse_chapter_selection(args.chapters, toc, depth)
        if not page_indices:
            print(f"Error: Invalid chapter selection '{args.chapters}'")
            print(f"Available indices: 1-{len(display_toc)} (use --toc to see list)")
            return 1

        pages_to_process = format_page_ranges(page_indices)

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
            result = await process_pdf(
                pdf_path, args.model, args.chunk_size, args.parallel, pages_to_process
            )
            if result is None:
                continue
            output_path = save_output(result)
            print(f"\nOutput: {output_path}")

            # Archive
            ARCHIVE_DIR.mkdir(exist_ok=True)
            shutil.move(str(pdf_path), ARCHIVE_DIR / pdf_path.name)
            print(f"Archived: {ARCHIVE_DIR / pdf_path.name}")

        except Exception as e:
            print(f"\nError processing {pdf_path.name}: {e}")
            continue

    print(f"\n{'=' * 60}")
    print("Done!")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
