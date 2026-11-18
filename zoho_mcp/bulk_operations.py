"""
Bulk operation utilities for Zoho Books MCP Integration.

This module provides utilities for performing bulk operations with progress tracking.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from zoho_mcp.progress import BulkOperationProgress
from zoho_mcp.tools.invoices import create_invoice
from zoho_mcp.tools.expenses import create_expense

logger = logging.getLogger(__name__)


async def bulk_create_invoices(
    invoices_data: List[Dict[str, Any]],
    callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]:
    """
    Create multiple invoices with progress tracking.
    
    Args:
        invoices_data: List of invoice data dictionaries
        callback: Optional callback(current, total), called after each invoice.
            Each invoice is an API round trip, so a per-invoice update costs little;
            the tracker's default of every 10 would leave a run of fewer than
            10 invoices silent until it ends.
        
    Returns:
        Dictionary with results including successful and failed invoices
    """
    total = len(invoices_data)
    logger.info(f"Starting bulk invoice creation: {total} invoices")
    
    successful = []
    failed = []
    
    async with BulkOperationProgress(
        total,
        "Bulk invoice creation",
        notify_interval=1,
        callback=callback
    ) as progress:
        for idx, invoice_data in enumerate(invoices_data):
            try:
                # Add a reference to track this invoice. Work on a copy:
                # create_invoice gets this dict itself, and writing the
                # reference into the caller's dict would make a retry of the
                # same list reuse an old BULK-<date> reference.
                invoice_data = dict(invoice_data)
                if "reference_number" not in invoice_data:
                    date_str = datetime.now().strftime('%Y%m%d')
                    invoice_data["reference_number"] = f"BULK-{date_str}-{idx + 1}"
                
                # Create the invoice. create_invoice takes the invoice fields
                # as one dict (kwargs=...), not as keyword arguments, because
                # MCP clients may send them as a JSON object; spreading them
                # with ** fails every invoice with a TypeError.
                result = await create_invoice(kwargs=invoice_data)
                
                # The response model allows invoice to be None. The invoice
                # exists in Zoho by now, so it must count as created, never
                # fall into the except branch below, where a retry would
                # create it twice.
                invoice = result.get("invoice") or {}
                successful.append({
                    "index": idx,
                    "invoice_id": invoice.get("invoice_id"),
                    "invoice_number": invoice.get("invoice_number"),
                    "customer_name": invoice.get("customer_name"),
                    "total": invoice.get("total"),
                })
                
            except Exception as e:
                logger.error(f"Failed to create invoice {idx + 1}: {str(e)}")
                failed.append({
                    "index": idx,
                    "customer_id": invoice_data.get("customer_id"),
                    "error": str(e),
                })
            
            # Update progress
            await progress.async_increment()
    
    # Calculate summary
    # "total" is None when Zoho leaves it out; count that as 0 rather than
    # raise after every invoice has been created.
    total_amount = sum(inv["total"] or 0 for inv in successful)
    
    return {
        "summary": {
            "total_requested": total,
            "successful": len(successful),
            "failed": len(failed),
            "total_amount": total_amount,
            "average_amount": total_amount / len(successful) if successful else 0,
        },
        "successful_invoices": successful,
        "failed_invoices": failed,
    }


async def bulk_record_expenses(
    expenses_data: List[Dict[str, Any]],
    callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]:
    """
    Record multiple expenses with progress tracking.
    
    Args:
        expenses_data: List of expense data dictionaries
        callback: Optional callback(current, total), called after each expense.
            Each expense is an API round trip, so a per-expense update costs little;
            the tracker's default of every 10 would leave a run of fewer than
            10 expenses silent until it ends.
        
    Returns:
        Dictionary with results including successful and failed expenses
    """
    total = len(expenses_data)
    logger.info(f"Starting bulk expense recording: {total} expenses")
    
    successful = []
    failed = []
    
    async with BulkOperationProgress(
        total,
        "Bulk expense recording",
        notify_interval=1,
        callback=callback
    ) as progress:
        for idx, expense_data in enumerate(expenses_data):
            try:
                # Create the expense
                result = await create_expense(**expense_data)
                
                # As for invoices: the expense exists now, even if the
                # response has no expense body.
                expense = result.get("expense") or {}
                successful.append({
                    "index": idx,
                    "expense_id": expense.get("expense_id"),
                    "date": expense.get("date"),
                    "account_name": expense.get("account_name"),
                    "total": expense.get("total"),
                })
                
            except Exception as e:
                logger.error(f"Failed to record expense {idx + 1}: {str(e)}")
                failed.append({
                    "index": idx,
                    "date": expense_data.get("date"),
                    "error": str(e),
                })
            
            # Update progress
            await progress.async_increment()
    
    # Calculate summary
    total_amount = sum(exp["total"] or 0 for exp in successful)
    
    return {
        "summary": {
            "total_requested": total,
            "successful": len(successful),
            "failed": len(failed),
            "total_amount": total_amount,
            "average_amount": total_amount / len(successful) if successful else 0,
        },
        "successful_expenses": successful,
        "failed_expenses": failed,
    }


async def batch_process_with_progress(
    items: List[Any],
    process_func: Callable,
    operation_name: str,
    batch_size: int = 10,
    callback: Optional[Callable[[int, int], None]] = None
) -> List[Any]:
    """
    Process items in batches with progress tracking.
    
    This is useful for operations that benefit from batching,
    such as API calls that support bulk operations.
    
    Args:
        items: List of items to process
        process_func: Async function to process each batch
        operation_name: Name of the operation for logging
        batch_size: Number of items to process per batch
        callback: Optional callback(current, total), called after each batch.
            Each batch is an API round trip, so a per-batch update costs little;
            the tracker's default of every 10 would leave a run of fewer than
            10 batches silent until it ends.
        
    Returns:
        List of results from processing all batches
    """
    total_batches = (len(items) + batch_size - 1) // batch_size
    results = []
    
    async with BulkOperationProgress(
        total_batches,
        f"{operation_name} (batched)",
        notify_interval=1,
        callback=callback
    ) as progress:
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            try:
                # Process the batch
                batch_result = await process_func(batch)
                results.append(batch_result)
                
            except Exception as e:
                logger.error(f"Error processing batch {i // batch_size + 1}: {str(e)}")
                results.append({"error": str(e), "batch_index": i // batch_size})
            
            # Update progress
            await progress.async_increment()
    
    return results
