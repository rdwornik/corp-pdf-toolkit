# Corporate PDF Toolkit

CLI tools for processing corporate PDFs locally. Extract text to Markdown for AI context, or anonymize sensitive content using a local Ollama LLM. All processing happens on your machine -- no data leaves localhost.

## Features

- **PDF to Markdown** -- instant text extraction, no LLM required
- **PDF Anonymization** -- replaces company names, people, prices, dates, etc. with placeholders via local Ollama
- **Chapter/page selection** -- process specific sections using TOC navigation or page ranges
- **Parallel processing** -- concurrent chunk processing for anonymization
- **YAML frontmatter** -- output includes source metadata for traceability

## Installation

```bash
pip install pdfplumber httpx pypdf
```

For anonymization, install and run [Ollama](https://ollama.ai/):

```bash
ollama pull qwen2.5:7b
ollama serve
```

## Usage

### Extract PDF to Markdown

```bash
python pdf2md.py                          # All PDFs in input/
python pdf2md.py document.pdf             # Specific file
python pdf2md.py doc.pdf --pages 1-50     # Specific pages
python pdf2md.py doc.pdf --chapters 1-4   # Specific chapters
python pdf2md.py doc.pdf --toc            # Show table of contents
python pdf2md.py doc.pdf --info           # Show PDF metadata
```

Output: `input/document.pdf` -> `output/document.md`

### Anonymize PDF

```bash
python anonymize.py                       # All PDFs in input/
python anonymize.py document.pdf          # Specific file
python anonymize.py --model mistral       # Different model
python anonymize.py --chunk-size 4000     # Larger chunks (fewer LLM calls)
python anonymize.py --parallel 4          # More concurrent requests
```

Output: `input/document.pdf` -> `output/document_anonymized.md`

### Navigation Options

Both scripts share these options:

| Option | Description |
|--------|-------------|
| `--toc` | Show table of contents |
| `--toc-depth N` | TOC depth (1=main, 2=+sub, 3=+sub-sub) |
| `--chapters 1-4,8-10` | Select chapters by index |
| `--pages 1-50,80-100` | Select page ranges |
| `--info` | Show PDF info without processing |

### Anonymization Placeholders

| Placeholder | Replaces |
|-------------|----------|
| `[COMPANY]`, `[CLIENT]`, `[VENDOR]` | Company/organization names |
| `[PRODUCT]`, `[PLATFORM]` | Product/solution names |
| `[PERSON]`, `[EXECUTIVE]` | Person names |
| `[PRICE]`, `[REVENUE]`, `[AMOUNT]` | Financial figures |
| `[EMAIL]`, `[PHONE]`, `[URL]` | Contact information |
| `[LOCATION]` | Addresses/locations |
| `[DATE]` | Specific dates |

## Architecture

```
corporate-pdf-toolkit/
├── input/           # Drop PDFs here
├── output/          # Generated .md files
├── pdf_utils.py     # Shared: TOC parsing, extraction, selection
├── anonymize.py     # Anonymize via Ollama (async, parallel)
├── pdf2md.py        # Extract to Markdown (no LLM)
└── pyproject.toml   # Dependencies
```

## Performance Tuning

For anonymization on CPU with 32GB RAM:

```bash
# Faster (larger chunks, more parallel)
python anonymize.py --chunk-size 4000 --parallel 4

# Memory constrained
python anonymize.py --chunk-size 2000 --parallel 2
```

Ollama environment variables:

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

## Testing

No test suite yet.

## Related repos

- corp-by-os -- orchestrator
- corp-os-meta -- shared schemas
- corp-knowledge-extractor -- extraction engine
- corp-rfp-agent -- RFP automation
- ai-council -- multi-model debate

## License

Internal use only -- Blue Yonder Pre-Sales Engineering
