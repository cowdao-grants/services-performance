"""Chain Reconciliation Utility

This module provides utilities to reconcile database state with on-chain state
by querying the blockchain directly for settlement events. This is necessary
in Anvil fork mode where event synchronization is broken due to lack of
debug_traceTransaction support.

The reconciliation process:
1. Queries the chain for Trade events in the test block range
2. Extracts order UIDs from event data
3. Compares with orders in the database
4. Outputs accurate fill rate and discrepancy report
5. Optionally updates database with on-chain trade data
"""

import logging
import os
from dataclasses import dataclass

import psycopg2  # type: ignore
from web3 import Web3
from web3.types import LogReceipt

logger = logging.getLogger(__name__)


@dataclass
class TradeEvent:
    """Represents a Trade event from the settlement contract."""

    transaction_hash: str
    block_number: int
    log_index: int
    order_uid: str
    owner: str
    sell_token: str
    buy_token: str
    sell_amount: int
    buy_amount: int
    fee_amount: int


@dataclass
class ReconciliationReport:
    """Report comparing database state with on-chain state."""

    total_orders: int
    database_filled: int
    chain_filled: int
    database_fill_rate: float
    chain_fill_rate: float
    discrepancy_percentage_points: float
    filled_order_uids: set[str]
    unfilled_order_uids: set[str]
    trade_events: list[TradeEvent]


class ChainReconciliator:
    """Reconciles database order state with on-chain settlement events."""

    # Trade event signature: Trade(address indexed owner, address sellToken, address buyToken, uint256 sellAmount, uint256 buyAmount, uint256 feeAmount, bytes orderUid)
    TRADE_EVENT_SIGNATURE = "0xa07a543ab8a018198e99ca0184c93fe9050a79400a0a723441f84de1d972cc17"

    def __init__(
        self,
        rpc_url: str,
        settlement_contract: str = "0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        db_url: str | None = None,
    ):
        """Initialize the reconciliator.

        Args:
            rpc_url: RPC endpoint URL for the blockchain
            settlement_contract: Address of the CoW Protocol settlement contract
            db_url: PostgreSQL connection URL (default: from environment variables)
        """
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.settlement_contract = Web3.to_checksum_address(settlement_contract)
        self.db_url = db_url or self._build_db_url_from_env()

    def _build_db_url_from_env(self) -> str:
        """Build PostgreSQL connection URL from environment variables."""
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "password")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    def _parse_trade_event(self, log: LogReceipt) -> TradeEvent:
        """Parse a Trade event from a log receipt.

        Args:
            log: Web3 log receipt containing the Trade event

        Returns:
            Parsed TradeEvent object
        """
        # Topics: [event_signature, indexed_owner]
        owner = Web3.to_checksum_address("0x" + log["topics"][1].hex()[26:])

        # Data contains: sellToken, buyToken, sellAmount, buyAmount, feeAmount, orderUid
        data = log["data"].hex()[2:]  # Remove 0x prefix

        # Parse data (each field is 32 bytes = 64 hex chars)
        sell_token = Web3.to_checksum_address("0x" + data[24:64])
        buy_token = Web3.to_checksum_address("0x" + data[88:128])
        sell_amount = int(data[128:192], 16)
        buy_amount = int(data[192:256], 16)
        fee_amount = int(data[256:320], 16)

        # OrderUid is variable length bytes, prefixed with offset and length
        # Skip offset (320:384) and length (384:448), then read the actual UID
        order_uid_hex = data[448:]  # Everything after length
        # OrderUID is 56 bytes = 112 hex chars
        order_uid = "0x" + order_uid_hex[:112]

        return TradeEvent(
            transaction_hash=log["transactionHash"].hex(),
            block_number=log["blockNumber"],
            log_index=log["logIndex"],
            order_uid=order_uid,
            owner=owner,
            sell_token=sell_token,
            buy_token=buy_token,
            sell_amount=sell_amount,
            buy_amount=buy_amount,
            fee_amount=fee_amount,
        )

    def get_trade_events(self, from_block: int, to_block: int) -> list[TradeEvent]:
        """Query the chain for Trade events in the given block range.

        Args:
            from_block: Starting block number
            to_block: Ending block number

        Returns:
            List of parsed Trade events
        """
        # Query logs for Trade events
        logs = self.web3.eth.get_logs(
            {
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": self.settlement_contract,
                "topics": [self.TRADE_EVENT_SIGNATURE],  # type: ignore
            }
        )

        # Parse each log into a TradeEvent
        trade_events = []
        for log in logs:
            try:
                event = self._parse_trade_event(log)
                trade_events.append(event)
            except Exception as e:
                print(
                    f"Warning: Failed to parse Trade event in tx {log['transactionHash'].hex()}: {e}"
                )
                continue

        return trade_events

    def reconcile(
        self,
        from_block: int,
        to_block: int,
        submitted_order_uids: set[str],
        database_filled_count: int = 0,
    ) -> ReconciliationReport:
        """Reconcile database state with on-chain state.

        Args:
            from_block: Starting block of test period
            to_block: Ending block of test period
            submitted_order_uids: Set of order UIDs submitted during test
            database_filled_count: Number of filled orders reported by database

        Returns:
            ReconciliationReport with comparison data
        """
        # Get Trade events from chain
        trade_events = self.get_trade_events(from_block, to_block)

        # Extract filled order UIDs from events
        filled_order_uids = {event.order_uid for event in trade_events}

        # Filter to only orders from this test (in case there were other orders)
        filled_order_uids = filled_order_uids.intersection(submitted_order_uids)

        # Calculate unfilled orders
        unfilled_order_uids = submitted_order_uids - filled_order_uids

        # Calculate fill rates
        total_orders = len(submitted_order_uids)
        chain_filled = len(filled_order_uids)
        chain_fill_rate = (chain_filled / total_orders * 100) if total_orders > 0 else 0.0
        database_fill_rate = (
            (database_filled_count / total_orders * 100) if total_orders > 0 else 0.0
        )
        discrepancy = chain_fill_rate - database_fill_rate

        return ReconciliationReport(
            total_orders=total_orders,
            database_filled=database_filled_count,
            chain_filled=chain_filled,
            database_fill_rate=database_fill_rate,
            chain_fill_rate=chain_fill_rate,
            discrepancy_percentage_points=discrepancy,
            filled_order_uids=filled_order_uids,
            unfilled_order_uids=unfilled_order_uids,
            trade_events=trade_events,
        )

    def print_report(self, report: ReconciliationReport, verbose: bool = False) -> None:
        """Print a formatted reconciliation report.

        Args:
            report: ReconciliationReport to print
            verbose: If True, print detailed order-by-order breakdown
        """
        print("\n" + "=" * 80)
        print("CHAIN RECONCILIATION REPORT")
        print("=" * 80)
        print("\n📊 Fill Rate Comparison:")
        print(
            f"  Database Reports:  {report.database_filled}/{report.total_orders} filled ({report.database_fill_rate:.1f}%)"
        )
        print(
            f"  On-Chain Reality:  {report.chain_filled}/{report.total_orders} filled ({report.chain_fill_rate:.1f}%)"
        )

        if report.discrepancy_percentage_points != 0:
            symbol = "⚠️" if abs(report.discrepancy_percentage_points) > 10 else "ℹ️"
            print(
                f"\n{symbol} Discrepancy: {report.discrepancy_percentage_points:+.1f} percentage points"
            )

            if report.discrepancy_percentage_points > 0:
                print(
                    f"  → Database is UNDER-reporting fills by {report.discrepancy_percentage_points:.1f}pp"
                )
            else:
                print(
                    f"  → Database is OVER-reporting fills by {abs(report.discrepancy_percentage_points):.1f}pp"
                )
        else:
            print("\n✅ Perfect Sync: Database matches on-chain state")

        print("\n📈 Settlement Summary:")
        print(f"  Total Trade Events: {len(report.trade_events)}")
        print(f"  Filled Orders: {len(report.filled_order_uids)}")
        print(f"  Unfilled Orders: {len(report.unfilled_order_uids)}")

        if verbose and report.trade_events:
            print("\n📝 Trade Event Details:")
            for i, event in enumerate(report.trade_events, 1):
                print(f"\n  Trade #{i}:")
                print(f"    Tx Hash: {event.transaction_hash}")
                print(f"    Block: {event.block_number}")
                print(f"    Order UID: {event.order_uid[:18]}...{event.order_uid[-8:]}")
                print(f"    Sell Amount: {event.sell_amount}")
                print(f"    Buy Amount: {event.buy_amount}")

        if verbose and report.unfilled_order_uids:
            print("\n❌ Unfilled Orders:")
            for uid in report.unfilled_order_uids:
                print(f"    {uid[:18]}...{uid[-8:]}")

        print("\n" + "=" * 80 + "\n")

    def update_database(self, report: ReconciliationReport) -> int:
        """Update database with on-chain trade data.

        Inserts trade records for all filled orders found on-chain.
        This fixes the database state to match blockchain reality.

        Args:
            report: ReconciliationReport with on-chain trade data

        Returns:
            Number of trade records inserted

        Raises:
            psycopg2.Error: If database operation fails
        """
        if not report.trade_events:
            logger.info("No trade events to insert into database")
            return 0

        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()

            inserted_count = 0

            for event in report.trade_events:
                try:
                    # Convert order UID from hex string to bytes
                    order_uid_bytes = bytes.fromhex(event.order_uid[2:])  # Remove 0x prefix

                    # Insert trade record
                    cursor.execute(
                        """
                        INSERT INTO trades (block_number, log_index, order_uid, sell_amount, buy_amount, fee_amount)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (block_number, log_index) DO NOTHING
                        """,
                        (
                            event.block_number,
                            event.log_index,
                            order_uid_bytes,
                            event.sell_amount,
                            event.buy_amount,
                            event.fee_amount,
                        ),
                    )

                    if cursor.rowcount > 0:
                        inserted_count += 1
                        logger.debug(f"Inserted trade for order {event.order_uid[:18]}...")

                except Exception as e:
                    logger.warning(f"Failed to insert trade for order {event.order_uid}: {e}")
                    continue

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Successfully inserted {inserted_count} trade records into database")
            return inserted_count

        except psycopg2.Error as e:
            logger.error(f"Database error during reconciliation update: {e}")
            raise


async def reconcile_test_results(
    from_block: int,
    to_block: int,
    submitted_order_uids: set[str],
    rpc_url: str,
    database_filled_count: int = 0,
    verbose: bool = False,
) -> ReconciliationReport:
    """Convenience function to reconcile test results.

    Args:
        from_block: Starting block of test
        to_block: Ending block of test
        submitted_order_uids: Set of order UIDs from test
        rpc_url: RPC URL for blockchain queries
        database_filled_count: Filled count from database
        verbose: Print detailed report

    Returns:
        ReconciliationReport
    """
    reconciliator = ChainReconciliator(rpc_url=rpc_url)
    report = reconciliator.reconcile(
        from_block=from_block,
        to_block=to_block,
        submitted_order_uids=submitted_order_uids,
        database_filled_count=database_filled_count,
    )

    if verbose:
        reconciliator.print_report(report, verbose=True)

    return report
