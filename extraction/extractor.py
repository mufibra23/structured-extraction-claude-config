"""Three extraction strategies using the Anthropic Claude API.

1. extract_invoice          — Forced tool_use (tool_choice forced to a single tool)
2. extract_with_structured_output — output_config JSON schema (no tools, schema-constrained response)
3. extract_auto_detect      — Multi-tool with tool_choice="auto" (Claude picks the right tool)
"""

import json
import os

import anthropic
from dotenv import load_dotenv

from extraction.schemas import (
    InvoiceExtraction,
    MarketingReportExtraction,
    SupportTicketExtraction,
    get_strict_json_schema,
    get_tool_definition,
)

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-20250514"

# ── Tool definitions built once from Pydantic models ─────────────────────────

INVOICE_TOOL = get_tool_definition(InvoiceExtraction, "extract_invoice")
MARKETING_TOOL = get_tool_definition(MarketingReportExtraction, "extract_marketing_report")
SUPPORT_TOOL = get_tool_definition(SupportTicketExtraction, "extract_support_ticket")

ALL_TOOLS = [INVOICE_TOOL, MARKETING_TOOL, SUPPORT_TOOL]

# ── Schema map for output_config approach ────────────────────────────────────

SCHEMA_MAP = {
    "invoice": InvoiceExtraction,
    "marketing_report": MarketingReportExtraction,
    "support_ticket": SupportTicketExtraction,
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Forced tool_use — extract_invoice
# ─────────────────────────────────────────────────────────────────────────────


def extract_invoice(document_text: str) -> dict:
    """Extract invoice data using forced tool selection.

    Forces Claude to call the extract_invoice tool, guaranteeing structured
    output that matches the InvoiceExtraction schema.
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[INVOICE_TOOL],
        tool_choice={"type": "tool", "name": "extract_invoice"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract all structured data from this invoice document.\n\n"
                    f"<document>\n{document_text}\n</document>"
                ),
            }
        ],
    )

    # With forced tool_choice the first content block is always a tool_use
    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise ValueError("No tool_use block found in response")


# ─────────────────────────────────────────────────────────────────────────────
# 2. output_config JSON schema — extract_with_structured_output
# ─────────────────────────────────────────────────────────────────────────────


def extract_with_structured_output(document_text: str, doc_type: str) -> dict:
    """Extract data using output_config to constrain Claude's response to a JSON schema.

    This approach requires no tools — Claude's entire response is forced to
    conform to the provided JSON schema.

    Args:
        document_text: Raw text of the document.
        doc_type: One of "invoice", "marketing_report", "support_ticket".
    """
    if doc_type not in SCHEMA_MAP:
        raise ValueError(f"Unknown doc_type '{doc_type}'. Must be one of: {list(SCHEMA_MAP.keys())}")

    model_class = SCHEMA_MAP[doc_type]
    schema = get_strict_json_schema(model_class)

    # output_config json_schema requires claude-sonnet-4-5+ models
    STRUCTURED_OUTPUT_MODEL = "claude-sonnet-4-5"

    response = client.messages.create(
        model=STRUCTURED_OUTPUT_MODEL,
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Extract all structured data from this {doc_type.replace('_', ' ')} document. "
                    "Return ONLY the JSON object matching the required schema.\n\n"
                    f"<document>\n{document_text}\n</document>"
                ),
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )

    # With output_config the response text IS the JSON
    return json.loads(response.content[0].text)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Auto-detect multi-tool — extract_auto_detect
# ─────────────────────────────────────────────────────────────────────────────


def extract_auto_detect(document_text: str) -> dict:
    """Let Claude choose which extraction tool to use based on document content.

    All three tools are provided and tool_choice is set to "auto", so Claude
    decides which document type it's looking at and calls the appropriate tool.

    Returns:
        dict with keys: tool_used, data, reasoning
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=ALL_TOOLS,
        tool_choice={"type": "auto"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze this document and extract structured data using the most "
                    "appropriate extraction tool. First briefly explain what type of "
                    "document this is, then call the correct tool.\n\n"
                    f"<document>\n{document_text}\n</document>"
                ),
            }
        ],
    )

    reasoning = ""
    tool_used = None
    data = None

    for block in response.content:
        if block.type == "text":
            reasoning = block.text
        elif block.type == "tool_use":
            tool_used = block.name
            data = block.input

    if tool_used is None:
        raise ValueError("Claude did not call any extraction tool")

    return {
        "tool_used": tool_used,
        "data": data,
        "reasoning": reasoning,
    }
