"""Multi-pass cross-file review for extraction consistency.

After extracting structured data from multiple documents, this module
sends all results to Claude for a consistency audit — catching issues
that only surface when comparing documents side-by-side.
"""

import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# output_config json_schema requires claude-sonnet-4-5+ models
MODEL = "claude-sonnet-4-5"

REVIEW_SCHEMA = {
    "type": "object",
    "required": ["issues_found", "summary"],
    "additionalProperties": False,
    "properties": {
        "issues_found": {
            "type": "array",
            "description": "List of consistency issues detected across documents",
            "items": {
                "type": "object",
                "required": ["issue_type", "severity", "description", "affected_documents"],
                "additionalProperties": False,
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "enum": [
                            "entity_name_mismatch",
                            "currency_mismatch",
                            "date_sequence_issue",
                            "duplicate_invoice_number",
                            "math_error",
                            "missing_data",
                            "other",
                        ],
                        "description": "Category of the consistency issue",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "How critical this issue is",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed explanation of the issue",
                    },
                    "affected_documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of documents involved in this issue",
                    },
                    "suggested_fix": {
                        "type": "string",
                        "description": "Recommended action to resolve the issue",
                    },
                },
            },
        },
        "summary": {
            "type": "object",
            "required": ["total_documents_reviewed", "total_issues", "issues_by_severity", "overview"],
            "additionalProperties": False,
            "properties": {
                "total_documents_reviewed": {
                    "type": "integer",
                    "description": "Number of extractions reviewed",
                },
                "total_issues": {
                    "type": "integer",
                    "description": "Total number of issues found",
                },
                "issues_by_severity": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "high": {"type": "integer"},
                        "medium": {"type": "integer"},
                        "low": {"type": "integer"},
                    },
                    "required": ["high", "medium", "low"],
                },
                "overview": {
                    "type": "string",
                    "description": "Brief narrative summary of findings",
                },
            },
        },
    },
}


def cross_file_review(extractions: list[dict]) -> dict:
    """Review multiple extraction results for cross-document consistency.

    Sends all extractions to Claude in a single call. Claude compares them
    and flags issues that only surface when looking across documents:

    - Same entity appearing with different names or spellings
    - Currency mismatches between related documents
    - Date sequence issues (e.g. due date before invoice date)
    - Duplicate invoice numbers across different documents
    - Math errors (totals not adding up)
    - Missing data that should be present given other documents

    Args:
        extractions: List of dicts, each with keys:
            - id   (str): Document identifier
            - type (str): Document type ("invoice", "marketing_report", etc.)
            - data (dict): The extracted structured data

    Returns:
        Dict matching REVIEW_SCHEMA with issues_found and summary.
    """
    # Format extractions for the prompt
    docs_text = ""
    for ext in extractions:
        docs_text += f"\n--- Document: {ext['id']} (type: {ext['type']}) ---\n"
        docs_text += json.dumps(ext["data"], indent=2)
        docs_text += "\n"

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    "You are a data quality auditor. Review the following extracted "
                    "documents and identify any cross-document consistency issues.\n\n"
                    "Check for:\n"
                    "1. ENTITY NAME MISMATCHES: Same company/person with different "
                    "spellings or names across documents\n"
                    "2. CURRENCY MISMATCHES: Inconsistent currencies between related "
                    "documents\n"
                    "3. DATE SEQUENCE ISSUES: Dates that don't make logical sense "
                    "(e.g., due date before invoice date, report covering future periods)\n"
                    "4. DUPLICATE INVOICE NUMBERS: Same invoice number appearing in "
                    "multiple documents\n"
                    "5. MATH ERRORS: Totals that don't add up, ROAS calculations that "
                    "don't match spend/revenue, percentages that are wrong\n"
                    "6. MISSING DATA: Fields that should be populated given context "
                    "from other documents\n\n"
                    "If no issues are found, return an empty issues_found array.\n\n"
                    f"<documents>{docs_text}\n</documents>"
                ),
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": REVIEW_SCHEMA,
            }
        },
    )

    return json.loads(response.content[0].text)
