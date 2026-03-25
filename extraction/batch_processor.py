"""Batch extraction using the Anthropic Message Batches API.

Submits many documents in a single batch request for cost-efficient,
high-throughput extraction. 50% cheaper than real-time API calls.

Functions:
    create_extraction_batch  — Submit documents, get batch_id
    poll_batch               — Wait for completion, return parsed results
    process_documents_batch  — End-to-end wrapper
"""

import os
import time

import anthropic
from dotenv import load_dotenv

from extraction.schemas import (
    InvoiceExtraction,
    MarketingReportExtraction,
    SupportTicketExtraction,
    get_tool_definition,
)

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-20250514"

# ── Tool lookup by doc type ──────────────────────────────────────────────────

TOOL_MAP = {
    "invoice": ("extract_invoice", get_tool_definition(InvoiceExtraction, "extract_invoice")),
    "marketing_report": (
        "extract_marketing_report",
        get_tool_definition(MarketingReportExtraction, "extract_marketing_report"),
    ),
    "support_ticket": (
        "extract_support_ticket",
        get_tool_definition(SupportTicketExtraction, "extract_support_ticket"),
    ),
}

PROMPT_MAP = {
    "invoice": "Extract all structured data from this invoice document.",
    "marketing_report": "Extract all structured data from this marketing report.",
    "support_ticket": "Extract all structured data from this support ticket.",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Create batch
# ─────────────────────────────────────────────────────────────────────────────


def create_extraction_batch(documents: list[dict]) -> str:
    """Submit a list of documents as a Message Batch for extraction.

    Args:
        documents: List of dicts, each with keys:
            - id   (str): Unique document identifier, used as custom_id
            - text (str): Raw document text
            - type (str): One of "invoice", "marketing_report", "support_ticket"

    Returns:
        The batch_id string for polling.
    """
    requests = []

    for doc in documents:
        doc_type = doc["type"]
        if doc_type not in TOOL_MAP:
            raise ValueError(
                f"Unknown doc type '{doc_type}' for document '{doc['id']}'. "
                f"Must be one of: {list(TOOL_MAP.keys())}"
            )

        tool_name, tool_def = TOOL_MAP[doc_type]

        requests.append({
            "custom_id": doc["id"],
            "params": {
                "model": MODEL,
                "max_tokens": 4096,
                "tools": [tool_def],
                "tool_choice": {"type": "tool", "name": tool_name},
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"{PROMPT_MAP[doc_type]}\n\n"
                            f"<document>\n{doc['text']}\n</document>"
                        ),
                    }
                ],
            },
        })

    batch = client.messages.batches.create(requests=requests)
    print(f"Batch created: {batch.id} ({len(requests)} requests)")
    return batch.id


# ─────────────────────────────────────────────────────────────────────────────
# 2. Poll batch until complete
# ─────────────────────────────────────────────────────────────────────────────


def poll_batch(batch_id: str, poll_interval: int = 30) -> list[dict]:
    """Poll a batch until it reaches a terminal state, then retrieve results.

    Args:
        batch_id: The batch ID returned by create_extraction_batch.
        poll_interval: Seconds between status checks (default 30).

    Returns:
        List of result dicts, each with keys:
            - custom_id (str): The document ID from submission
            - status    (str): "succeeded", "errored", "canceled", or "expired"
            - data      (dict | None): Extracted data if succeeded
            - error     (str | None): Error message if failed
    """
    terminal_states = {"ended", "canceled", "expired"}

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        status = batch.processing_status

        counts = batch.request_counts
        total = counts.processing + counts.succeeded + counts.errored + counts.canceled + counts.expired
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        print(f"Batch {batch_id}: {status} — {done}/{total} complete")

        if status in terminal_states:
            break

        time.sleep(poll_interval)

    # ── Retrieve results ─────────────────────────────────────────────────
    results = []

    for entry in client.messages.batches.results(batch_id):
        result = {
            "custom_id": entry.custom_id,
            "status": entry.result.type,
            "data": None,
            "error": None,
        }

        if entry.result.type == "succeeded":
            message = entry.result.message
            for block in message.content:
                if block.type == "tool_use":
                    result["data"] = block.input
                    break
        elif entry.result.type == "errored":
            result["error"] = str(entry.result.error)
        elif entry.result.type == "canceled":
            result["error"] = "Request was canceled"
        elif entry.result.type == "expired":
            result["error"] = "Request expired before processing"

        results.append(result)

    print(f"Retrieved {len(results)} results from batch {batch_id}")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 3. End-to-end wrapper
# ─────────────────────────────────────────────────────────────────────────────


def process_documents_batch(
    documents: list[dict],
    poll_interval: int = 30,
) -> dict:
    """End-to-end batch extraction: submit → poll → return structured results.

    Args:
        documents: List of {"id": ..., "text": ..., "type": ...} dicts.
        poll_interval: Seconds between status checks.

    Returns:
        Dict with keys:
            - batch_id (str)
            - results  (list[dict]): Per-document results keyed by custom_id
            - summary  (dict): Counts of succeeded / errored / total
    """
    batch_id = create_extraction_batch(documents)
    results = poll_batch(batch_id, poll_interval=poll_interval)

    succeeded = sum(1 for r in results if r["status"] == "succeeded")
    errored = len(results) - succeeded

    return {
        "batch_id": batch_id,
        "results": results,
        "summary": {
            "total": len(results),
            "succeeded": succeeded,
            "errored": errored,
        },
    }
