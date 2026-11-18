"""
Test suite for Zoho Books MCP resources.

The tests read each resource through a real FastMCP server (list_resources and
read_resource), the path a client uses, with the Zoho API mocked out. An
earlier version of these tests captured the decorated functions with a
hand-written fake of mcp.resource; when the decorator's signature and the
resource set changed, the fake went stale and the tests failed without saying
anything about the resources themselves.
"""

from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from zoho_mcp.resources import register_resources

EXPECTED_URIS = {
    "dashboard://summary",
    "invoice://overdue",
    "invoice://unpaid",
    "payment://recent",
}


@pytest.fixture
def mcp():
    """A real FastMCP server with the resources registered."""
    server = FastMCP(name="test")
    register_resources(server)
    return server


async def _read(mcp: FastMCP, uri: str) -> str:
    """Read a resource through FastMCP and return its text."""
    contents = list(await mcp.read_resource(uri))
    assert len(contents) == 1
    assert contents[0].mime_type == "text/plain"
    return contents[0].content


class TestResources:
    """Test suite for MCP resources."""

    @pytest.mark.asyncio
    async def test_register_resources(self, mcp):
        """Every resource is listed, with a name and a description."""
        resources = {str(r.uri): r for r in await mcp.list_resources()}
        assert set(resources) == EXPECTED_URIS
        for resource in resources.values():
            assert resource.name
            assert resource.description

    @pytest.mark.asyncio
    async def test_dashboard_summary(self, mcp):
        """The dashboard reads the organization and dashboard endpoints."""
        api = AsyncMock(
            side_effect=[
                {"organizations": [{"name": "Test Org", "currency_code": "EUR"}]},
                {
                    "dashboard": {
                        "total_revenue": 3000,
                        "total_receivables": 1500.5,
                        "overdue_invoices_count": 5,
                    }
                },
            ]
        )
        with patch("zoho_mcp.resources.zoho_api_request_async", api):
            text = await _read(mcp, "dashboard://summary")

        assert [c.args for c in api.call_args_list] == [
            ("GET", "/organizations"),
            ("GET", "/dashboard"),
        ]
        assert "**Organization**: Test Org" in text
        assert "**Currency**: EUR" in text
        assert "Total Income: 3,000.00" in text
        assert "Total Receivables: 1,500.50" in text
        assert "Number of Overdue Invoices: 5" in text

    @pytest.mark.asyncio
    async def test_overdue_invoices(self, mcp):
        """The overdue list asks for overdue invoices, oldest due date first."""
        list_invoices = AsyncMock(
            return_value={
                "invoices": [
                    {
                        "invoice_number": "INV-001",
                        "customer_name": "Test Customer",
                        "balance": 500.00,
                        "due_date": "2023-01-01",
                        "overdue_days": 12,
                    },
                    {"invoice_number": "INV-002", "customer_name": "Other", "balance": 250},
                ]
            }
        )
        with patch("zoho_mcp.resources.list_invoices", list_invoices):
            text = await _read(mcp, "invoice://overdue")

        list_invoices.assert_awaited_once_with(
            status="overdue", sort_column="due_date", sort_order="ascending", page_size=50
        )
        assert "**Total Count**: 2" in text
        assert "**Total Overdue Amount**: 750.00" in text
        assert "INV-001" in text
        assert "Test Customer" in text
        assert "**Days Overdue**: 12" in text

    @pytest.mark.asyncio
    async def test_overdue_invoices_empty(self, mcp):
        """With no overdue invoices the resource says so."""
        with patch(
            "zoho_mcp.resources.list_invoices", AsyncMock(return_value={"invoices": []})
        ):
            text = await _read(mcp, "invoice://overdue")

        assert "No overdue invoices found" in text

    @pytest.mark.asyncio
    async def test_unpaid_invoices(self, mcp):
        """The unpaid list totals the balances and counts the overdue ones."""
        list_invoices = AsyncMock(
            return_value={
                "invoices": [
                    {"invoice_number": "INV-001", "balance": 100, "status": "overdue"},
                    {"invoice_number": "INV-002", "balance": 50.25, "status": "sent"},
                ]
            }
        )
        with patch("zoho_mcp.resources.list_invoices", list_invoices):
            text = await _read(mcp, "invoice://unpaid")

        list_invoices.assert_awaited_once_with(
            status="unpaid", sort_column="date", sort_order="descending", page_size=50
        )
        assert "**Total Unpaid Amount**: 150.25" in text
        assert "**Overdue Invoices**: 1" in text
        assert "🔴 Invoice #INV-001" in text
        assert "🟡 Invoice #INV-002" in text

    @pytest.mark.asyncio
    async def test_recent_payments(self, mcp):
        """Recent payments covers the last 30 days and lists each payment."""
        api = AsyncMock(
            return_value={
                "customerpayments": [
                    {
                        "payment_number": "PMT-1",
                        "customer_name": "Test Customer",
                        "amount": 1200,
                        "invoices": [{"invoice_number": "INV-001"}, {"invoice_number": "INV-002"}],
                    }
                ]
            }
        )
        with patch("zoho_mcp.resources.zoho_api_request_async", api):
            text = await _read(mcp, "payment://recent")

        args, kwargs = api.call_args
        assert args == ("GET", "/customerpayments")
        assert set(kwargs["params"]) == {"date_start", "date_end", "sort_column", "sort_order"}
        assert "**Total Received**: 1,200.00" in text
        assert "PMT-1" in text
        assert "**Invoice(s)**: INV-001, INV-002" in text

    @pytest.mark.asyncio
    async def test_resource_error_propagates(self, mcp):
        """An API failure surfaces as an error, not as an empty resource."""
        api = AsyncMock(side_effect=RuntimeError("Zoho is down"))
        with patch("zoho_mcp.resources.zoho_api_request_async", api):
            with pytest.raises(Exception, match="Zoho is down"):
                await mcp.read_resource("payment://recent")
