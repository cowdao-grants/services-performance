#!/usr/bin/env python3
"""
Reconciliation script for recent test run.

This script demonstrates the chain reconciliation utility by analyzing
the recent test that showed 0% fill rate in database but 75% on-chain.

Usage:
    python scripts/reconcile_recent_test.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cow_performance.utils.chain_reconciliation import ChainReconciliator

# Test parameters from recent run (2026-03-16)
FROM_BLOCK = 24673430
TO_BLOCK = 24673700
RPC_URL = "http://localhost:8545"

# Orders submitted during test (from database query)
SUBMITTED_ORDER_UIDS = {
    "0xf20b7dccb4caee8d6fd582fd68807580b2f1980054cb7de17e4e4f145ceb1e3062500c211ba359bfc4659ae7d9031997f2c999bd69b8a1d3",
    "0xc95c1809aa57d29f40b2297e5219276a7dd7508730a8dbefc49f1f24e7e6f9da9b2fe53fdc7dee25cd8f0d571f77a313f438e97669b8a1d1",
    "0x68142743b06db589aa97118cb56474b70703601b6bb36dbea9ee7b78a748e1f762500c211ba359bfc4659ae7d9031997f2c999bd69b8a1ce",
    "0x24a45ad60f46001140a4cbc9493141a2a19d3409b64bb861d2a150a09659c1b99b2fe53fdc7dee25cd8f0d571f77a313f438e97669b8a1cc",
    "0xa28c239c9ce342ca9018b3c309258081fc505558d1f721a7393d724d356ca5bf62500c211ba359bfc4659ae7d9031997f2c999bd69b8a1c7",
    "0xfe09bbc5896776757a9e693a53d354f75d0beca75d9fbf21437b87390ff2133d9b2fe53fdc7dee25cd8f0d571f77a313f438e97669b8a1c6",
    "0x3a1730f0c4989a834b98ff208b722cb75e8cbb5e2b8000b35d20f07c881556139b2fe53fdc7dee25cd8f0d571f77a313f438e97669b8a1bf",
    "0x06c7b3b2f965ce692dc6efdb4dbe39cc714a86970cfd0d8c77cdb5d3fc0f136762500c211ba359bfc4659ae7d9031997f2c999bd69b8a1bf",
}

# Database reported 0 filled
DATABASE_FILLED = 0


def main():
    """Run reconciliation for recent test."""
    print("🔍 Reconciling Recent Test Run...")
    print(f"Block Range: {FROM_BLOCK} → {TO_BLOCK}")
    print(f"Orders Submitted: {len(SUBMITTED_ORDER_UIDS)}")
    print(f"Database Reported: {DATABASE_FILLED} filled\n")

    # Create reconciliator
    reconciliator = ChainReconciliator(rpc_url=RPC_URL)

    # Run reconciliation
    report = reconciliator.reconcile(
        from_block=FROM_BLOCK,
        to_block=TO_BLOCK,
        submitted_order_uids=SUBMITTED_ORDER_UIDS,
        database_filled_count=DATABASE_FILLED,
    )

    # Print report
    reconciliator.print_report(report, verbose=True)

    # Validation
    print("✅ Validation:")
    expected_fill_rate = 75.0  # 6 out of 8
    if abs(report.chain_fill_rate - expected_fill_rate) < 0.1:
        print(
            f"  ✓ Fill rate matches expected {expected_fill_rate}% (actual: {report.chain_fill_rate}%)"
        )
    else:
        print(
            f"  ✗ Fill rate mismatch: expected {expected_fill_rate}%, got {report.chain_fill_rate}%"
        )

    if report.chain_filled == 6:
        print(f"  ✓ Found expected 6 filled orders")
    else:
        print(f"  ✗ Expected 6 filled orders, found {report.chain_filled}")

    if report.discrepancy_percentage_points == 75.0:
        print(f"  ✓ Discrepancy is 75pp as expected (0% → 75%)")
    else:
        print(f"  ✗ Expected 75pp discrepancy, got {report.discrepancy_percentage_points}pp")

    print("\n💡 Key Insight:")
    print("  The database shows 0% fill rate, but the chain proves 75% of orders were filled.")
    print("  This demonstrates the event sync issue in Anvil fork mode and the need for")
    print("  chain-based reconciliation to get accurate metrics.\n")

    return 0 if report.chain_filled == 6 else 1


if __name__ == "__main__":
    sys.exit(main())
