"""Validation and retry logic for structured extraction.

1. validate_extraction   — Schema + business logic validation
2. extract_with_retry    — CCA pattern: extract → validate → feed errors back → retry
"""

import os

import anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from extraction.schemas import (
    InvoiceExtraction,
    MarketingReportExtraction,
    SupportTicketExtraction,
    get_tool_definition,
)

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-20250514"

# ── Maps ─────────────────────────────────────────────────────────────────────

SCHEMA_MAP: dict[str, type] = {
    "extract_invoice": InvoiceExtraction,
    "extract_marketing_report": MarketingReportExtraction,
    "extract_support_ticket": SupportTicketExtraction,
}

TOOL_DEFS = {
    name: get_tool_definition(model_cls, name)
    for name, model_cls in SCHEMA_MAP.items()
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Validation — schema + business logic
# ─────────────────────────────────────────────────────────────────────────────


def _validate_invoice_business_logic(data: dict) -> list[str]:
    """Invoice-specific business rules beyond schema validation."""
    errors = []

    # Line item totals should sum to subtotal (within $0.01)
    line_items = data.get("line_items", [])
    if line_items:
        computed_subtotal = sum(item.get("total", 0) for item in line_items)
        reported_subtotal = data.get("subtotal", 0)
        if abs(computed_subtotal - reported_subtotal) > 0.01:
            errors.append(
                f"Line item totals sum to ${computed_subtotal:.2f} "
                f"but subtotal is ${reported_subtotal:.2f} (difference: "
                f"${abs(computed_subtotal - reported_subtotal):.2f})"
            )

    # Subtotal + tax should equal total_amount
    subtotal = data.get("subtotal", 0)
    tax = data.get("tax_amount") or 0
    total = data.get("total_amount", 0)
    if abs((subtotal + tax) - total) > 0.01:
        errors.append(
            f"subtotal (${subtotal:.2f}) + tax (${tax:.2f}) = "
            f"${subtotal + tax:.2f}, but total_amount is ${total:.2f}"
        )

    # If payment_terms is "other", payment_terms_detail must not be empty
    if data.get("payment_terms") == "other":
        detail = (data.get("payment_terms_detail") or "").strip()
        if not detail:
            errors.append(
                "payment_terms is 'other' but payment_terms_detail is empty — "
                "provide a description of the actual payment terms"
            )

    return errors


def validate_extraction(tool_name: str, data: dict) -> tuple[bool, list[str]]:
    """Validate extracted data against its Pydantic model and business rules.

    Args:
        tool_name: The extraction tool name (e.g. "extract_invoice").
        data: The extracted data dict to validate.

    Returns:
        Tuple of (is_valid, list_of_error_strings).
    """
    if tool_name not in SCHEMA_MAP:
        return False, [f"Unknown tool '{tool_name}'. Expected one of: {list(SCHEMA_MAP.keys())}"]

    errors = []

    # ── Schema validation via Pydantic ───────────────────────────────────
    model_class = SCHEMA_MAP[tool_name]
    try:
        model_class.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = " → ".join(str(part) for part in err["loc"])
            errors.append(f"[schema] {loc}: {err['msg']}")

    # ── Business logic validation ────────────────────────────────────────
    if tool_name == "extract_invoice":
        errors.extend(_validate_invoice_business_logic(data))

    return (len(errors) == 0, errors)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Extract with retry — the CCA correction loop
# ─────────────────────────────────────────────────────────────────────────────


def extract_with_retry(
    document_text: str,
    tool_name: str,
    max_retries: int = 2,
) -> dict:
    """Extract structured data with validation-driven retry.

    The CCA (Claude Correction Agentic) pattern:
      1. Force Claude to call the extraction tool.
      2. Validate the result (schema + business logic).
      3. If invalid, send back the tool_use + a tool_result containing
         the specific errors. Claude sees what went wrong and self-corrects.
      4. Repeat up to max_retries times.

    Args:
        document_text: Raw document text.
        tool_name: Which extraction tool to force ("extract_invoice", etc.).
        max_retries: Maximum correction attempts after the first extraction.

    Returns:
        dict with keys: data, attempts, status, errors
    """
    if tool_name not in SCHEMA_MAP:
        raise ValueError(f"Unknown tool '{tool_name}'. Expected one of: {list(SCHEMA_MAP.keys())}")

    tool_def = TOOL_DEFS[tool_name]

    # ── Initial extraction ───────────────────────────────────────────────
    messages = [
        {
            "role": "user",
            "content": (
                "Extract all structured data from this document. "
                "Be precise with numeric values and calculations.\n\n"
                f"<document>\n{document_text}\n</document>"
            ),
        }
    ]

    attempts = 0

    for attempt in range(1 + max_retries):
        attempts = attempt + 1

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=[tool_def],
            tool_choice={"type": "tool", "name": tool_name},
            messages=messages,
        )

        # Find the tool_use block
        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use":
                tool_use_block = block
                break

        if tool_use_block is None:
            raise ValueError(f"No tool_use block in response (attempt {attempts})")

        data = tool_use_block.input

        # ── Validate ─────────────────────────────────────────────────────
        is_valid, errors = validate_extraction(tool_name, data)

        if is_valid:
            return {
                "data": data,
                "attempts": attempts,
                "status": "success",
                "errors": [],
            }

        # ── Build retry conversation ─────────────────────────────────────
        # Append Claude's tool_use response as an assistant message,
        # then a user message with tool_result containing the errors.
        # This lets Claude see exactly what it produced and what was wrong.

        if attempt < max_retries:
            error_text = "VALIDATION FAILED. Fix these errors and try again:\n"
            for i, err in enumerate(errors, 1):
                error_text += f"  {i}. {err}\n"

            messages.append({"role": "assistant", "content": response.content})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_block.id,
                            "is_error": True,
                            "content": error_text,
                        }
                    ],
                }
            )

    # Exhausted all retries
    return {
        "data": data,
        "attempts": attempts,
        "status": "failed_validation",
        "errors": errors,
    }
