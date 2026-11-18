"""
Test suite for Zoho Books MCP prompt templates.

The tests go through a real FastMCP server (list_prompts and get_prompt), the
same path a client uses, so they catch a prompt that registers but renders
wrongly. An earlier version of the prompts returned an mcp.types.Prompt
object, which FastMCP renders as a JSON dump of the argument list; reading
the prompt back through get_prompt is what shows that.
"""

import re

import pytest
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

from zoho_mcp.prompts import register_prompts
from zoho_mcp.server import register_tools

PROMPT_ARGUMENTS = {
    "invoice_collection_workflow": {
        "required": {"customer_info", "items_info", "send_preference"},
        "optional": {"payment_terms", "payment_reminder"},
    },
    "monthly_invoicing": {
        "required": {"client_selection", "billing_period", "services_items", "send_action"},
        "optional": {"payment_terms"},
    },
    "expense_tracking_workflow": {
        "required": {"expense_count", "expense_date", "amount", "vendor", "category"},
        "optional": {
            "description",
            "payment_method",
            "receipt_available",
            "tax_deductible",
            "project_customer",
        },
    },
}


@pytest.fixture
def mcp():
    """A real FastMCP server with the prompts registered."""
    server = FastMCP(name="test")
    register_prompts(server)
    return server


async def _render(mcp: FastMCP, name: str, arguments: dict) -> str:
    """Render a prompt through FastMCP and return its single text message."""
    result = await mcp.get_prompt(name, arguments)
    assert len(result.messages) == 1
    message = result.messages[0]
    assert message.role == "user"
    assert isinstance(message.content, TextContent)
    return message.content.text


class TestPrompts:
    """Test suite for MCP prompt templates."""

    def test_register_prompts(self):
        """Every prompt is registered under its name."""
        mock_mcp = MagicMock(spec=FastMCP)
        register_prompts(mock_mcp)

        registered_names = [call[0][0] for call in mock_mcp.prompt.call_args_list]
        assert sorted(registered_names) == sorted(PROMPT_ARGUMENTS)

    @pytest.mark.asyncio
    async def test_prompt_arguments(self, mcp):
        """Each prompt exposes its arguments, with the right ones required."""
        prompts = {p.name: p for p in await mcp.list_prompts()}
        assert set(prompts) == set(PROMPT_ARGUMENTS)

        for name, expected in PROMPT_ARGUMENTS.items():
            arguments = {a.name: a for a in prompts[name].arguments}
            assert set(arguments) == expected["required"] | expected["optional"], name
            for arg_name, arg in arguments.items():
                assert arg.required == (arg_name in expected["required"]), (name, arg_name)
                # A client shows the description next to the field; without
                # it the user sees only a bare name like send_action.
                assert arg.description, (name, arg_name)
            assert prompts[name].description

    @pytest.mark.asyncio
    async def test_invoice_collection_workflow_prompt(self, mcp):
        """The invoice prompt includes the caller's details and the tool steps."""
        text = await _render(
            mcp,
            "invoice_collection_workflow",
            {
                "customer_info": "Acme Corp",
                "items_info": "10 hours consulting at 150",
                "send_preference": "email",
                "payment_terms": "Net 30",
            },
        )

        assert "Acme Corp" in text
        assert "10 hours consulting at 150" in text
        assert "Net 30" in text
        for tool in ("list_contacts", "create_invoice", "email_invoice", "record_payment"):
            assert tool in text
        # The workflow guidance, not a serialised prompt definition.
        assert '"arguments"' not in text
        # An optional argument that was not given is left out.
        assert "Payment reminder" not in text

    @pytest.mark.asyncio
    async def test_monthly_invoicing_prompt(self, mcp):
        """The monthly invoicing prompt includes the caller's details and the tool steps."""
        text = await _render(
            mcp,
            "monthly_invoicing",
            {
                "client_selection": "all retainer clients",
                "billing_period": "current month",
                "services_items": "monthly retainer",
                "send_action": "keep as drafts",
            },
        )

        assert "all retainer clients" in text
        assert "current month" in text
        assert "keep as drafts" in text
        for tool in ("list_contacts", "list_invoices", "create_invoice"):
            assert tool in text
        assert "Payment terms" not in text

    @pytest.mark.asyncio
    async def test_expense_tracking_workflow_prompt(self, mcp):
        """The expense prompt includes the caller's details and the tool steps."""
        text = await _render(
            mcp,
            "expense_tracking_workflow",
            {
                "expense_count": "single",
                "expense_date": "2025-01-15",
                "amount": "120.50",
                "vendor": "Office Depot",
                "category": "office supplies",
                "payment_method": "company card",
            },
        )

        assert "Office Depot" in text
        assert "120.50" in text
        assert "company card" in text
        for tool in ("create_vendor", "create_expense", "categorize_expense", "get_expense"):
            assert tool in text

    @pytest.mark.asyncio
    async def test_empty_required_argument_is_kept(self, mcp):
        """A required argument sent empty still shows in the prompt."""
        text = await _render(
            mcp,
            "invoice_collection_workflow",
            {"customer_info": "", "items_info": "x", "send_preference": "draft"},
        )
        assert "- Customer: \n" in text

    @pytest.mark.asyncio
    async def test_missing_required_argument_is_refused(self, mcp):
        """FastMCP refuses a render that leaves out a required argument."""
        with pytest.raises(Exception, match="customer_info"):
            await mcp.get_prompt(
                "invoice_collection_workflow",
                {"items_info": "x", "send_preference": "draft"},
            )

    @pytest.mark.asyncio
    async def test_prompt_tools_exist(self, mcp):
        """Every tool a prompt names is registered on the server.

        The prompts name tools so the model can follow them; a renamed or
        removed tool would leave a prompt pointing at nothing.
        """
        server = FastMCP(name="tools")
        register_tools(server)
        tool_names = {t.name for t in await server.list_tools()}
        # Any snake_case word that starts with a registered tool's verb
        # (list_, create_, upload_, ...) is read as a tool name, so a
        # misspelled or removed tool is caught whatever its verb.
        verbs = sorted({t.split("_", 1)[0] for t in tool_names})
        tool_word = re.compile(rf"\b(?:{'|'.join(verbs)})_[a-z_]+\b")

        for name, expected in PROMPT_ARGUMENTS.items():
            text = await _render(mcp, name, {arg: "x" for arg in expected["required"]})
            named = set(tool_word.findall(text))
            assert named, name
            assert named <= tool_names, (name, named - tool_names)
