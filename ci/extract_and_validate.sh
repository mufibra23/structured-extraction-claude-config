#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# ci/extract_and_validate.sh
#
# Extract structured data from a document using Claude Code in print mode.
# Designed for CI/CD pipelines — non-interactive, JSON output, exit codes.
#
# Usage:
#   ./ci/extract_and_validate.sh <document_path> [output_path]
#
# Arguments:
#   $1  Path to the document file (required)
#   $2  Path for JSON output (default: output.json)
#
# Exit codes:
#   0  Success — valid JSON extraction written to output
#   1  Usage error (missing arguments, file not found)
#   2  Claude extraction failed
#   3  Output is not valid JSON (validation failed)
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Args ─────────────────────────────────────────────────────────────────────

DOCUMENT_PATH="${1:-}"
OUTPUT_PATH="${2:-output.json}"

if [[ -z "$DOCUMENT_PATH" ]]; then
    echo "ERROR: No document path provided." >&2
    echo "Usage: $0 <document_path> [output_path]" >&2
    exit 1
fi

if [[ ! -f "$DOCUMENT_PATH" ]]; then
    echo "ERROR: File not found: $DOCUMENT_PATH" >&2
    exit 1
fi

# ── Extract ──────────────────────────────────────────────────────────────────

FILENAME=$(basename "$DOCUMENT_PATH")
echo "Extracting: $DOCUMENT_PATH"
echo "Output:     $OUTPUT_PATH"
echo "──────────────────────────────────────────"

# Build the prompt — Claude reads the file, detects type, extracts, validates
PROMPT="Read the document at ${DOCUMENT_PATH}. \
Determine its type (invoice, marketing report, or support ticket). \
Extract all structured data following the schemas in extraction/schemas.py. \
Validate the extraction: for invoices check that line item totals sum to subtotal \
and subtotal + tax = total_amount. \
If validation fails, fix the errors. \
Output ONLY the final JSON object — no markdown, no explanation, no code fences. \
The JSON must include a top-level \"_metadata\" field with: \
\"source_file\" (the filename), \"document_type\" (invoice/marketing_report/support_ticket), \
\"extraction_timestamp\" (ISO 8601 now), and \"validation_status\" (pass/fail)."

# Run Claude in print mode with JSON output format
if ! claude -p \
    --output-format json \
    --max-turns 3 \
    --model sonnet \
    "$PROMPT" \
    > "$OUTPUT_PATH" 2>/dev/null; then
    echo "ERROR: Claude extraction failed for $FILENAME" >&2
    exit 2
fi

# ── Validate JSON ────────────────────────────────────────────────────────────

if ! python -c "
import json, sys
try:
    with open('${OUTPUT_PATH}') as f:
        data = json.load(f)
    # Verify it's a dict with actual content
    if not isinstance(data, dict) or len(data) == 0:
        print('ERROR: Output is empty or not a JSON object', file=sys.stderr)
        sys.exit(1)
    # Print summary
    doc_type = data.get('_metadata', {}).get('document_type', 'unknown')
    status = data.get('_metadata', {}).get('validation_status', 'unknown')
    field_count = len([k for k in data.keys() if k != '_metadata'])
    print(f'  Type:       {doc_type}')
    print(f'  Validation: {status}')
    print(f'  Fields:     {field_count}')
except json.JSONDecodeError as e:
    print(f'ERROR: Invalid JSON — {e}', file=sys.stderr)
    sys.exit(1)
"; then
    echo "ERROR: Output failed JSON validation" >&2
    exit 3
fi

echo "──────────────────────────────────────────"
echo "SUCCESS: Extraction saved to $OUTPUT_PATH"
