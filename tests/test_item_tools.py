"""
Unit tests for item management tools.

Tests for listing, creating, retrieving, and updating items in Zoho Books.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from zoho_mcp.tools.items import list_items, create_item, get_item, update_item
from zoho_mcp.tools.api import ZohoRequestError

# The tools are coroutines (they await zoho_api_request_async), so every
# test here runs on an event loop.
pytestmark = pytest.mark.asyncio


# Sample item data for testing
SAMPLE_ITEM = {
    "item_id": "123456789",
    "name": "Test Item",
    "description": "Test item description",
    "item_type": "service",
    "rate": 100.0,
    "status": "active",
    "sku": "TST-001",
    "tax_id": "1234",
}

SAMPLE_ITEM_LIST = {
    "items": [SAMPLE_ITEM],
    "page_context": {
        "page": 1,
        "per_page": 25,
        "has_more_page": False,
        "total": 1
    }
}

SAMPLE_ITEM_RESPONSE = {
    "item": SAMPLE_ITEM,
    "code": 0,
    "message": "Success"
}


class TestListItems:
    """Tests for list_items function."""
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_list_items_default(self, mock_api):
        """Test listing items with default parameters."""
        # Setup mock response
        mock_api.return_value = SAMPLE_ITEM_LIST
        
        # Call the function
        result = await list_items()
        
        # Verify API call
        mock_api.assert_called_once()
        args, kwargs = mock_api.call_args
        assert args[0] == "GET"
        assert args[1] == "/items"
        assert kwargs["params"]["page"] == 1
        assert kwargs["params"]["per_page"] == 25
        
        # Verify result
        assert result["items"] == [SAMPLE_ITEM]
        assert result["page"] == 1
        assert result["page_size"] == 25
        assert result["has_more_page"] is False
        assert result["total"] == 1
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_list_items_with_filters(self, mock_api):
        """Test listing items with filters."""
        # Setup mock response
        mock_api.return_value = SAMPLE_ITEM_LIST
        
        # Call the function with parameters
        result = await list_items(
            page=2,
            page_size=10,
            item_type="service",
            search_text="test",
            status="active",
            sort_column="name",
            sort_order="descending"
        )
        
        # Verify API call
        mock_api.assert_called_once()
        args, kwargs = mock_api.call_args
        assert args[0] == "GET"
        assert args[1] == "/items"
        assert kwargs["params"]["page"] == 2
        assert kwargs["params"]["per_page"] == 10
        assert kwargs["params"]["filter_by"] == "ItemType.service"
        assert kwargs["params"]["search_text"] == "test"
        assert kwargs["params"]["status"] == "active"
        assert kwargs["params"]["sort_column"] == "name"
        assert kwargs["params"]["sort_order"] == "descending"
        
        # Verify result
        assert result["items"] == [SAMPLE_ITEM]
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_list_items_error(self, mock_api):
        """Test error handling when listing items."""
        # Setup mock to raise an exception
        mock_api.side_effect = ZohoRequestError(400, "Invalid request")
        
        # Call the function and expect an exception
        with pytest.raises(ZohoRequestError):
            await list_items()


class TestCreateItem:
    """Tests for create_item function."""
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_create_item_minimal(self, mock_api):
        """Test creating an item with minimal required parameters."""
        # Setup mock response
        mock_api.return_value = SAMPLE_ITEM_RESPONSE
        
        # Call the function with minimal parameters
        result = await create_item(
            name="Test Item",
            rate=100.0
        )
        
        # Verify API call
        mock_api.assert_called_once()
        args, kwargs = mock_api.call_args
        assert args[0] == "POST"
        assert args[1] == "/items"
        assert kwargs["json_data"]["name"] == "Test Item"
        assert kwargs["json_data"]["rate"] == 100.0
        assert kwargs["json_data"]["item_type"] == "service"  # Default value
        
        # Verify result
        assert result["item"] == SAMPLE_ITEM
        assert "message" in result
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_create_item_complete(self, mock_api):
        """Test creating an item with all parameters."""
        # Setup mock response
        mock_api.return_value = SAMPLE_ITEM_RESPONSE
        
        # Call the function with all parameters
        result = await create_item(
            name="Test Item",
            rate=100.0,
            description="Test item description",
            item_type="inventory",
            sku="TST-001",
            unit="pcs",
            initial_stock=10,
            initial_stock_rate=50.0,
            purchase_account_id="acc123",
            inventory_account_id="inv123",
            sales_account_id="sales123",
            purchase_description="Test purchase description",
            tax_id="1234",
            custom_fields={"custom1": "value1"}
        )
        
        # Verify API call
        mock_api.assert_called_once()
        args, kwargs = mock_api.call_args
        assert args[0] == "POST"
        assert args[1] == "/items"
        assert kwargs["json_data"]["name"] == "Test Item"
        assert kwargs["json_data"]["rate"] == 100.0
        assert kwargs["json_data"]["description"] == "Test item description"
        assert kwargs["json_data"]["item_type"] == "inventory"
        assert kwargs["json_data"]["sku"] == "TST-001"
        assert kwargs["json_data"]["unit"] == "pcs"
        assert kwargs["json_data"]["initial_stock"] == 10
        assert kwargs["json_data"]["initial_stock_rate"] == 50.0
        assert kwargs["json_data"]["purchase_account_id"] == "acc123"
        assert kwargs["json_data"]["inventory_account_id"] == "inv123"
        assert kwargs["json_data"]["sales_account_id"] == "sales123"
        assert kwargs["json_data"]["purchase_description"] == "Test purchase description"
        assert kwargs["json_data"]["tax_id"] == "1234"
        assert kwargs["json_data"]["custom_fields"] == {"custom1": "value1"}
        
        # Verify result
        assert result["item"] == SAMPLE_ITEM
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_create_item_validation_error(self, mock_api):
        """Test validation error when creating an item."""
        # Call the function with invalid data (inventory item without required fields)
        with pytest.raises(ValueError):
            await create_item(
                name="Test Item",
                rate=100.0,
                item_type="inventory"  # Missing required fields for inventory
            )
        
        # Verify API was not called
        mock_api.assert_not_called()
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_create_item_api_error(self, mock_api):
        """Test API error when creating an item."""
        # Setup mock to raise an exception
        mock_api.side_effect = ZohoRequestError(400, "Invalid request")
        
        # Call the function and expect an exception
        with pytest.raises(ZohoRequestError):
            await create_item(
                name="Test Item",
                rate=100.0
            )


class TestGetItem:
    """Tests for get_item function."""
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_get_item_success(self, mock_api):
        """Test getting an item by ID."""
        # Setup mock response
        mock_api.return_value = SAMPLE_ITEM_RESPONSE
        
        # Call the function
        result = await get_item(item_id="123456789")
        
        # Verify API call
        mock_api.assert_called_once()
        args, kwargs = mock_api.call_args
        assert args[0] == "GET"
        assert args[1] == "/items/123456789"
        
        # Verify result
        assert result["item"] == SAMPLE_ITEM
        assert "message" in result
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_get_item_not_found(self, mock_api):
        """Test getting a non-existent item."""
        # Setup mock response for item not found
        mock_api.return_value = {"item": None, "message": "Item not found"}
        
        # Call the function
        result = await get_item(item_id="nonexistent")
        
        # Verify API call
        mock_api.assert_called_once()
        
        # Verify result
        assert result["item"] is None
        assert result["message"] == "Item not found"
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_get_item_invalid_id(self, mock_api):
        """Test getting an item with an invalid ID."""
        # Call the function with an empty ID
        with pytest.raises(ValueError):
            await get_item(item_id="")
        
        # Verify API was not called
        mock_api.assert_not_called()
    
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_get_item_api_error(self, mock_api):
        """Test API error when getting an item."""
        # Setup mock to raise an exception
        mock_api.side_effect = ZohoRequestError(404, "Item not found")
        
        # Call the function and expect an exception
        with pytest.raises(ZohoRequestError):
            await get_item(item_id="123456789")


class TestUpdateItem:
    """Tests for update_item function."""
    
    @patch("zoho_mcp.tools.items.get_item")
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_update_item_partial(self, mock_api, mock_get_item):
        """Test updating an item with partial data."""
        # Setup mock response for get_item
        mock_get_item.return_value = {
            "item": SAMPLE_ITEM,
            "message": "Success"
        }
        
        # Setup mock response for the update
        mock_api.return_value = SAMPLE_ITEM_RESPONSE
        
        # Call the function with partial updates
        result = await update_item(
            item_id="123456789",
            description="Updated description",
            rate=150.0
        )
        
        # Verify get_item was called
        mock_get_item.assert_called_once_with("123456789")
        
        # Verify API call
        mock_api.assert_called_once()
        args, kwargs = mock_api.call_args
        assert args[0] == "PUT"
        assert args[1] == "/items/123456789"
        assert kwargs["json_data"]["name"] == SAMPLE_ITEM["name"]  # Preserved from original
        assert kwargs["json_data"]["rate"] == 150.0  # Updated
        assert kwargs["json_data"]["description"] == "Updated description"  # Updated
        
        # Verify result
        assert result["item"] == SAMPLE_ITEM
        assert "message" in result
    
    @patch("zoho_mcp.tools.items.get_item")
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_update_item_not_found(self, mock_api, mock_get_item):
        """Test updating a non-existent item."""
        # Setup mock response for get_item
        mock_get_item.return_value = {
            "item": None,
            "message": "Item not found"
        }
        
        # Call the function and expect an exception
        with pytest.raises(ValueError):
            await update_item(
                item_id="nonexistent",
                name="New Name"
            )
        
        # Verify get_item was called but API update was not
        mock_get_item.assert_called_once()
        mock_api.assert_not_called()
    
    @patch("zoho_mcp.tools.items.get_item")
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_update_item_all_fields(self, mock_api, mock_get_item):
        """Test updating all fields of an item."""
        # Setup mock response for get_item
        mock_get_item.return_value = {
            "item": SAMPLE_ITEM,
            "message": "Success"
        }
        
        # Setup mock response for the update
        mock_api.return_value = SAMPLE_ITEM_RESPONSE
        
        # Call the function with all updatable fields
        result = await update_item(
            item_id="123456789",
            name="New Name",
            rate=200.0,
            description="New description",
            sku="NEW-001",
            unit="units",
            tax_id="5678",
            tax_name=None,
            tax_percentage=None,
            purchase_account_id="new_acc",
            inventory_account_id="new_inv",
            sales_account_id="new_sales",
            purchase_description="New purchase description",
            custom_fields={"new_custom": "new_value"}
        )
        
        # Verify API call
        mock_api.assert_called_once()
        args, kwargs = mock_api.call_args
        assert kwargs["json_data"]["name"] == "New Name"
        assert kwargs["json_data"]["rate"] == 200.0
        assert kwargs["json_data"]["description"] == "New description"
        assert kwargs["json_data"]["sku"] == "NEW-001"
        assert kwargs["json_data"]["unit"] == "units"
        assert kwargs["json_data"]["tax_id"] == "5678"
        assert kwargs["json_data"]["purchase_account_id"] == "new_acc"
        assert kwargs["json_data"]["inventory_account_id"] == "new_inv"
        assert kwargs["json_data"]["sales_account_id"] == "new_sales"
        assert kwargs["json_data"]["purchase_description"] == "New purchase description"
        assert kwargs["json_data"]["custom_fields"] == {"new_custom": "new_value"}
        
        # Verify result
        assert result["item"] == SAMPLE_ITEM
    
    @patch("zoho_mcp.tools.items.get_item")
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_update_item_validation_error(self, mock_api, mock_get_item):
        """Test validation error when updating an item."""
        # Setup mock response for get_item
        mock_get_item.return_value = {
            "item": SAMPLE_ITEM,
            "message": "Success"
        }
        
        # Call the function with invalid data
        with pytest.raises(ValueError):
            await update_item(
                item_id="123456789",
                rate="invalid"  # Type error: should be a number
            )
        
        # Verify get_item was called but API update was not
        mock_get_item.assert_called_once()
        mock_api.assert_not_called()
    
    @patch("zoho_mcp.tools.items.get_item")
    @patch("zoho_mcp.tools.items.zoho_api_request_async", new_callable=AsyncMock)
    async def test_update_item_api_error(self, mock_api, mock_get_item):
        """Test API error when updating an item."""
        # Setup mock response for get_item
        mock_get_item.return_value = {
            "item": SAMPLE_ITEM,
            "message": "Success"
        }
        
        # Setup mock API to raise an exception
        mock_api.side_effect = ZohoRequestError(400, "Invalid request")
        
        # Call the function and expect an exception
        with pytest.raises(ZohoRequestError):
            await update_item(
                item_id="123456789",
                name="New Name"
            )