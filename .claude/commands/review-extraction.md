---
allowed-tools:
  - Bash(python:*)
  - Read
---

# Review Extraction Quality

Run extraction on ALL sample documents and produce a quality report.

## Steps

1. Find all sample documents:
   - `sample_data/invoices/*.txt`
   - `sample_data/marketing_reports/*.txt`
   - `sample_data/support_tickets/*.txt`

2. For each document, run extraction using the appropriate strategy:
   - Invoices: use `extract_with_retry` (with validation) from `extraction.validator`
   - Marketing reports: use `extract_with_structured_output` from `extraction.extractor`
   - Support tickets: use `extract_auto_detect` from `extraction.extractor`

3. For invoice extractions, validate with `validate_extraction` and report:
   - Schema validation pass/fail
   - Business logic checks (math correctness)
   - Number of retry attempts needed

4. Run cross-file consistency review using `extraction.multi_pass.cross_file_review`
   on all extraction results together

5. Produce a summary report:
   - Total documents processed
   - Per-document: extraction method used, validation status, key extracted fields
   - Cross-document issues found (entity mismatches, currency issues, etc.)
   - Overall quality score and recommendations
