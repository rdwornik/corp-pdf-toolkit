# PDF Anonymizer

CLI tools for processing PDFs: anonymization via local Ollama LLMs, and instant text extraction to Markdown.

## Structure

```
pdf-anonymizer/
├── input/                    # Drop PDFs here
├── output/                   # Output .md files
├── pdf_utils.py              # Shared utilities (TOC, extraction, selection)
├── anonymize.py              # Anonymize PDFs via Ollama LLM
├── pdf2md.py                 # Extract PDF text to Markdown (no LLM)
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

## Usage

### pdf2md.py — PDF to Markdown (no LLM)

Fast text extraction for feeding into AI tools as context.

```bash
# Extract all PDFs in input/
python pdf2md.py

# Extract specific file
python pdf2md.py document.pdf

# Show chapters / PDF info
python pdf2md.py doc.pdf --toc
python pdf2md.py doc.pdf --info

# Extract specific chapters or pages
python pdf2md.py doc.pdf --chapters 1-4,8-10
python pdf2md.py doc.pdf --pages 1-50,80-100
```

### anonymize.py — Anonymize via Ollama

```bash
# Setup
pip install pdfplumber httpx pypdf

# Process all PDFs in input/
python anonymize.py

# Process specific file
python anonymize.py document.pdf

# Show chapters (default depth=2)
python anonymize.py doc.pdf --toc
python anonymize.py doc.pdf --toc-depth 1   # Only main chapters
python anonymize.py doc.pdf --toc-depth 3   # More subsections

# Process by index (supports ranges)
python anonymize.py doc.pdf --chapters 1-4        # Chapters 1,2,3,4
python anonymize.py doc.pdf --chapters 1-4,8-10   # Multiple ranges
python anonymize.py doc.pdf --chapters 1,3,5-8    # Mix single and ranges

# Process specific pages
python anonymize.py doc.pdf --pages 1-50,80-100

# PDF info
python anonymize.py doc.pdf --info

# Use different model
python anonymize.py --model mistral
```

**--toc output:**
```
Table of Contents: document.pdf
[1] 1. General (pages 8-9)
[2] 2. Project topics (pages 13-17)
[3] 3. Architecture (pages 44-96)
[4]     3.1 System landscape (pages 45-49)
[5]     3.2 Integration (pages 50-54)
[6] 4. Requirements (pages 122-129)

Use: --chapters 1-3,5-6 to select by index
```

## Requirements

- Python 3.10+
- `pdfplumber`, `pypdf` (both scripts)
- `httpx` (anonymize.py only)
- Ollama running locally for anonymize.py (`ollama serve`)
- Model: qwen2.5:7b (default)

## Output Format

### pdf2md.py

`input/document.pdf` → `output/document.md`

```markdown
---
source: "document.pdf"
pages: 25
extracted: 2026-01-22T14:08:39
pages_selected: "1-50"
---

Full text content...
```

### anonymize.py

`input/document.pdf` → `output/document_anonymized.md`

```markdown
---
source: "document.pdf"
pages: 25
model: qwen2.5:7b
processed: 2026-01-22T14:08:39
placeholders:
  COMPANY: company/organization name
  PERSON: person name
---

Anonymized text content...
```

Only placeholders actually used are listed in frontmatter.

## Placeholders

| Placeholder | Replaces |
|-------------|----------|
| [COMPANY] | Company names |
| [PRODUCT] | Product/solution names |
| [PERSON] | Person names |
| [PRICE] | Prices/costs |
| [DATE] | Specific dates |
| [URL] | URLs/domains |
| [EMAIL] | Email addresses |
| [LOCATION] | Addresses/locations |

## Debugging

```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Check available models
ollama list
```

## Ollama Configuration

Set these environment variables before running `ollama serve`:

```bash
# Linux/macOS
export OLLAMA_NUM_THREADS=14
export OLLAMA_KEEP_ALIVE=60m
ollama serve

# Windows PowerShell
$env:OLLAMA_NUM_THREADS=14
$env:OLLAMA_KEEP_ALIVE="60m"
ollama serve
```

## Options

Shared options (both scripts):

| Option | Default | Description |
|--------|---------|-------------|
| `--toc` | - | Show table of contents |
| `--toc-depth` | 2 | Depth: 1=main, 2=+sub, 3=+sub-sub |
| `--chapters` | all | Indices (e.g., `1-4` or `1-4,8-10`) |
| `--pages` | all | Pages (e.g., `1-50` or `1-20,50-60`) |
| `--info` | - | Show PDF info (no processing) |

anonymize.py only:

| Option | Default | Description |
|--------|---------|-------------|
| `--chunk-size` | 3500 | Characters per chunk |
| `--parallel` | 3 | Concurrent chunks |
| `--model` | qwen2.5:7b | Ollama model |

## Performance Tuning

Optimized for CPU with 32GB RAM (anonymize.py).

```bash
# Faster (larger chunks, more parallel)
python anonymize.py --chunk-size 4000 --parallel 4

# Memory constrained
python anonymize.py --chunk-size 2000 --parallel 2
```

**How it works:**
- Model preloaded with `keep_alive=60m` at startup
- 3 chunks processed in parallel (Ollama queues requests)
- Progress: `Chunk 5-7/20 processing... (4 done)`
