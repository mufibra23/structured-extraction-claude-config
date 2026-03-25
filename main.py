"""Demo script — runs all 4 extraction modes on sample data."""

import json
import sys
from pathlib import Path

from extraction.extractor import (
    extract_auto_detect,
    extract_invoice,
    extract_with_structured_output,
)
from extraction.validator import extract_with_retry


def load_sample(relative_path: str) -> str:
    path = Path(__file__).parent / relative_path
    return path.read_text(encoding="utf-8")


def print_result(label: str, data: dict) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"{'=' * 70}")
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ─────────────────────────────────────────────────────────────────────────────


def demo_1_forced_tool_use():
    """Invoice extraction with forced tool_choice."""
    print("\n[Demo 1] Invoice Extraction — Forced tool_use")
    print("-" * 50)

    text = load_sample("sample_data/invoices/invoice_001.txt")
    result = extract_invoice(text)

    print_result("Extracted Invoice (forced tool_use)", result)
    return result


def demo_2_structured_output():
    """Marketing report extraction with output_config JSON schema."""
    print("\n[Demo 2] Marketing Report — output_config Structured Output")
    print("-" * 50)

    text = load_sample("sample_data/marketing_reports/q1_2026_report.txt")
    result = extract_with_structured_output(text, "marketing_report")

    print_result("Extracted Marketing Report (output_config)", result)
    return result


def demo_3_auto_detect():
    """Support ticket extraction with auto-detect multi-tool."""
    print("\n[Demo 3] Support Ticket — Auto-detect Multi-tool")
    print("-" * 50)

    text = load_sample("sample_data/support_tickets/ticket_001.txt")
    result = extract_auto_detect(text)

    print(f"\nClaude's reasoning: {result['reasoning'][:200]}...")
    print(f"Tool selected: {result['tool_used']}")
    print_result("Extracted Support Ticket (auto-detect)", result["data"])
    return result


def demo_4_validation_retry():
    """Invoice extraction with validation-retry loop (CCA pattern)."""
    print("\n[Demo 4] Invoice — Validation + Retry Loop (CCA Pattern)")
    print("-" * 50)

    text = load_sample("sample_data/invoices/invoice_001.txt")
    result = extract_with_retry(text, "extract_invoice", max_retries=2)

    print(f"\nStatus:   {result['status']}")
    print(f"Attempts: {result['attempts']}")
    if result["errors"]:
        print(f"Remaining errors: {result['errors']}")
    print_result("Extracted Invoice (with validation)", result["data"])
    return result


# ─────────────────────────────────────────────────────────────────────────────


DEMOS = {
    "1": ("Forced tool_use (invoice)", demo_1_forced_tool_use),
    "2": ("output_config structured output (marketing)", demo_2_structured_output),
    "3": ("Auto-detect multi-tool (support ticket)", demo_3_auto_detect),
    "4": ("Validation + retry loop (invoice)", demo_4_validation_retry),
}


def main():
    # If specific demo numbers passed as args, run only those
    selected = sys.argv[1:] if len(sys.argv) > 1 else DEMOS.keys()

    for key in selected:
        if key not in DEMOS:
            print(f"Unknown demo '{key}'. Choose from: {list(DEMOS.keys())}")
            continue
        label, func = DEMOS[key]
        try:
            func()
        except Exception as e:
            print(f"\n[Demo {key}] FAILED: {e}")

    print(f"\n{'=' * 70}")
    print("  All demos complete.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
