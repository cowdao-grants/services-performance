"""Run command implementation for performance testing."""

import asyncio
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from web3 import Web3

from cow_performance.api import InstrumentedOrderbookClient, OrderbookClient
from cow_performance.baselines import BaselineManager
from cow_performance.cli.live_display import create_performance_metrics_dict
from cow_performance.load_generation import (
    ConditionalOrderFactory,
    OrchestrationConfig,
    OrderFactory,
    OrderSigner,
    OrderTracker,
    RateLimitConfig,
    TraderBehaviorConfig,
    TraderOrchestrator,
    TradingPattern,
    create_mainnet_token_registry,
)
from cow_performance.load_generation.order_signer import ConditionalOrderSigner
from cow_performance.metrics import ExpirationChecker, MetricsStore
from cow_performance.monitoring import ResourceMonitor, ResourceMonitorConfig
from cow_performance.prometheus import PrometheusExporter
from cow_performance.utils.chain_reconciliation import ChainReconciliator

from ..config import PerformanceTestConfig
from ..output import (
    create_result_filename,
    format_metrics_json,
    format_metrics_table,
    save_metrics_to_file,
)
from ..wallet_funding import create_trader_pool_from_config, fund_trader_pool


def _register_shutdown_handlers(orchestrator: TraderOrchestrator) -> None:
    """Register asyncio-native signal handlers for SIGINT and SIGTERM.

    Cancels all running trader tasks immediately so that any sleeping or
    awaiting coroutines are interrupted at the next yield point.

    Args:
        orchestrator: The TraderOrchestrator whose tasks will be cancelled
    """
    loop = asyncio.get_event_loop()
    shutdown_called = False

    def _handle_shutdown() -> None:
        nonlocal shutdown_called
        if shutdown_called:
            return
        shutdown_called = True
        print("\n\nShutdown requested, stopping traders...")
        orchestrator._running = False
        for task in orchestrator.tasks:
            if not task.done():
                task.cancel()

    loop.add_signal_handler(signal.SIGINT, _handle_shutdown)
    loop.add_signal_handler(signal.SIGTERM, _handle_shutdown)


async def update_prometheus_metrics(
    exporter: PrometheusExporter,
    orchestrator: TraderOrchestrator,
    test_duration: float,
    target_rate: float,
) -> None:
    """Periodically update Prometheus progress and throughput metrics.

    Args:
        exporter: The Prometheus exporter to update
        orchestrator: The trader orchestrator (to check running state and get order counts)
        test_duration: Total test duration in seconds
        target_rate: Target orders per second
    """
    start_time = time.time()

    while orchestrator._running:
        elapsed = time.time() - start_time

        # Update progress (0-100%)
        progress_percent = min(100.0, (elapsed / test_duration) * 100)
        exporter.update_progress(progress_percent)

        # Calculate actual rate
        total_orders = orchestrator.trader_pool.get_total_orders_submitted()
        actual_rate = total_orders / elapsed if elapsed > 0 else 0.0

        # Update throughput metrics
        exporter.update_throughput(
            orders_per_second=actual_rate,
            target_rate=target_rate,
            actual_rate=actual_rate,
        )

        await asyncio.sleep(1.0)  # Update every second


async def run_performance_test(
    config: PerformanceTestConfig,
    traders: int | None = None,
    duration: int | None = None,
    settlement_wait: int | None = None,
    verbose: bool = False,
    dry_run: bool = False,
    prometheus_port: int | None = None,
) -> dict[str, Any]:
    """Run a performance test with the given configuration.

    Args:
        config: Performance test configuration
        traders: Optional override for number of traders
        duration: Optional override for test duration (seconds)
        settlement_wait: Optional override for settlement wait time (seconds, default 180)
        verbose: Enable verbose output
        dry_run: Perform dry run without submitting orders

    Returns:
        Dictionary with test results and metrics

    Raises:
        ValueError: If configuration is invalid
    """
    console = Console()

    # Use overrides or config defaults
    num_traders = traders if traders is not None else config.default_trader_count
    test_duration = duration if duration is not None else config.default_duration
    settlement_wait_time = (
        settlement_wait if settlement_wait is not None else 180.0
    )  # Default 3 minutes (sufficient for 120s order validity)

    # Connect to Web3 to get block numbers for reconciliation
    web3 = Web3(Web3.HTTPProvider(config.network.rpc_url))
    start_block = 0
    end_block = 0

    if verbose:
        console.print("[bold cyan]Configuration:[/bold cyan]")
        console.print(f"  Traders: {num_traders}")
        console.print(f"  Duration: {test_duration}s")
        console.print(f"  Settlement wait: {settlement_wait_time}s")
        console.print(f"  Chain ID: {config.network.chain_id}")
        console.print(f"  API URL: {config.api.base_url}")
        console.print(f"  Trading pattern: {config.trading_pattern}")
        console.print(f"  Base rate: {config.base_rate} orders/min")

        # Show pattern-specific parameters
        if config.trading_pattern in ("ramp_up", "ramp_down"):
            console.print(
                f"  Ramp: {config.ramp_start_rate} → {config.ramp_target_rate} orders/min over {config.ramp_duration}s ({config.ramp_curve})"
            )
        elif config.trading_pattern == "spike":
            console.print(
                f"  Spike: {config.spike_normal_rate} → {config.spike_burst_rate} orders/min for {config.spike_duration}s"
            )
        elif config.trading_pattern == "poisson":
            console.print(f"  Poisson lambda: {config.poisson_lambda} events/min")

        # Show rate limiting if enabled
        if config.enable_global_rate_limit:
            if config.max_orders_global_per_second:
                limit = config.max_orders_global_per_second
            elif config.max_orders_global_per_minute:
                limit = config.max_orders_global_per_minute / 60.0
            else:
                limit = 0.0
            console.print(f"  Global rate limit: {limit:.1f} orders/sec")
        if config.enable_per_trader_rate_limit:
            if config.max_orders_per_trader_per_second:
                limit = config.max_orders_per_trader_per_second
            elif config.max_orders_per_trader_per_minute:
                limit = config.max_orders_per_trader_per_minute / 60.0
            else:
                limit = 0.0
            console.print(f"  Per-trader rate limit: {limit:.1f} orders/sec")

        console.print()

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No orders will be submitted[/yellow]")
        console.print()

    # Create token registry
    token_registry = create_mainnet_token_registry()

    # Filter token pairs to only use funded tokens if wallet funding is enabled
    if config.wallet.funding_enabled and config.wallet.token_balances:
        funded_tokens = set(config.wallet.token_balances.keys())
        all_pairs = token_registry.get_all_pairs()
        filtered_pairs = [
            pair
            for pair in all_pairs
            if pair.sell_token.symbol in funded_tokens and pair.buy_token.symbol in funded_tokens
        ]

        # Create new registry with filtered pairs
        from cow_performance.load_generation.token_pair import TokenPairRegistry

        token_registry = TokenPairRegistry(token_pairs=filtered_pairs)

        if verbose and len(filtered_pairs) < len(all_pairs):
            console.print("[cyan]Token Pairs:[/cyan]")
            console.print(
                f"  Filtered to {len(filtered_pairs)} pairs using funded tokens: {', '.join(sorted(funded_tokens))}"
            )
            console.print()

    # Create trader pool based on wallet configuration
    trader_pool = create_trader_pool_from_config(config.wallet, num_traders)

    # Fund wallets if enabled (requires Anvil fork mode)
    if config.wallet.funding_enabled:
        if verbose:
            console.print("[bold cyan]Wallet Funding:[/bold cyan]")
            console.print(f"  RPC URL: {config.network.rpc_url}")
            console.print(f"  ETH per wallet: {config.wallet.eth_balance}")
            console.print(f"  Token balances: {config.wallet.token_balances}")

        try:
            # Connect to Web3
            web3 = Web3(Web3.HTTPProvider(config.network.rpc_url))
            if not web3.is_connected():
                raise ValueError(f"Failed to connect to RPC at {config.network.rpc_url}")

            if verbose:
                console.print(
                    f"  [green]✓[/green] Connected to RPC (chain ID: {web3.eth.chain_id})"
                )

            # Fund all traders in the pool
            fund_trader_pool(
                web3=web3,
                trader_pool=trader_pool,
                eth_balance=config.wallet.eth_balance,
                token_balances=config.wallet.token_balances,
                vault_relayer=config.network.vault_relayer,
            )

            if verbose:
                console.print(f"  [green]✓[/green] Funded {trader_pool.get_pool_size()} wallets")
                # Print wallet addresses for verification
                for i, trader in enumerate(trader_pool.get_all_traders()):
                    console.print(f"    Wallet {i+1}: {trader.address}")
                console.print()

        except Exception as e:
            console.print(f"[bold red]Error funding wallets:[/bold red] {e}")
            console.print(
                "[yellow]Hint: Wallet funding requires Anvil running in fork mode[/yellow]"
            )
            raise SystemExit(1) from None
    elif verbose and (config.wallet.private_keys or config.wallet.generate_count > 0):
        console.print("[bold cyan]Wallet Configuration:[/bold cyan]")
        if config.wallet.private_keys:
            console.print(f"  Using {len(config.wallet.private_keys)} provided private keys")
        elif config.wallet.generate_count > 0:
            console.print(f"  Generated {config.wallet.generate_count} new wallets")
        console.print("  [yellow]Note: Funding disabled. Wallets may not have balance.[/yellow]")
        console.print()

    # Create order factories
    # Set amount range: use explicit config values if set, otherwise calculate from wallet funding
    if config.min_order_amount and config.max_order_amount:
        # Use explicitly configured order amounts
        amount_range = (config.min_order_amount, config.max_order_amount)
    elif config.wallet.funding_enabled:
        # Calculate from wallet funding: use 20-60% of minimum funded token balance
        # to ensure fees are coverable while avoiding insufficient balance errors
        min_token_balance = (
            min(config.wallet.token_balances.values()) if config.wallet.token_balances else 1.0
        )
        amount_range = (min_token_balance * 0.2, min_token_balance * 0.6)
    else:
        # Conservative default for unfunded wallets
        amount_range = (0.01, 0.1)

    if verbose:
        console.print("[cyan]Order Configuration:[/cyan]")
        console.print(f"  Amount range: {amount_range[0]} - {amount_range[1]} tokens")
        console.print()

    # Create API client first (needed for quotes in OrderFactory)
    api_client: OrderbookClient | None = None
    if not dry_run:
        api_client = OrderbookClient(
            base_url=config.api.base_url,
            timeout=config.api.timeout,
            max_retries=config.api.max_retries,
        )

        if verbose:
            console.print(f"[cyan]API Client:[/cyan] {config.api.base_url}")
            # Check API health
            is_healthy = await api_client.check_health()
            if is_healthy:
                console.print("[green]✓[/green] Orderbook API is healthy")
            else:
                console.print("[yellow]⚠[/yellow] Warning: Could not reach orderbook API")
            console.print()

    order_factory = OrderFactory(
        token_pair_registry=token_registry,
        chain_id=config.network.chain_id,
        settlement_contract=config.network.settlement_contract,
        amount_range=amount_range,
        valid_duration=60,  # 60 seconds for expiration testing
        fee_percentage=0.0,  # Zero fees (CoW Protocol calculates fees automatically)
        api_client=api_client,  # Pass API client for getting quotes
    )

    # Use a dummy Safe address for conditional orders (will be replaced with actual Safe per trader)
    dummy_safe_address = "0x0000000000000000000000000000000000000001"
    conditional_order_factory = ConditionalOrderFactory(
        token_pair_registry=token_registry,
        chain_id=config.network.chain_id,
        safe_wallet_address=dummy_safe_address,
    )

    # Create order signers
    order_signer = OrderSigner(
        chain_id=config.network.chain_id,
        settlement_contract=config.network.settlement_contract,
    )

    conditional_order_signer = ConditionalOrderSigner(
        chain_id=config.network.chain_id,
        composable_cow_contract=config.network.composable_cow_contract,
    )

    # Create shared metrics store for all components
    metrics_store = MetricsStore()

    # Create expiration checker for automatic order expiration tracking
    expiration_checker = ExpirationChecker(
        metrics_store=metrics_store,
        check_interval=5.0,  # Check every 5 seconds
    )

    # Start Prometheus exporter if port specified
    prometheus_exporter: PrometheusExporter | None = None
    if prometheus_port is not None:
        prometheus_exporter = PrometheusExporter(
            port=prometheus_port,
            scenario=config.trading_pattern,  # Use trading pattern as scenario name
        )
        prometheus_exporter.start()
        prometheus_exporter.register_with_store(metrics_store)

        # Set initial test metadata
        prometheus_exporter.set_test_duration(test_duration)
        prometheus_exporter.set_num_traders(num_traders)
        prometheus_exporter.set_test_start()

        if verbose:
            console.print(
                f"[cyan]Prometheus Exporter:[/cyan] http://localhost:{prometheus_port}/metrics"
            )
            console.print()

    # Create order tracker with metrics store
    order_tracker = OrderTracker(
        poll_interval=5.0,  # Poll every 5 seconds
        max_poll_attempts=36,  # Up to 180 seconds (3 minutes)
        metrics_store=metrics_store,
    )

    # Create trader behavior config from app config
    behavior_config = TraderBehaviorConfig(
        pattern=TradingPattern(config.trading_pattern),
        base_rate=config.base_rate,
        market_order_ratio=config.market_order_ratio,
        limit_order_ratio=config.limit_order_ratio,
        twap_order_ratio=config.twap_order_ratio,
        stop_loss_order_ratio=config.stop_loss_order_ratio,
        good_after_time_order_ratio=config.good_after_time_order_ratio,
        # Random interval parameters
        min_interval=config.min_interval,
        max_interval=config.max_interval,
        # Burst pattern parameters
        burst_size=config.burst_size,
        burst_interval=config.burst_interval,
        quiet_period=config.quiet_period,
        # Time-based parameters
        active_hours=config.active_hours,
        active_multiplier=config.active_multiplier,
        # Ramp parameters
        ramp_start_rate=config.ramp_start_rate,
        ramp_target_rate=config.ramp_target_rate,
        ramp_duration=config.ramp_duration,
        ramp_curve=config.ramp_curve,
        # Spike parameters
        spike_normal_rate=config.spike_normal_rate,
        spike_burst_rate=config.spike_burst_rate,
        spike_duration=config.spike_duration,
        spike_recovery_time=config.spike_recovery_time,
        # Poisson parameters
        poisson_lambda=config.poisson_lambda,
    )

    # Create rate limit config from app config
    rate_limit_config = RateLimitConfig(
        enable_per_trader_limit=config.enable_per_trader_rate_limit,
        max_orders_per_trader_per_second=config.max_orders_per_trader_per_second,
        max_orders_per_trader_per_minute=config.max_orders_per_trader_per_minute,
        enable_global_limit=config.enable_global_rate_limit,
        max_orders_global_per_second=config.max_orders_global_per_second,
        max_orders_global_per_minute=config.max_orders_global_per_minute,
        burst_allowance=config.rate_limit_burst_allowance,
    )

    # Create orchestration config
    orchestration_config = OrchestrationConfig(
        num_traders=num_traders,
        duration=float(test_duration),
        startup_interval=config.default_startup_interval,
        restart_on_failure=True,
        max_restarts_per_trader=3,
        graceful_shutdown_timeout=10.0,
        settlement_wait_time=float(settlement_wait_time),
    )

    # Create instrumented API client for metrics collection (skip in dry run mode)
    instrumented_client: InstrumentedOrderbookClient | None = None
    if not dry_run:
        instrumented_client = InstrumentedOrderbookClient(
            base_url=config.api.base_url,
            metrics_store=metrics_store,
            timeout=config.api.timeout,
            max_retries=config.api.max_retries,
        )

        if verbose:
            console.print(f"[cyan]Instrumented API Client:[/cyan] {config.api.base_url}")
            # Check API health
            is_healthy = await instrumented_client.check_health()
            if is_healthy:
                console.print("[green]✓[/green] Orderbook API is healthy")
            else:
                console.print("[yellow]⚠[/yellow] Warning: Could not reach orderbook API")
            console.print()

    orchestrator = TraderOrchestrator(
        trader_pool=trader_pool,
        order_factory=order_factory,
        conditional_order_factory=conditional_order_factory,
        order_signer=order_signer,
        conditional_order_signer=conditional_order_signer,
        order_tracker=order_tracker,
        default_behavior_config=behavior_config,
        orchestration_config=orchestration_config,
        api_client=instrumented_client,
        order_cleanup_config=config.order_cleanup,
        rate_limit_config=rate_limit_config,
    )

    # Set up graceful shutdown handlers for SIGINT and SIGTERM
    _register_shutdown_handlers(orchestrator)

    # Create resource monitor (only if not dry-run)
    resource_monitor = None
    if not dry_run:
        resource_config = ResourceMonitorConfig(
            service_patterns=["orderbook", "autopilot", "driver", "baseline", "chain"],
            sample_interval=5.0,
        )
        resource_monitor = ResourceMonitor(metrics_store, resource_config)

    # Start resource monitoring before test
    if resource_monitor:
        await resource_monitor.start()
        if verbose and resource_monitor.is_running():
            containers = resource_monitor.get_monitored_containers()
            console.print(f"[cyan]Resource Monitor:[/cyan] Monitoring {len(containers)} containers")
            console.print()

    # Run the test with progress display
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Running performance test with {num_traders} traders...",
                total=None,
            )

            try:
                # Start expiration checker
                await expiration_checker.start()

                # Start test
                start_time = datetime.now()

                # Capture start block for reconciliation
                if web3.is_connected():
                    start_block = web3.eth.block_number

                if prometheus_exporter:
                    # Calculate target rate from behavior config (orders per minute -> per second)
                    target_rate = behavior_config.base_rate / 60.0

                    # Run orchestrator and metrics update loop concurrently
                    metrics_task = asyncio.create_task(
                        update_prometheus_metrics(
                            prometheus_exporter,
                            orchestrator,
                            float(test_duration),
                            target_rate,
                        )
                    )
                    await orchestrator.run()
                    metrics_task.cancel()  # Stop metrics loop when test completes
                    try:
                        await metrics_task
                    except asyncio.CancelledError:
                        pass
                else:
                    await orchestrator.run()

                end_time = datetime.now()

                # Capture end block for reconciliation
                if web3.is_connected():
                    end_block = web3.eth.block_number

                progress.update(task, description="[bold green]Test completed!")

            except Exception as e:
                progress.update(task, description="[bold red]Test failed!")
                console.print(f"\n[bold red]Error:[/bold red] {e}")
                raise
    finally:
        # Stop expiration checker
        await expiration_checker.stop()

        # Stop resource monitoring
        if resource_monitor:
            await resource_monitor.stop()

        # Stop Prometheus exporter
        if prometheus_exporter:
            prometheus_exporter.stop()

    # Get metrics
    metrics = orchestrator.get_metrics()

    # Add timing and block information
    metrics["timing"] = {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "start_block": start_block,
        "end_block": end_block,
    }

    # Add configuration info
    metrics["config"] = {
        "num_traders": num_traders,
        "duration": test_duration,
        "chain_id": config.network.chain_id,
        "api_url": config.api.base_url,
        "dry_run": dry_run,
        "trading_pattern": config.trading_pattern,
        "base_rate": config.base_rate,
        "global_rate_limit_enabled": config.enable_global_rate_limit,
        "per_trader_rate_limit_enabled": config.enable_per_trader_rate_limit,
    }

    # Update orchestration metrics with actual config values
    metrics["orchestration"]["num_traders"] = num_traders
    metrics["orchestration"]["duration"] = test_duration
    metrics["orchestration"]["startup_interval"] = config.default_startup_interval

    # Order type breakdown is now provided by orchestrator from actual tracking
    # (removed ratio-based estimation)

    # Add trader statistics
    active_traders = sum(
        1 for trader in trader_pool.get_all_traders() if trader.orders_submitted > 0
    )
    metrics["traders"] = {
        "active_traders": active_traders,
        "total_traders": num_traders,
    }

    # Add performance metrics with percentiles from aggregator
    elapsed = metrics["orchestration"]["elapsed_time"]
    perf_metrics = create_performance_metrics_dict(metrics_store, elapsed)
    metrics["performance"] = perf_metrics

    # Add metrics store summary (API metrics, resource metrics)
    metrics["metrics_store"] = metrics_store.summary()

    # Also include the actual MetricsStore object for baseline creation
    metrics["_metrics_store_object"] = metrics_store

    # Include prometheus exporter for reconciliation updates
    metrics["_prometheus_exporter"] = prometheus_exporter

    return metrics


def run_command(
    config: PerformanceTestConfig,
    traders: int | None = None,
    duration: int | None = None,
    settlement_wait: int | None = None,
    output_format: str | None = None,
    save_results: bool = False,
    output_file: str | None = None,
    verbose: bool = False,
    dry_run: bool = False,
    prometheus_port: int | None = None,
    save_baseline: str | None = None,
    baseline_description: str = "",
    baseline_tags: list[str] | None = None,
) -> None:
    """Run command entry point.

    Args:
        config: Performance test configuration
        traders: Optional override for number of traders
        duration: Optional override for test duration (seconds)
        settlement_wait: Optional override for settlement wait time (seconds)
        output_format: Optional override for output format
        save_results: Whether to save results to file
        output_file: Optional path to save results
        verbose: Enable verbose output
        dry_run: Perform dry run without submitting orders
        prometheus_port: Optional port for Prometheus metrics exporter
        save_baseline: Optional baseline name to save after test completes
        baseline_description: Optional description for the baseline
        baseline_tags: Optional list of tags for the baseline

    Raises:
        SystemExit: On error (with appropriate exit code)
    """
    console = Console()

    try:
        # Merge verbose flag: CLI flag OR config setting
        use_verbose = verbose or config.output.verbose

        # Run the test
        metrics = asyncio.run(
            run_performance_test(
                config=config,
                traders=traders,
                duration=duration,
                settlement_wait=settlement_wait,
                verbose=use_verbose,
                dry_run=dry_run,
                prometheus_port=prometheus_port,
            )
        )

        # Extract MetricsStore and PrometheusExporter objects before formatting (not JSON serializable)
        metrics_store_obj = metrics.pop("_metrics_store_object", None)
        prometheus_exporter_obj = metrics.pop("_prometheus_exporter", None)

        # Determine output format
        fmt = output_format or config.output.format

        # Display results
        console.print("\n[bold green]Test Results:[/bold green]\n")

        if fmt == "json":
            console.print(format_metrics_json(metrics))
        elif fmt == "table":
            format_metrics_table(metrics, console)
        elif fmt in ["csv", "prometheus"]:
            # For non-interactive formats, show as JSON on console
            # but save in requested format if saving
            format_metrics_table(metrics, console)
        else:
            console.print(f"[bold red]Error:[/bold red] Unknown output format: {fmt}")
            sys.exit(1)

        # Run chain reconciliation (always enabled to verify on-chain state)
        if not dry_run:
            try:
                console.print("\n[bold cyan]Chain Reconciliation:[/bold cyan]")

                # Get block range
                start_block = metrics.get("timing", {}).get("start_block", 0)
                end_block = metrics.get("timing", {}).get("end_block", 0)

                if start_block == 0 or end_block == 0:
                    console.print(
                        "[yellow]⚠ Block numbers not captured, skipping reconciliation[/yellow]"
                    )
                elif not metrics_store_obj:
                    console.print(
                        "[yellow]⚠ MetricsStore not available, skipping reconciliation[/yellow]"
                    )
                else:
                    # Get submitted order UIDs from metrics store
                    all_orders = metrics_store_obj.get_all_orders()
                    submitted_order_uids = {order.order_uid for order in all_orders}

                    # Get database reported filled count
                    database_filled = metrics.get("orders", {}).get("orders_filled", 0)

                    # Create reconciliator
                    reconciliator = ChainReconciliator(rpc_url=config.network.rpc_url)

                    console.print(f"  Block range: {start_block} → {end_block}")
                    console.print(f"  Orders submitted: {len(submitted_order_uids)}")
                    console.print(f"  Database reported: {database_filled} filled\n")

                    # Run reconciliation
                    report = reconciliator.reconcile(
                        from_block=start_block,
                        to_block=end_block,
                        submitted_order_uids=submitted_order_uids,
                        database_filled_count=database_filled,
                    )

                    # Print report
                    reconciliator.print_report(report, verbose=use_verbose)

                    # Update database with on-chain trade data
                    try:
                        inserted_count = reconciliator.update_database(report)
                        if inserted_count > 0:
                            console.print(
                                f"\n[green]✓[/green] Database updated: {inserted_count} trade records inserted"
                            )
                            console.print("  Orders now correctly marked as FILLED in database")
                        else:
                            console.print(
                                "\n[yellow]Note:[/yellow] No new trade records to insert (may already exist)"
                            )
                    except Exception as db_error:
                        console.print(
                            f"[yellow]Warning:[/yellow] Failed to update database: {db_error}"
                        )
                        if use_verbose:
                            console.print(
                                "  Database updates failed, but metrics are still accurate from chain query"
                            )

                    # Update Prometheus metrics with accurate on-chain data
                    if prometheus_exporter_obj and prometheus_exporter_obj.is_running():
                        prometheus_exporter_obj.update_from_reconciliation(
                            total_orders=report.total_orders,
                            chain_filled=report.chain_filled,
                            database_filled=report.database_filled,
                        )
                        console.print(
                            "\n[green]✓[/green] Prometheus metrics updated with accurate on-chain data"
                        )

            except Exception as e:
                console.print(f"[bold red]Chain reconciliation error:[/bold red] {e}")
                if use_verbose:
                    console.print_exception()

        # Save results if requested
        should_save = save_results or config.output.save_results or output_file
        if should_save:
            # Table format is for console only, convert to JSON for file saving
            save_fmt = "json" if fmt == "table" else fmt

            if output_file:
                output_path = Path(output_file)
            else:
                # Auto-generate filename
                results_dir = config.output.results_dir
                results_dir.mkdir(parents=True, exist_ok=True)
                filename = create_result_filename(
                    prefix="perf-test",
                    output_format=save_fmt,
                )
                output_path = results_dir / filename

            save_metrics_to_file(metrics, save_fmt, output_path)
            console.print(f"\n[bold green]✓[/bold green] Results saved to: {output_path}")

        # Save baseline if requested
        if save_baseline:
            try:
                if not metrics_store_obj:
                    console.print(
                        "[bold yellow]Warning:[/bold yellow] MetricsStore not available, baseline not saved"
                    )
                else:
                    # Extract test parameters from metrics
                    orchestration = metrics.get("orchestration", {})

                    # Prepare config dict for baseline
                    baseline_config = {
                        "scenario_name": config.trading_pattern,
                        "duration_seconds": float(orchestration.get("duration", 0)),
                        "num_traders": orchestration.get("num_traders", 0),
                        "base_rate": config.base_rate,
                        "market_order_ratio": config.market_order_ratio,
                        "limit_order_ratio": config.limit_order_ratio,
                    }

                    # Create baseline manager and save
                    manager = BaselineManager()
                    baseline = manager.save(
                        name=save_baseline,
                        metrics_store=metrics_store_obj,
                        config=baseline_config,
                        description=baseline_description,
                        tags=baseline_tags,
                    )

                    console.print(
                        f"[bold green]✓[/bold green] Baseline saved: {baseline.name} (ID: {baseline.id[:8]}...)"
                    )
                    console.print(f"  Location: .cow-perf/baselines/{baseline.id}.json")
            except Exception as e:
                console.print(f"[bold red]Error saving baseline:[/bold red] {e}")
                if verbose:
                    console.print_exception()

    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        sys.exit(130)  # Standard exit code for SIGINT
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(3)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(1)
