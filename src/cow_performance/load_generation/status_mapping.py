"""
Status mapping utilities for CoW Protocol order states.

Maps between CoW API status strings and internal OrderStatus enum values.
"""

from cow_performance.metrics import OrderStatus

# CoW API status values (from OpenAPI spec)
# https://api.cow.fi/docs/#/default/get_api_v1_orders__UID_
COW_API_STATUS_MAPPING: dict[str, OrderStatus] = {
    "presignaturePending": OrderStatus.SUBMITTED,
    "open": OrderStatus.OPEN,
    "fulfilled": OrderStatus.FILLED,
    "cancelled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
}


def map_api_status_to_order_status(api_status: str) -> OrderStatus:
    """
    Map CoW API status string to OrderStatus enum.

    Args:
        api_status: Status string from CoW API response

    Returns:
        Corresponding OrderStatus enum value

    Raises:
        ValueError: If the API status is unknown
    """
    status = COW_API_STATUS_MAPPING.get(api_status)
    if status is None:
        raise ValueError(f"Unknown API status: {api_status}")
    return status


def is_api_status_terminal(api_status: str) -> bool:
    """
    Check if an API status represents a terminal state.

    Args:
        api_status: Status string from CoW API response

    Returns:
        True if the status is terminal (no more updates expected)
    """
    terminal_statuses = {"fulfilled", "cancelled", "expired"}
    return api_status in terminal_statuses
