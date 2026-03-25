# Structured Extraction with Claude — Project Guide

## Overview

This project demonstrates structured data extraction using the Anthropic Claude API.
It showcases four extraction strategies (forced tool_use, output_config JSON schema,
auto-detect multi-tool, and validation-retry loops) across three document types:
invoices, marketing reports, and support tickets.

## Quick Start

```bash
# Environment setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Set API key
# Create .env with: ANTHROPIC_API_KEY=sk-ant-...

# Run all demos
python main.py

# Run specific demo (1-4)
python main.py 2

# Run tests (no API key needed)
python -m pytest tests/ -v
```

## Project Structure

```
extraction/
  schemas.py          — Pydantic v2 models (InvoiceExtraction, MarketingReport, SupportTicket)
  extractor.py        — Three extraction strategies (forced tool, output_config, auto-detect)
  validator.py        — Schema + business logic validation, CCA retry loop
  batch_processor.py  — Message Batches API for bulk extraction
  multi_pass.py       — Cross-document consistency review
tests/
  test_extraction.py  — Unit tests (no API calls, tests schemas + validation logic)
sample_data/
  invoices/           — Sample invoice documents
  marketing_reports/  — Sample marketing performance reports
  support_tickets/    — Sample support ticket documents
main.py               — Demo runner for all 4 extraction modes
```

## Environment

- Python 3.11+
- Dependencies: anthropic, pydantic, python-dotenv, pytest
- API key via `.env` file (never committed — in .gitignore)
- Windows OS, activate venv with `venv\Scripts\activate`

## Architecture & Key Patterns

### Extraction Strategies

1. **Forced tool_use** (`extractor.extract_invoice`):
   `tool_choice={"type": "tool", "name": "extract_invoice"}` — guarantees Claude calls
   exactly one tool, producing structured output matching the schema.

2. **output_config structured output** (`extractor.extract_with_structured_output`):
   `output_config={"format": {"type": "json_schema", "schema": schema}}` — constrains
   Claude's entire response to match a JSON schema. No tools involved.

3. **Auto-detect multi-tool** (`extractor.extract_auto_detect`):
   `tool_choice={"type": "auto"}` with all three tools — Claude decides which to call.

4. **Validation + retry** (`validator.extract_with_retry`):
   CCA pattern — extract, validate, feed errors back as `tool_result` with `is_error=True`,
   Claude self-corrects. Up to `max_retries` correction rounds.

### Schema Design

All schemas live in `extraction/schemas.py` as Pydantic v2 `BaseModel` classes.
The `get_tool_definition()` helper converts any model into a Claude tool definition.
Every field must have a `Field(description=...)`. Enums must include an `OTHER` fallback.

### Validation Layers

- **Schema validation**: Pydantic `model_validate()` for type/structure checks
- **Business logic**: Math verification (line items sum, subtotal+tax=total),
  conditional field requirements (payment_terms="other" needs detail)

### Batch Processing

`batch_processor.py` uses `client.messages.batches.create()` for high-throughput
extraction at 50% cost reduction. Each document gets a `custom_id` for result correlation.

### Cross-File Review

`multi_pass.cross_file_review()` sends all extractions to Claude in one call,
checking for entity name mismatches, currency inconsistencies, date sequence
issues, duplicate invoice numbers, and math errors.

## Code Standards

- Type hints on all function signatures
- Pydantic v2 (`BaseModel`, `model_validate`, `model_json_schema`) — never v1 API
- `anthropic.Anthropic()` client with explicit `max_tokens` on every API call
- `python-dotenv` for API key loading — never hardcode keys
- All schemas use `Field(description=...)` for Claude to understand the expected data
- Docstrings on all public functions

## API Client Conventions

- Model constant: `MODEL = "claude-sonnet-4-20250514"`
- Always set `max_tokens=4096` explicitly
- Tool definitions built from Pydantic models via `get_tool_definition()`
- Handle both `text` and `tool_use` content blocks in responses
- Batch API: use `custom_id` for document correlation

## Testing

- All tests in `tests/` — run with `python -m pytest tests/ -v`
- Tests must NOT make real API calls
- Mock `client.messages.create()` when testing extraction functions
- Test validation logic directly (no mocks needed)
- Test schema generation via `get_tool_definition()` (no mocks needed)
