"""
Zoho Books MCP Prompt Templates

This module provides guided workflow templates for common business operations
in Zoho Books through the MCP protocol.

Each prompt is a FastMCP prompt function: its parameters are the prompt's
arguments (FastMCP builds the argument list from the signature), and it returns
the messages the client puts in front of the model. An earlier version
returned an ``mcp.types.Prompt`` object instead. FastMCP does not treat that as
a prompt definition; it serialises any non-message return value to JSON and
sends it as the message text, so clients got a JSON dump of the argument list
and no guidance. Returning messages is the shape FastMCP renders as intended.

The steps name this server's tools so the model can follow them without
guessing. Keep them in step with ``register_tools`` in ``server.py``.
upload_receipt is left out on purpose: it raises NotImplementedError.

Argument descriptions go in ``Field(description=...)``: FastMCP builds the
prompt's argument list from the signature and its pydantic metadata, and
ignores the docstring's Args section.
"""

import logging
from typing import Annotated, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import Message, UserMessage
from pydantic import Field

logger = logging.getLogger(__name__)


def _details(**values: Optional[str]) -> str:
    """Render the arguments the caller gave as a bullet list.

    Optional arguments the caller left out (None) are omitted, so the model is
    not shown fields with no value. A value the caller did send, even an empty
    string, is kept, so a required field never drops out of the prompt unseen.
    """
    lines = [
        f"- {name.replace('_', ' ').capitalize()}: {value}"
        for name, value in values.items()
        if value is not None
    ]
    return "\n".join(lines)


def register_prompts(mcp: FastMCP) -> None:
    """
    Register all MCP prompt templates with the server.

    Args:
        mcp: The FastMCP server instance
    """

    @mcp.prompt(
        "invoice_collection_workflow",
        description=(
            "Complete workflow for creating, sending, and collecting payment for an invoice"
        ),
    )
    async def invoice_collection_workflow(
        customer_info: Annotated[
            str,
            Field(description="Customer name, ID, or indication of new customer"),
        ],
        items_info: Annotated[
            str,
            Field(description="List of items/services with quantities and rates"),
        ],
        send_preference: Annotated[
            str,
            Field(
                description="How to handle the invoice after creation (email, draft, mark as sent)"
            ),
        ],
        payment_terms: Annotated[
            Optional[str],
            Field(description="Payment terms (e.g., Net 30, Due on receipt)"),
        ] = None,
        payment_reminder: Annotated[
            Optional[str],
            Field(description="Whether to set up automatic payment reminders"),
        ] = None,
    ) -> List[Message]:
        """Complete invoice-to-payment cycle workflow."""
        logger.info("Creating invoice collection workflow prompt")
        details = _details(
            customer=customer_info,
            items=items_info,
            send_preference=send_preference,
            payment_terms=payment_terms,
            payment_reminder=payment_reminder,
        )
        return [
            UserMessage(
                f"""Help me take an invoice in Zoho Books from creation to payment.

{details}

Work through these steps and confirm with me before each step that changes data:

1. Find the customer with list_contacts (search by name) or get_contact (by ID).
   If no customer matches, create one with create_customer.
2. Check the items with list_items, then build the line items with quantities and rates.
3. Create the invoice with create_invoice, applying the payment terms if I gave any.
4. Act on my send preference: email_invoice to email it, mark_invoice_as_sent if I
   send it myself, or leave it as a draft.
5. If I asked for reminders, use send_payment_reminder once the invoice is overdue.
6. When the customer pays, record it with record_payment.

Finish with a summary: invoice number, customer, total, due date and status."""
            )
        ]

    @mcp.prompt(
        "monthly_invoicing",
        description="Efficient workflow for creating multiple invoices for recurring clients",
    )
    async def monthly_invoicing(
        client_selection: Annotated[
            str,
            Field(description="Which clients to invoice (all, specific list, or by category)"),
        ],
        billing_period: Annotated[
            str,
            Field(description="Period being billed for (current month, previous month, custom)"),
        ],
        services_items: Annotated[
            str,
            Field(description="Services/products to bill (same for all or varies by client)"),
        ],
        send_action: Annotated[
            str,
            Field(description="What to do after creation (send all, schedule, keep as drafts)"),
        ],
        payment_terms: Annotated[
            Optional[str],
            Field(description="Payment terms to apply to all invoices"),
        ] = None,
    ) -> List[Message]:
        """Bulk invoice creation for recurring clients."""
        logger.info("Creating monthly invoicing workflow prompt")
        details = _details(
            clients=client_selection,
            billing_period=billing_period,
            services=services_items,
            send_action=send_action,
            payment_terms=payment_terms,
        )
        return [
            UserMessage(
                f"""Help me create this period's invoices for my recurring clients in Zoho Books.

{details}

Work through these steps:

1. Build the client list with list_contacts (contact_type "customer") and confirm it with me.
2. Check the services with list_items and work out the line items for each client.
3. Check list_invoices for invoices already raised for this billing period, so no
   client is billed twice.
4. Show me the planned invoices (client, line items, total) and wait for my approval.
5. Create each invoice with create_invoice. If one fails, note the error and go on
   with the rest.
6. Act on the send action: email_invoice for each, mark_invoice_as_sent, or leave drafts.

Finish with a summary: invoices created, any failures and why, and the total amount billed."""
            )
        ]

    @mcp.prompt(
        "expense_tracking_workflow",
        description=(
            "Comprehensive workflow for recording, categorizing, and managing business expenses"
        ),
    )
    async def expense_tracking_workflow(
        expense_count: Annotated[
            str,
            Field(description="Number of expenses to record (single, multiple, bulk)"),
        ],
        expense_date: Annotated[
            str,
            Field(description="Date of the expense(s)"),
        ],
        amount: Annotated[
            str,
            Field(description="Amount of the expense"),
        ],
        vendor: Annotated[
            str,
            Field(description="Vendor or payee name"),
        ],
        category: Annotated[
            str,
            Field(description="Expense category (travel, meals, office supplies, etc.)"),
        ],
        description: Annotated[
            Optional[str],
            Field(description="Description of the expense"),
        ] = None,
        payment_method: Annotated[
            Optional[str],
            Field(description="How the expense was paid"),
        ] = None,
        receipt_available: Annotated[
            Optional[str],
            Field(description="Whether receipts are available to attach"),
        ] = None,
        tax_deductible: Annotated[
            Optional[str],
            Field(description="Whether this is a tax-deductible expense"),
        ] = None,
        project_customer: Annotated[
            Optional[str],
            Field(description="Associated project or customer for reimbursable expenses"),
        ] = None,
    ) -> List[Message]:
        """Record and categorize business expenses."""
        logger.info("Creating expense tracking workflow prompt")
        details = _details(
            expense_count=expense_count,
            date=expense_date,
            amount=amount,
            vendor=vendor,
            category=category,
            description=description,
            payment_method=payment_method,
            receipt_available=receipt_available,
            tax_deductible=tax_deductible,
            project_or_customer=project_customer,
        )
        return [
            UserMessage(
                f"""Help me record and categorize business expenses in Zoho Books.

{details}

Work through these steps:

1. Find the vendor with list_contacts (contact_type "vendor"). If there is none,
   create it with create_vendor.
2. Pick the expense account that matches the category, and the account it was
   paid from. Ask me if either is unclear.
3. If the expense is billable to a customer or project, find the customer with
   list_contacts and mark the expense billable.
4. Record each expense with create_expense, then fix any wrong category with
   categorize_expense.
5. Check the result with get_expense.

Finish with a summary of each expense recorded: date, vendor, amount and category.
If I have receipts, remind me to attach them in Zoho Books."""
            )
        ]
