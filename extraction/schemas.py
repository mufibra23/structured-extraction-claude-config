"""Pydantic v2 schemas for structured data extraction via Claude tool_use API."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────


class PaymentTerms(str, Enum):
    NET_30 = "net_30"
    NET_60 = "net_60"
    NET_90 = "net_90"
    DUE_ON_RECEIPT = "due_on_receipt"
    OTHER = "other"


class TicketCategory(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    FEATURE_REQUEST = "feature_request"
    OTHER = "other"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Nested models ─────────────────────────────────────────────────────────────


class LineItem(BaseModel):
    """A single line item on an invoice."""

    description: str = Field(description="Description of the product or service")
    quantity: float = Field(description="Quantity of units")
    unit_price: float = Field(description="Price per unit")
    total: float = Field(description="Total cost for this line item (quantity * unit_price)")


class ChannelPerformance(BaseModel):
    """Performance metrics for a single marketing channel."""

    channel: str = Field(description="Marketing channel name (e.g. Google Ads, Facebook, Email)")
    spend: Optional[float] = Field(default=None, description="Total spend on this channel")
    impressions: Optional[int] = Field(default=None, description="Number of impressions")
    clicks: Optional[int] = Field(default=None, description="Number of clicks")
    conversions: Optional[int] = Field(default=None, description="Number of conversions")
    revenue: Optional[float] = Field(default=None, description="Revenue attributed to this channel")
    roas: Optional[float] = Field(default=None, description="Return on ad spend (revenue / spend)")


# ── Extraction models ─────────────────────────────────────────────────────────


class InvoiceExtraction(BaseModel):
    """Structured data extracted from an invoice document."""

    invoice_number: str = Field(description="Unique invoice identifier")
    vendor_name: str = Field(description="Name of the vendor or supplier")
    invoice_date: str = Field(description="Date the invoice was issued (YYYY-MM-DD)")
    due_date: Optional[str] = Field(default=None, description="Payment due date (YYYY-MM-DD)")
    currency: str = Field(description="3-letter ISO 4217 currency code (e.g. USD, EUR, GBP)")
    line_items: list[LineItem] = Field(description="List of itemised charges on the invoice")
    subtotal: float = Field(description="Sum of all line item totals before tax")
    tax_amount: Optional[float] = Field(default=None, description="Total tax amount applied")
    total_amount: float = Field(description="Final amount due including tax")
    payment_terms: PaymentTerms = Field(
        description="Payment terms category (net_30, net_60, net_90, due_on_receipt, or other)"
    )
    payment_terms_detail: Optional[str] = Field(
        default=None,
        description="Additional detail when payment_terms is 'other' or needs clarification",
    )


class MarketingReportExtraction(BaseModel):
    """Structured data extracted from a marketing performance report."""

    report_period: str = Field(description="Time period covered by the report (e.g. 'Q1 2025', 'March 2025')")
    total_spend: Optional[float] = Field(default=None, description="Total marketing spend across all channels")
    total_revenue: Optional[float] = Field(
        default=None, description="Total revenue attributed to marketing efforts"
    )
    channels: list[ChannelPerformance] = Field(
        description="Per-channel performance breakdown"
    )
    key_insights: list[str] = Field(description="Key findings and insights from the report")
    recommendations: list[str] = Field(
        default=[], description="Actionable recommendations based on the data"
    )


class SupportTicketExtraction(BaseModel):
    """Structured data extracted from a customer support ticket."""

    ticket_id: Optional[str] = Field(default=None, description="Support ticket identifier")
    customer_name: Optional[str] = Field(default=None, description="Name of the customer")
    customer_email: Optional[str] = Field(default=None, description="Customer email address")
    subject: str = Field(description="Brief subject or title of the ticket")
    category: TicketCategory = Field(
        description="Ticket category (billing, technical, account, feature_request, or other)"
    )
    priority: TicketPriority = Field(description="Ticket priority level (low, medium, high, critical)")
    issue_summary: str = Field(description="Concise summary of the customer's issue")
    action_items: list[str] = Field(description="Recommended next steps to resolve the issue")
    sentiment: str = Field(
        description="Overall customer sentiment (e.g. frustrated, neutral, satisfied)"
    )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _add_additional_properties_false(schema: dict) -> dict:
    """Recursively set additionalProperties: false on all object types.

    Required by the Claude API output_config json_schema format.
    """
    if isinstance(schema, dict):
        if schema.get("type") == "object" and "additionalProperties" not in schema:
            schema["additionalProperties"] = False
        for value in schema.values():
            if isinstance(value, dict):
                _add_additional_properties_false(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _add_additional_properties_false(item)
    return schema


def get_strict_json_schema(model_class: type[BaseModel]) -> dict:
    """Generate a JSON schema compatible with Claude's output_config format.

    Adds additionalProperties: false to all object types as required by the API.
    """
    schema = model_class.model_json_schema()
    return _add_additional_properties_false(schema)


def get_tool_definition(model_class: type[BaseModel], tool_name: str) -> dict:
    """Convert a Pydantic v2 model into a Claude tool_use definition.

    Args:
        model_class: The Pydantic model class to convert.
        tool_name: The name to assign to the tool.

    Returns:
        A dict matching the Claude API tool schema format.
    """
    schema = model_class.model_json_schema()

    # Pull out $defs (nested models / enums) so Claude sees a self-contained schema
    defs = schema.pop("$defs", {})

    return {
        "name": tool_name,
        "description": schema.get("description", f"Extract structured {tool_name} data"),
        "input_schema": {
            **schema,
            # Re-attach definitions if present — Claude resolves $ref internally
            **({"$defs": defs} if defs else {}),
        },
    }
