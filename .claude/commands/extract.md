---
allowed-tools:
  - Bash(python:*)
  - Read
  - Write
---

# Extract Structured Data

Run structured extraction on the specified document file.

1. Read the file at: $ARGUMENTS
2. Detect the document type from its content (invoice, marketing report, or support ticket)
3. Run extraction using the auto-detect strategy:
   ```
   python -c "
   from extraction.extractor import extract_auto_detect
   from pathlib import Path
   import json

   text = Path('$ARGUMENTS').read_text(encoding='utf-8')
   result = extract_auto_detect(text)
   print(f'Tool used: {result[\"tool_used\"]}')
   print(f'Reasoning: {result[\"reasoning\"]}')
   print(json.dumps(result['data'], indent=2))
   "
   ```
4. Display the extracted JSON result
5. If the detected type is invoice, also run validation:
   ```
   python -c "
   from extraction.validator import validate_extraction
   import json

   data = <the extracted data>
   is_valid, errors = validate_extraction('extract_invoice', data)
   print(f'Valid: {is_valid}')
   if errors:
       for e in errors:
           print(f'  - {e}')
   "
   ```
6. Save the extraction result to `output/<filename>_extracted.json`
