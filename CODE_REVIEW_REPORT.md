# Code Review Report -- corporate-pdf-toolkit

**Date:** 2026-03-15
**Branch:** `code-review-2026-03-15`
**Reviewer:** Claude Opus 4.6

## Summary

```
REPO: corporate-pdf-toolkit
TESTS: 0 (no test suite exists)
RUFF: clean (lint + format)
COMMITS: 4
FILES CHANGED: 5
```

## Commits Made

1. `8f3c1bf` -- style: ruff format pass on all Python files
2. `d27831f` -- chore: add .claude/ to .gitignore
3. `1411a10` -- docs: update CLAUDE.md to current state
4. `18f7cf6` -- docs: professional README with full usage guide

## Files Changed

| File | Change |
|------|--------|
| `anonymize.py` | Ruff formatting (whitespace, line breaks) |
| `pdf2md.py` | Ruff formatting |
| `pdf_utils.py` | Ruff formatting |
| `.gitignore` | Added `.claude/` directory |
| `CLAUDE.md` | Full rewrite to standard structure |
| `README.md` | Full rewrite as professional README |

## Issues Found

### Critical

None.

### Code Quality

| Issue | Status |
|-------|--------|
| Ruff formatting inconsistencies in all 3 Python files | **Fixed** |
| `.claude/` directory not in `.gitignore` | **Fixed** |
| CLAUDE.md was a copy of README content, not dev-focused | **Fixed** |

### No Test Coverage

All three modules have zero test coverage. Priority areas for future tests:

- **pdf_utils.py** -- TOC parsing (`get_toc`, `_get_toc_from_outlines`, `_get_toc_from_toc_page`), page range parsing (`parse_page_ranges`, `parse_chapter_selection`), format functions (`format_page_ranges`)
- **pdf2md.py** -- CLI argument handling, markdown output with frontmatter, archive behavior
- **anonymize.py** -- Chunk splitting (`get_chunks`), placeholder detection, Ollama API mocking

### Observations (No Action Taken)

- **No type checking** -- mypy is not installed in the environment. Consider adding to dev dependencies.
- **Archive behavior** -- both scripts silently move input PDFs to `input/archive/` after processing. This could surprise users who expect their input files to remain in place.
- **No error recovery** -- if anonymize.py fails mid-processing (Ollama crash, timeout), partial results may be lost. Consider writing intermediate results.
- **Flat layout** -- scripts at root level with relative imports. Works fine for 3 files but won't scale if more tools are added.
- **Print-based output** -- both scripts use `print()` instead of `logging`. Fine for CLI tools, but limits testability and output control.
- **No `--no-archive` flag** -- users cannot opt out of the auto-archive behavior.
- **Duplicate code** -- `anonymize.py` and `pdf2md.py` share ~50 lines of identical CLI handling for `--toc`, `--info`, `--chapters` resolution. Could be factored into `pdf_utils.py`.
- **`nul` file in repo root** -- appears to be an accidental Windows artifact (already in .gitignore)

## What Was NOT Changed

- No functionality changes
- No tests deleted (none existed)
- No code logic modified
- No dependencies added or removed
