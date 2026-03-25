#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# ci/batch_extract.sh
#
# Process all documents in a directory using Claude Code in print mode.
# Each document is extracted independently with a per-document budget cap.
#
# Usage:
#   ./ci/batch_extract.sh <input_dir> <output_dir>
#
# Arguments:
#   $1  Input directory containing document files (required)
#   $2  Output directory for JSON results (required)
#
# Exit codes:
#   0  All documents processed successfully
#   1  Usage error (missing arguments, directory not found)
#   2  Some documents failed (partial success)
# ──────────────────────────────────────────────────────────────────────────────

set -uo pipefail

# ── Args ─────────────────────────────────────────────────────────────────────

INPUT_DIR="${1:-}"
OUTPUT_DIR="${2:-}"

if [[ -z "$INPUT_DIR" || -z "$OUTPUT_DIR" ]]; then
    echo "ERROR: Both input and output directories are required." >&2
    echo "Usage: $0 <input_dir> <output_dir>" >&2
    exit 1
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "ERROR: Input directory not found: $INPUT_DIR" >&2
    exit 1
fi

# Create output directory if needed
mkdir -p "$OUTPUT_DIR"

# ── Process ──────────────────────────────────────────────────────────────────

TOTAL=0
SUCCEEDED=0
FAILED=0
FAILED_FILES=""

echo "══════════════════════════════════════════════════"
echo "  Batch Extraction"
echo "  Input:  $INPUT_DIR"
echo "  Output: $OUTPUT_DIR"
echo "══════════════════════════════════════════════════"
echo ""

# Find all .txt files recursively
while IFS= read -r -d '' FILEPATH; do
    TOTAL=$((TOTAL + 1))
    FILENAME=$(basename "$FILEPATH" .txt)
    OUTPUT_FILE="${OUTPUT_DIR}/${FILENAME}_extracted.json"

    echo "[$TOTAL] Processing: $FILEPATH"

    # Build extraction prompt
    PROMPT="Read the document at ${FILEPATH}. \
Determine its type (invoice, marketing report, or support ticket). \
Extract all structured data following the schemas in extraction/schemas.py. \
For invoices, validate that line item totals sum to subtotal and subtotal + tax = total. \
Output ONLY the final JSON object — no markdown, no explanation, no code fences. \
Include a \"_metadata\" field with: \"source_file\", \"document_type\", \
\"extraction_timestamp\" (ISO 8601), and \"validation_status\" (pass/fail)."

    # Run Claude with per-document budget cap
    if claude -p \
        --output-format json \
        --max-turns 3 \
        --max-budget-usd 0.50 \
        --model sonnet \
        "$PROMPT" \
        > "$OUTPUT_FILE" 2>/dev/null; then

        # Validate the output is real JSON
        if python -c "
import json, sys
try:
    with open('${OUTPUT_FILE}') as f:
        data = json.load(f)
    if not isinstance(data, dict) or len(data) == 0:
        sys.exit(1)
    doc_type = data.get('_metadata', {}).get('document_type', 'unknown')
    print(f'     -> {doc_type} — OK')
except (json.JSONDecodeError, Exception):
    sys.exit(1)
"; then
            SUCCEEDED=$((SUCCEEDED + 1))
        else
            FAILED=$((FAILED + 1))
            FAILED_FILES="${FAILED_FILES}\n     - ${FILEPATH} (invalid JSON)"
            echo "     -> FAILED: invalid JSON output"
            rm -f "$OUTPUT_FILE"
        fi
    else
        FAILED=$((FAILED + 1))
        FAILED_FILES="${FAILED_FILES}\n     - ${FILEPATH} (claude error)"
        echo "     -> FAILED: claude extraction error"
        rm -f "$OUTPUT_FILE"
    fi

done < <(find "$INPUT_DIR" -type f -name "*.txt" -print0 | sort -z)

# ── Report ───────────────────────────────────────────────────────────────────

echo ""
echo "══════════════════════════════════════════════════"
echo "  Batch Complete"
echo "══════════════════════════════════════════════════"
echo "  Total:     $TOTAL"
echo "  Succeeded: $SUCCEEDED"
echo "  Failed:    $FAILED"

if [[ $FAILED -gt 0 ]]; then
    echo ""
    echo "  Failed files:"
    echo -e "$FAILED_FILES"
    echo ""
    echo "══════════════════════════════════════════════════"
    exit 2
fi

echo "══════════════════════════════════════════════════"
exit 0
