"""Shared PDF utilities for pdf-anonymizer tools.

Provides TOC parsing, page selection, text extraction, and file resolution
used by both anonymize.py and pdf2md.py.
"""

import re
from pathlib import Path

import pdfplumber

# Try to import pypdf for TOC support
try:
    from pypdf import PdfReader

    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

# Directories
SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR / "input"
OUTPUT_DIR = SCRIPT_DIR / "output"
ARCHIVE_DIR = INPUT_DIR / "archive"


# ---------------------------------------------------------------------------
# PDF info
# ---------------------------------------------------------------------------


def count_outline_entries(outlines, count=0) -> int:
    """Recursively count outline entries."""
    for item in outlines:
        if isinstance(item, list):
            count = count_outline_entries(item, count)
        else:
            count += 1
    return count


def get_pdf_info(file_path: Path) -> dict:
    """Get basic PDF info without processing."""
    file_size = file_path.stat().st_size
    size_mb = file_size / (1024 * 1024)

    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        metadata = pdf.metadata or {}

    has_toc = False
    toc_entries = 0
    if HAS_PYPDF:
        try:
            reader = PdfReader(str(file_path))
            outlines = reader.outline
            if outlines:
                has_toc = True
                toc_entries = count_outline_entries(outlines)
        except Exception:
            pass

    return {
        "file": file_path.name,
        "pages": page_count,
        "size_mb": round(size_mb, 2),
        "has_toc": has_toc,
        "toc_entries": toc_entries,
        "metadata": metadata,
    }


def print_info(info: dict):
    """Print PDF info in readable format."""
    print(f"\nFile: {info['file']}")
    print(f"Pages: {info['pages']}")
    print(f"Size: {info['size_mb']} MB")
    print(f"Has TOC: {'Yes' if info['has_toc'] else 'No'}", end="")
    if info["has_toc"]:
        print(f" ({info['toc_entries']} entries)")
    else:
        print()

    if info["metadata"]:
        print("\nMetadata:")
        for key, value in info["metadata"].items():
            if value:
                print(f"  {key}: {value}")


# ---------------------------------------------------------------------------
# TOC extraction
# ---------------------------------------------------------------------------


def get_toc(file_path: Path, total_pages: int | None = None) -> list[dict] | None:
    """Extract table of contents from PDF. Priority: 1) PDF outlines, 2) TOC page parsing."""
    if total_pages is None:
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

    # Try PDF outlines first (with validation)
    if HAS_PYPDF:
        toc = _get_toc_from_outlines(file_path, total_pages)
        if toc and _validate_toc(toc, total_pages):
            _calculate_page_ranges(toc, total_pages)
            _detect_hierarchy_levels(toc)
            return toc

    # Fallback: parse actual TOC page
    toc = _get_toc_from_toc_page(file_path, total_pages)
    if toc and _validate_toc(toc, total_pages):
        _calculate_page_ranges(toc, total_pages)
        return toc

    return None


def _get_toc_from_outlines(file_path: Path, total_pages: int) -> list[dict] | None:
    """Extract TOC from PDF bookmarks/outlines using pypdf."""
    try:
        reader = PdfReader(str(file_path))
        outlines = reader.outline
        if not outlines:
            return None

        toc = []
        _extract_outline_entries(
            reader, outlines, toc, level=0, total_pages=total_pages
        )
        return toc if toc else None
    except Exception:
        return None


def _extract_outline_entries(
    reader: "PdfReader", outlines, toc: list, level: int, total_pages: int
):
    """Recursively extract outline entries with page numbers."""
    for item in outlines:
        if isinstance(item, list):
            _extract_outline_entries(reader, item, toc, level + 1, total_pages)
        else:
            try:
                title = item.title if hasattr(item, "title") else str(item)

                # Skip garbage titles (too long, empty, or looks like content)
                if not title or len(title) > 80 or title.count(" ") > 15:
                    continue

                # Get page number
                page_num = None
                if hasattr(item, "page") and item.page is not None:
                    try:
                        page_num = reader.get_destination_page_number(item) + 1
                        if page_num < 1 or page_num > total_pages:
                            page_num = None
                    except Exception:
                        pass

                toc.append(
                    {
                        "title": title.strip(),
                        "page": page_num,
                        "level": level,
                        "numbering": _extract_numbering(title),
                    }
                )
            except Exception:
                continue


def _get_toc_from_toc_page(file_path: Path, total_pages: int) -> list[dict] | None:
    """Parse actual TOC page looking for 'title.....page' patterns."""
    toc = []

    toc_page_markers = [
        r"table\s+of\s+contents",
        r"contents",
        r"spis\s+treści",
        r"inhalt",
        r"índice",
    ]
    toc_marker_pattern = "|".join(toc_page_markers)

    toc_entry_patterns = [
        r"^(\d+(?:\.\d+)*\.?)\s+(.+?)\s*\.{2,}\s*(\d+)\s*$",
        r"^(.+?)\s*\.{2,}\s*(\d+)\s*$",
        r"^(\d+(?:\.\d+)*\.?)\s+(.+?)\s{3,}(\d+)\s*$",
        r"^(.+?)\s{3,}(\d+)\s*$",
    ]

    with pdfplumber.open(file_path) as pdf:
        toc_page_found = False
        pages_to_check = min(10, len(pdf.pages))

        for page_idx in range(pages_to_check):
            page = pdf.pages[page_idx]
            text = page.extract_text() or ""
            lines = text.split("\n")

            page_text_lower = text.lower()
            if re.search(toc_marker_pattern, page_text_lower):
                toc_page_found = True

            if not toc_page_found:
                continue

            for line in lines:
                line = line.strip()
                if not line or len(line) < 5:
                    continue

                if re.match(toc_marker_pattern, line.lower()):
                    continue

                for pattern in toc_entry_patterns:
                    match = re.match(pattern, line)
                    if match:
                        groups = match.groups()

                        if len(groups) == 3:
                            numbering, title, page_str = groups
                        else:
                            title, page_str = groups
                            numbering = None

                        try:
                            page_num = int(page_str)
                        except ValueError:
                            continue

                        title = title.strip()
                        if len(title) > 80 or page_num > total_pages or page_num < 1:
                            continue

                        level = 0
                        if numbering:
                            numbering = numbering.strip().rstrip(".")
                            level = numbering.count(".")

                        if any(
                            e["title"] == title and e["page"] == page_num for e in toc
                        ):
                            continue

                        toc.append(
                            {
                                "title": title,
                                "page": page_num,
                                "level": level,
                                "numbering": numbering,
                            }
                        )
                        break

            if toc_page_found and len(toc) > 0:
                entries_on_page = sum(
                    1
                    for line in lines
                    if any(re.match(p, line.strip()) for p in toc_entry_patterns)
                )
                if entries_on_page == 0 and page_idx > 0:
                    break

    return toc if len(toc) >= 2 else None


def _extract_numbering(title: str) -> str | None:
    """Extract chapter numbering from title (e.g., '1.', '1.1', '2.3.1')."""
    match = re.match(r"^(\d+(?:\.\d+)*\.?)\s", title)
    if match:
        return match.group(1).rstrip(".")
    return None


def _detect_hierarchy_levels(toc: list[dict]):
    """Detect hierarchy levels from numbering patterns."""
    for entry in toc:
        if entry.get("numbering"):
            entry["level"] = entry["numbering"].count(".")


def _validate_toc(toc: list[dict], total_pages: int) -> bool:
    """Validate TOC entries - reject garbage."""
    if not toc or len(toc) < 2:
        return False

    valid_entries = 0
    for entry in toc:
        title = entry.get("title", "")
        page = entry.get("page")

        if len(title) > 80:
            continue
        if title.count(" ") > 15:
            continue

        if page is not None and (page < 1 or page > total_pages):
            continue

        valid_entries += 1

    return valid_entries >= len(toc) * 0.6 and valid_entries >= 2


def _calculate_page_ranges(toc: list[dict], total_pages: int):
    """Calculate end_page for each TOC entry based on next entry's start."""
    toc_with_pages = [(i, e) for i, e in enumerate(toc) if e.get("page")]
    toc_with_pages.sort(key=lambda x: x[1]["page"])

    for idx, (i, entry) in enumerate(toc_with_pages):
        if idx + 1 < len(toc_with_pages):
            next_page = toc_with_pages[idx + 1][1]["page"]
            entry["end_page"] = (
                next_page - 1 if next_page > entry["page"] else entry["page"]
            )
        else:
            entry["end_page"] = total_pages

    for entry in toc:
        if entry.get("page") is None:
            entry["end_page"] = None
        elif "end_page" not in entry:
            entry["end_page"] = total_pages


def _get_top_level_toc(toc: list[dict]) -> list[dict]:
    """Filter TOC to only include top-level entries (level 0)."""
    return [e for e in toc if e.get("level", 0) == 0]


def filter_toc_by_depth(toc: list[dict], depth: int = 2) -> list[dict]:
    """Filter TOC entries to specified depth (1 = only top-level, 2 = X and X.Y, etc.)."""
    return [e for e in toc if e.get("level", 0) < depth]


def print_toc(
    toc: list[dict], show_usage: bool = True, depth: int = 2, filename: str = ""
):
    """Print table of contents with natural sequential indexing."""
    if filename:
        print(f"\nTable of Contents: {filename}")
    else:
        print("\nTable of Contents:")

    display_toc = filter_toc_by_depth(toc, depth)

    if not display_toc:
        print("  (no chapters detected)")
        return

    for i, entry in enumerate(display_toc, 1):
        level = entry.get("level", 0)
        indent = "    " * level

        if entry.get("page") and entry.get("end_page"):
            if entry["page"] == entry["end_page"]:
                page_str = f"page {entry['page']}"
            else:
                page_str = f"pages {entry['page']}-{entry['end_page']}"
        elif entry.get("page"):
            page_str = f"page {entry['page']}"
        else:
            page_str = "page ?"

        title = entry["title"]
        if entry.get("numbering") and not title.startswith(entry["numbering"]):
            title = f"{entry['numbering']}. {title}"

        print(f"[{i}] {indent}{title} ({page_str})")

    if show_usage:
        n = len(display_toc)
        if n > 4:
            print(f"\nUse: --chapters 1-3,5-{n} to select by index")
        else:
            print(f"\nUse: --chapters 1-{n} to select chapters")

        has_more = any(e.get("level", 0) >= depth for e in toc)
        if has_more:
            print(f"Use: --toc-depth 3 for more levels (current: {depth})")


# ---------------------------------------------------------------------------
# Selection parsing
# ---------------------------------------------------------------------------


def parse_page_ranges(pages_str: str, total_pages: int) -> list[int]:
    """Parse page ranges like '1-50' or '1-20,45-80,100-120' into list of page indices (0-based)."""
    page_indices = []

    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = max(1, int(start.strip()))
            end = min(total_pages, int(end.strip()))
            page_indices.extend(range(start - 1, end))
        else:
            page_num = int(part.strip())
            if 1 <= page_num <= total_pages:
                page_indices.append(page_num - 1)

    return sorted(set(page_indices))


def parse_chapter_selection(
    chapters_str: str, toc: list[dict], depth: int = 2
) -> list[int]:
    """Parse chapter selection like '1,3,5' or '2-4' into page indices (0-based).

    Uses natural indices from filtered TOC (same as displayed by --toc).
    """
    display_toc = filter_toc_by_depth(toc, depth)

    if not display_toc:
        return []

    chapter_nums = []
    for part in chapters_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = int(start.strip())
            end = int(end.strip())
            chapter_nums.extend(range(start, end + 1))
        else:
            chapter_nums.append(int(part.strip()))

    page_indices = []
    for ch_num in chapter_nums:
        if 1 <= ch_num <= len(display_toc):
            entry = display_toc[ch_num - 1]
            if entry.get("page") and entry.get("end_page"):
                page_indices.extend(range(entry["page"] - 1, entry["end_page"]))

    return sorted(set(page_indices))


def format_page_ranges(page_indices: list[int]) -> str:
    """Format page indices back to readable ranges (1-based)."""
    if not page_indices:
        return ""

    ranges = []
    start = page_indices[0] + 1
    end = start

    for idx in page_indices[1:]:
        page = idx + 1
        if page == end + 1:
            end = page
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = page

    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ",".join(ranges)


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------


def extract_pdf(
    file_path: Path, page_indices: list[int] | None = None
) -> tuple[list[str], int, int]:
    """Extract text from PDF, returns (pages_text, selected_count, total_count)."""
    pages = []
    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)

        if page_indices is None:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
            return pages, total_pages, total_pages
        else:
            for idx in page_indices:
                if 0 <= idx < total_pages:
                    text = pdf.pages[idx].extract_text() or ""
                    pages.append(text)
            return pages, len(pages), total_pages


# ---------------------------------------------------------------------------
# File resolution
# ---------------------------------------------------------------------------


def get_pdf_files(specific_file: str | None) -> list[Path]:
    """Get list of PDFs to process."""
    if specific_file:
        path = Path(specific_file)
        if not path.exists():
            path = INPUT_DIR / specific_file
        if not path.exists():
            print(f"Error: File not found: {specific_file}")
            return []
        return [path]

    pdfs = list(INPUT_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {INPUT_DIR}/")
    return pdfs
