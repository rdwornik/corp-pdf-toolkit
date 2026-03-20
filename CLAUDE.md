# CLAUDE.md -- corporate-pdf-toolkit

## What this repo does

CLI tools for processing corporate PDFs: instant text extraction to Markdown (pdf2md.py) and anonymization via local Ollama LLMs (anonymize.py). All processing happens locally -- no data leaves the machine.

## Quick start

```bash
# Install dependencies
pip install pdfplumber httpx pypdf

# Extract PDF to Markdown (no LLM needed)
python pdf2md.py document.pdf

# Anonymize a PDF (requires Ollama running)
ollama serve
python anonymize.py document.pdf
```

## Architecture

Flat layout, no `src/` directory. Three Python modules at root:

| File | Purpose |
|------|---------|
| `pdf_utils.py` | Shared utilities: TOC parsing, page/chapter selection, text extraction, file resolution |
| `pdf2md.py` | PDF-to-Markdown extractor (no LLM). Argparse CLI |
| `anonymize.py` | PDF anonymizer via Ollama LLM. Async with parallel chunk processing. Argparse CLI |

**Data flow:**
- `input/` -- drop PDFs here
- `output/` -- generated `.md` files
- `input/archive/` -- processed PDFs are moved here after completion

**Shared constants** in `pdf_utils.py`: `INPUT_DIR`, `OUTPUT_DIR`, `ARCHIVE_DIR`, `SCRIPT_DIR`.

**TOC detection** (priority order):
1. PDF bookmarks/outlines via pypdf
2. TOC page parsing ("title.....page" dot-leader patterns)

## Dev standards

- Python 3.10+, Windows-first (PowerShell / Git Bash)
- `pyproject.toml` as single source of truth for dependencies
- `ruff` for linting and formatting
- No `src/` layout -- scripts at root level
- argparse for CLI (not Click)
- No logging framework -- uses print statements
- async/httpx for Ollama communication (anonymize.py)
- pdfplumber for text extraction, pypdf for outline/bookmark parsing

## Key commands

```bash
# PDF to Markdown
python pdf2md.py                          # All PDFs in input/
python pdf2md.py doc.pdf                  # Specific file
python pdf2md.py doc.pdf --toc            # Show table of contents
python pdf2md.py doc.pdf --toc-depth 3    # Deeper TOC levels
python pdf2md.py doc.pdf --chapters 1-4   # Extract specific chapters
python pdf2md.py doc.pdf --pages 1-50     # Extract specific pages
python pdf2md.py doc.pdf --info           # Show PDF metadata

# Anonymize via Ollama
python anonymize.py                       # All PDFs in input/
python anonymize.py doc.pdf               # Specific file
python anonymize.py --model mistral       # Different model
python anonymize.py --chunk-size 4000     # Larger chunks
python anonymize.py --parallel 4          # More concurrency

# Code quality
python -m ruff check *.py --fix
python -m ruff format *.py
```

## Test suite

No tests exist yet. All three modules (`pdf_utils.py`, `pdf2md.py`, `anonymize.py`) have zero test coverage.

## Dependencies

| Package | Used by | Purpose |
|---------|---------|---------|
| `pdfplumber` | Both | PDF text extraction |
| `pypdf` | Both | PDF outline/bookmark reading |
| `httpx` | anonymize.py | Async HTTP client for Ollama API |

Ollama must be running locally (`ollama serve`) for anonymize.py. Default model: `qwen2.5:7b`.

## API Keys

Keys loaded globally from `Documents/.secrets/.env` via PowerShell profile.
Do NOT add API keys to local `.env`.
Check: `keys list` | Update: `keys set KEY value` | Reload: `keys reload`

This repo uses: **none** — all processing is local (Ollama for LLM, pdfplumber/pypdf for PDF parsing).

## Known issues

- **No test coverage** -- all modules untested
- **No type checking** -- mypy not configured or installed
- **Archive behavior** -- both scripts move processed PDFs to `input/archive/` after processing, which could surprise users
- **No error recovery** -- if Ollama fails mid-processing, partial results may be lost
- **Flat layout** -- no package structure, scripts import each other via relative imports at root level

## Related repos

- corp-by-os -- orchestrator
- corp-os-meta -- shared schemas
- corp-knowledge-extractor -- extraction engine
- corp-rfp-agent -- RFP automation
- ai-council -- multi-model debate
