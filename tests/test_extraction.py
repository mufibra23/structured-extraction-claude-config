"""Unit tests for schema generation and validation logic. No real API calls."""

from extraction.schemas import (
    InvoiceExtraction,
    MarketingReportExtraction,
    get_tool_definition,
)
from extraction.validator import validate_extraction


# ── Helpers ──────────────────────────────────────────────────────────────────


def _valid_invoice_data(**overrides) -> dict:
    """Build a valid invoice dict, with optional field overrides."""
    base = {
        "invoice_number": "INV-2026-0342",
        "vendor_name": "PT. Digital Nusantara Solutions",
        "invoice_date": "2026-03-15",
        "due_date": "2026-04-14",
        "currency": "USD",
        "line_items": [
            {"description": "AI Dashboard Setup", "quantity": 1, "unit_price": 3500.00, "total": 3500.00},
            {"description": "Monthly Maintenance", "quantity": 3, "unit_price": 750.00, "total": 2250.00},
            {"description": "Report Templates", "quantity": 5, "unit_price": 200.00, "total": 1000.00},
            {"description": "GA4+BigQuery Integration", "quantity": 1, "unit_price": 1500.00, "total": 1500.00},
        ],
        "subtotal": 8250.00,
        "tax_amount": 907.50,
        "total_amount": 9157.50,
        "payment_terms": "net_30",
    }
    base.update(overrides)
    return base


# ── Schema generation tests ──────────────────────────────────────────────────


class TestInvoiceSchemaGeneration:
    def test_tool_definition_has_correct_name(self):
        tool = get_tool_definition(InvoiceExtraction, "extract_invoice")
        assert tool["name"] == "extract_invoice"

    def test_tool_definition_has_input_schema(self):
        tool = get_tool_definition(InvoiceExtraction, "extract_invoice")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "invoice_number" in schema["properties"]
        assert "vendor_name" in schema["properties"]
        assert "line_items" in schema["properties"]
        assert "subtotal" in schema["properties"]
        assert "total_amount" in schema["properties"]
        assert "payment_terms" in schema["properties"]

    def test_tool_definition_has_description(self):
        tool = get_tool_definition(InvoiceExtraction, "extract_invoice")
        assert len(tool["description"]) > 0

    def test_required_fields_present(self):
        tool = get_tool_definition(InvoiceExtraction, "extract_invoice")
        required = tool["input_schema"]["required"]
        assert "invoice_number" in required
        assert "vendor_name" in required
        assert "total_amount" in required

    def test_optional_fields_not_required(self):
        tool = get_tool_definition(InvoiceExtraction, "extract_invoice")
        required = tool["input_schema"]["required"]
        assert "due_date" not in required
        assert "payment_terms_detail" not in required


# ── Validation pass tests ────────────────────────────────────────────────────


class TestInvoiceValidationPass:
    def test_valid_invoice_passes(self):
        is_valid, errors = validate_extraction("extract_invoice", _valid_invoice_data())
        assert is_valid is True
        assert errors == []

    def test_valid_invoice_with_zero_tax(self):
        data = _valid_invoice_data(tax_amount=0, total_amount=8250.00)
        is_valid, errors = validate_extraction("extract_invoice", data)
        assert is_valid is True
        assert errors == []

    def test_valid_invoice_with_null_tax(self):
        data = _valid_invoice_data(tax_amount=None, total_amount=8250.00)
        is_valid, errors = validate_extraction("extract_invoice", data)
        assert is_valid is True
        assert errors == []


# ── Validation failure tests ─────────────────────────────────────────────────


class TestInvoiceValidationMathError:
    def test_line_items_not_summing_to_subtotal(self):
        data = _valid_invoice_data(subtotal=9999.00, total_amount=10906.50, tax_amount=907.50)
        is_valid, errors = validate_extraction("extract_invoice", data)
        assert is_valid is False
        assert any("Line item totals sum to" in e for e in errors)

    def test_subtotal_plus_tax_not_equal_total(self):
        data = _valid_invoice_data(total_amount=5000.00)
        is_valid, errors = validate_extraction("extract_invoice", data)
        assert is_valid is False
        assert any("subtotal" in e and "tax" in e for e in errors)

    def test_both_math_errors_at_once(self):
        data = _valid_invoice_data(subtotal=1000.00, tax_amount=100.00, total_amount=5000.00)
        is_valid, errors = validate_extraction("extract_invoice", data)
        assert is_valid is False
        # Should catch both: line items vs subtotal AND subtotal+tax vs total
        math_errors = [e for e in errors if "sum to" in e or "subtotal" in e]
        assert len(math_errors) >= 2

    def test_payment_terms_other_missing_detail(self):
        data = _valid_invoice_data(payment_terms="other", payment_terms_detail=None)
        is_valid, errors = validate_extraction("extract_invoice", data)
        assert is_valid is False
        assert any("payment_terms_detail" in e for e in errors)

    def test_payment_terms_other_with_detail_passes(self):
        data = _valid_invoice_data(payment_terms="other", payment_terms_detail="50% upfront, 50% on delivery")
        is_valid, errors = validate_extraction("extract_invoice", data)
        assert is_valid is True

    def test_unknown_tool_name_fails(self):
        is_valid, errors = validate_extraction("extract_bogus", {})
        assert is_valid is False
        assert any("Unknown tool" in e for e in errors)

    def test_missing_required_field_fails_schema(self):
        data = _valid_invoice_data()
        del data["invoice_number"]
        is_valid, errors = validate_extraction("extract_invoice", data)
        assert is_valid is False
        assert any("[schema]" in e for e in errors)


# ── Marketing report schema tests ────────────────────────────────────────────


class TestMarketingReportSchema:
    def test_channels_field_is_array(self):
        tool = get_tool_definition(MarketingReportExtraction, "extract_marketing_report")
        channels_prop = tool["input_schema"]["properties"]["channels"]
        assert channels_prop["type"] == "array"

    def test_channels_items_reference_channel_performance(self):
        tool = get_tool_definition(MarketingReportExtraction, "extract_marketing_report")
        channels_prop = tool["input_schema"]["properties"]["channels"]
        # Items should either have $ref to ChannelPerformance or inline properties
        items = channels_prop["items"]
        assert "$ref" in items or "properties" in items

    def test_key_insights_is_array_of_strings(self):
        tool = get_tool_definition(MarketingReportExtraction, "extract_marketing_report")
        insights = tool["input_schema"]["properties"]["key_insights"]
        assert insights["type"] == "array"
        assert insights["items"]["type"] == "string"

    def test_recommendations_is_array(self):
        tool = get_tool_definition(MarketingReportExtraction, "extract_marketing_report")
        recs = tool["input_schema"]["properties"]["recommendations"]
        assert recs["type"] == "array"
