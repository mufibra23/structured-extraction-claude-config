---
allowed-tools:
  - Read
  - Write
---

# Add New Extraction Schema

Create a new Pydantic extraction schema following the project's established patterns.

The user will describe a document type: $ARGUMENTS

## Steps

1. Read `extraction/schemas.py` to understand the existing patterns
2. Design the new schema based on the user's description:
   - Create any needed `str, Enum` classes with an `OTHER = "other"` fallback value
   - Create nested `BaseModel` classes for repeated/grouped data (like LineItem)
   - Create the main extraction `BaseModel` with:
     - Every field using `Field(description="...")`
     - `Optional[X] = Field(default=None, ...)` for nullable fields
     - `list[X]` for array fields
     - A class docstring explaining the schema
3. Add the new classes to `extraction/schemas.py`
4. Update the `SCHEMA_MAP` dicts in:
   - `extraction/extractor.py` (add to imports, SCHEMA_MAP, and tool definitions)
   - `extraction/validator.py` (add to imports and SCHEMA_MAP)
   - `extraction/batch_processor.py` (add to imports and TOOL_MAP)
5. Verify the schema generates correctly:
   ```python
   from extraction.schemas import NewModel, get_tool_definition
   tool = get_tool_definition(NewModel, "extract_new_type")
   ```
6. Add basic tests in `tests/test_extraction.py` for the new schema
