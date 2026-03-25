---
paths:
  - "extraction/schemas.py"
---

# Extraction Schema Rules

## Docstrings
- Every `BaseModel` subclass MUST have a docstring explaining what it represents
- Example: `"""Structured data extracted from an invoice document."""`

## Field Descriptions
- Every field MUST use `Field(description="...")` — Claude uses these descriptions
  to understand what data to extract, so they must be clear and specific
- Include format hints in descriptions where relevant (e.g., "YYYY-MM-DD", "3-letter ISO 4217")

## Enums
- All `str, Enum` classes MUST include an `OTHER = "other"` variant as a fallback
- This prevents extraction failures when documents contain unexpected categories

## Schema Generation
- Use `model_json_schema()` (Pydantic v2) — never `schema()` (Pydantic v1 legacy)
- Use `get_tool_definition(ModelClass, "tool_name")` to build Claude tool definitions
- The helper handles `$defs` extraction for nested models automatically

## Type Conventions
- Use `list[X]` not `List[X]` (Python 3.11+ native generics)
- Use `Optional[X]` with `default=None` for nullable fields
- Monetary values: `float` type
- Counts: `int` type
- Dates: `str` type with format described in Field description

## Adding New Schemas
1. Define any new enums with an OTHER fallback
2. Define nested models (e.g., line items) as separate BaseModel classes
3. Define the main extraction model with all fields having Field descriptions
4. Test that `get_tool_definition()` produces valid output
5. Add the new model to SCHEMA_MAP dicts in extractor.py and validator.py
