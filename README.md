# PDF Anonymizer

CLI tools for processing PDFs: instant text extraction to Markdown, and anonymization via local Ollama LLMs.

**All processing happens on your machine. No data leaves localhost.**

## Quick Start

```bash
# Install dependencies
pip install pdfplumber httpx pypdf

# Extract PDF text to Markdown (no LLM needed)
python pdf2md.py document.pdf

# Anonymize a PDF (requires Ollama)
ollama serve
python anonymize.py document.pdf
```

## pdf2md.py — PDF to Markdown

Fast text extraction for feeding into AI tools as context. No LLM required.

```bash
python pdf2md.py                    # All PDFs from input/
python pdf2md.py document.pdf       # Specific file
python pdf2md.py doc.pdf --pages 1-50          # Specific pages
python pdf2md.py doc.pdf --chapters 1-4,8-10   # Specific chapters
```

Output: `input/document.pdf` → `output/document.md`

```markdown
---
source: "document.pdf"
pages: 25
extracted: 2026-01-22T14:08:39
pages_selected: "1-50"
---

Full text content...
```

## anonymize.py — Anonymize via Ollama

Replaces sensitive information (company names, person names, prices, etc.) with placeholders while preserving document structure.

```bash
python anonymize.py                    # All PDFs from input/
python anonymize.py document.pdf       # Specific file
python anonymize.py --model mistral    # Different model
python anonymize.py --chunk-size 4000  # Larger chunks (fewer LLM calls)
python anonymize.py --parallel 4       # More parallel requests
```

Output: `input/document.pdf` → `output/document_anonymized.md`

```markdown
---
source: "document.pdf"
pages: 25
model: qwen2.5:7b
processed: 2026-01-22T14:08:39
placeholders:
  COMPANY: company/organization name
  CLIENT: client company name
  PRICE: price/cost amount
  PERSON: person name
---

Anonymized text...
```

Only placeholders actually used in the text are listed in frontmatter.

### What Gets Anonymized

| Original | Placeholder |
|----------|-------------|
| Company names | `[COMPANY]`, `[CLIENT]`, `[VENDOR]` |
| Products | `[PRODUCT]`, `[PLATFORM]` |
| People | `[PERSON]`, `[EXECUTIVE]` |
| Money | `[PRICE]`, `[REVENUE]`, `[AMOUNT]` |
| Contact | `[EMAIL]`, `[PHONE]`, `[URL]` |
| Location | `[LOCATION]` |
| Dates | `[DATE]` |

### What Stays

- Technical definitions and terminology
- Process descriptions
- Architectural concepts
- Feature descriptions (generalized)
- Industry terminology

## Page & Chapter Selection

Both scripts share the same selection options.

### Page Selection

```bash
python pdf2md.py doc.pdf --pages 1-50
python pdf2md.py doc.pdf --pages 1-20,45-80,100-120
```

### Chapter Selection

```bash
# Show chapters (default depth=2: main + subsections)
python pdf2md.py doc.pdf --toc

# Control depth
python pdf2md.py doc.pdf --toc-depth 1   # Only main chapters
python pdf2md.py doc.pdf --toc-depth 3   # Include sub-subsections
```

Example `--toc` output:
```
Table of Contents: document.pdf
[1] 1. General (pages 8-9)
[2] 2. Project topics (pages 13-17)
[3] 3. Processes / operational issues (pages 18-43)
[4] 4. Architecture / Interfaces / Technology (pages 44-96)
[5]     4.1 System landscape (pages 45-49)
[6]     4.2 Integration pattern (pages 50-54)
[7]     4.3 System functionalities (pages 55-96)
[8]     4.4 Interfaces (pages 97-121)
[9] 5. Requirements (pages 122-129)
[10] 6. Glossary (pages 172-179)

Use: --chapters 1-4,6-8 to select by index
```

```bash
# Process by index (supports ranges)
python pdf2md.py doc.pdf --chapters 1-4        # Chapters 1,2,3,4
python pdf2md.py doc.pdf --chapters 1-4,8-10   # Multiple ranges
python pdf2md.py doc.pdf --chapters 1,3,5-8    # Mix single and ranges
```

**Chapter detection (priority order):**
1. PDF bookmarks/outlines (validated)
2. TOC page parsing ("title.....page" patterns)

### PDF Info

```bash
python pdf2md.py doc.pdf --info
```

```
File: document.pdf
Pages: 180
Size: 2.45 MB
Has TOC: Yes (12 entries)
```

## Options

Shared options (both scripts):

| Option | Default | Description |
|--------|---------|-------------|
| `--toc` | - | Show table of contents |
| `--toc-depth` | 2 | TOC depth: 1=main, 2=+subsections, 3=+sub-sub |
| `--chapters` | all | Chapter indices (e.g., `1-4` or `1-4,8-10`) |
| `--pages` | all | Page ranges (e.g., `1-50` or `1-20,50-60`) |
| `--info` | - | Show PDF info without processing |

anonymize.py only:

| Option | Default | Description |
|--------|---------|-------------|
| `--chunk-size` | 3500 | Characters per chunk. Larger = fewer LLM calls |
| `--parallel` | 3 | Concurrent chunks. Ollama queues requests |
| `--model` | qwen2.5:7b | Model to use |

## Performance Tuning

Optimized for CPU with 32GB RAM (anonymize.py).

### Ollama Configuration

Set these environment variables before running `ollama serve`:

```bash
# Use 14 CPU threads (adjust for your CPU)
export OLLAMA_NUM_THREADS=14

# Keep model in RAM for 60 minutes (avoids reload between files)
export OLLAMA_KEEP_ALIVE=60m

# Then start Ollama
ollama serve
```

Windows (PowerShell):
```powershell
$env:OLLAMA_NUM_THREADS=14
$env:OLLAMA_KEEP_ALIVE="60m"
ollama serve
```

### Tuning Tips

```bash
# Faster processing (larger chunks, more parallel)
python anonymize.py --chunk-size 4000 --parallel 4

# Memory constrained (smaller chunks, less parallel)
python anonymize.py --chunk-size 2000 --parallel 2
```

**How it works:**
- Model is preloaded with `keep_alive=60m` at startup
- 3 chunks processed in parallel (Ollama queues requests)
- Larger chunks (3500 chars) = fewer total LLM calls
- Progress shows: `Chunk 5-7/20 processing... (4 done)`

## Requirements

- Python 3.10+
- `pdfplumber`, `pypdf` (both scripts)
- `httpx` (anonymize.py only)
- [Ollama](https://ollama.ai/) with a model (anonymize.py only)

## Model Recommendations

| Model | Size | Notes |
|-------|------|-------|
| qwen2.5:7b | 4.7 GB | Best for structured output (default) |
| mistral:latest | 4.4 GB | Good general purpose |
| llama3.2:latest | 2.0 GB | Faster, lighter |

```bash
# Check your models
ollama list

# Pull recommended model
ollama pull qwen2.5:7b
```

## Project Structure

```
pdf-anonymizer/
├── input/           # Drop PDFs here
├── output/          # Output .md files
├── pdf_utils.py     # Shared utilities (TOC, extraction, selection)
├── anonymize.py     # Anonymize PDFs via Ollama LLM
├── pdf2md.py        # Extract PDF text to Markdown (no LLM)
├── pyproject.toml
└── README.md
```

## License

MIT
