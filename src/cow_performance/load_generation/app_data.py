"""
AppData generation and hashing utilities for CoW Protocol orders.

This module provides utilities for creating appData documents with proper metadata
including orderClass classification (market vs limit orders).
"""

import json

from web3 import Web3

from .order_schema import OrderClass


def create_app_data_doc(
    order_class: OrderClass,
    app_code: str = "CoW Performance Testing Suite",
    version: str = "0.9.0",
) -> dict:
    """
    Create an appData document with orderClass metadata.

    Args:
        order_class: The order classification (market or limit)
        app_code: Application identifier (default: "CoW Performance Testing Suite")
        version: AppData schema version (default: "0.9.0")

    Returns:
        AppData document as a dictionary
    """
    return {
        "version": version,
        "appCode": app_code,
        "metadata": {
            "orderClass": {
                "orderClass": order_class.value,
            }
        },
    }


def compute_app_data_hash(app_data_doc: dict) -> str:
    """
    Compute the keccak256 hash of an appData document.

    Uses consistent JSON serialization to ensure hash stability.

    Args:
        app_data_doc: The appData document to hash

    Returns:
        Hex-encoded hash with 0x prefix (32 bytes)
    """
    # Use consistent JSON serialization (no spaces, sorted keys)
    app_data_json = json.dumps(app_data_doc, separators=(",", ":"), sort_keys=True)

    # Compute keccak256 hash (.hex() already includes 0x prefix)
    computed_hash = Web3.keccak(text=app_data_json).hex()

    return computed_hash


def create_app_data(order_class: OrderClass) -> tuple[str, dict]:
    """
    Create an appData document and compute its hash.

    Convenience function that combines document creation and hashing.

    Args:
        order_class: The order classification (market or limit)

    Returns:
        Tuple of (hash, document) where hash is the keccak256 hash
        and document is the full appData JSON object
    """
    doc = create_app_data_doc(order_class)
    hash_value = compute_app_data_hash(doc)
    return hash_value, doc
