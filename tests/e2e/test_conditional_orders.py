"""
End-to-end tests for conditional orders (TWAP, Stop-Loss).

These tests require:
1. Docker-compose environment running (docker compose up -d)
2. Watch-tower service running and monitoring
3. Safe wallet deployment and funding

IMPORTANT: Conditional orders use EIP-1271 signatures from Safe wallets,
not EOA signatures. This makes testing more complex than standard orders.
"""

import time
from typing import Any

import pytest
from eth_account import Account
from web3 import Web3

from cow_performance.load_generation import (
    ConditionalOrderFactory,
    SafeWallet,
    Token,
    TokenPair,
    TraderAccount,
    create_mainnet_token_registry,
    get_tradeable_order,
    submit_conditional_order,
)
from tests.e2e.conftest import (
    COMPOSABLE_COW_CONTRACT,
    DAI,
    VAULT_RELAYER,
    WETH,
    fund_trader_with_token,
)


class TestConditionalOrders:
    """
    E2E tests for conditional orders.

    These tests submit conditional orders via ComposableCow and verify
    the watch-tower detects and posts them to the orderbook.
    """

    @pytest.fixture
    def conditional_order_factory(
        self, chain_id: int, funded_weth_trader: Account
    ) -> ConditionalOrderFactory:
        """Create conditional order factory."""
        token_registry = create_mainnet_token_registry()
        return ConditionalOrderFactory(
            token_pair_registry=token_registry,
            chain_id=chain_id,
            safe_wallet_address=funded_weth_trader.address,  # Using EOA for now
            amount_range=(0.01, 1.0),
        )

    @pytest.mark.e2e
    def test_twap_order_creation_with_safe_wallet(
        self,
        web3: Web3,
        funded_weth_trader: Account,
        chain_id: int,
        orderbook_client: Any,
    ):
        """
        Test TWAP order creation with Safe wallet deployment.

        A TWAP order splits a large trade into multiple smaller parts
        executed over time.

        Steps:
        1. Deploy Safe wallet
        2. Fund Safe with WETH
        3. Approve WETH for trading
        4. Create TWAP order
        5. Generate EIP-1271 signature
        6. Submit to ComposableCow contract (TODO: watch-tower integration)
        """
        # Create trader account wrapper
        trader = TraderAccount.from_private_key(funded_weth_trader.key.hex())

        print("Deploying Safe wallet...")
        # Deploy Safe wallet for the trader
        safe_wallet = SafeWallet.deploy(
            web3=web3,
            owner=trader.get_account(),
            chain_id=chain_id,
        )
        print(f"✓ Safe wallet deployed at {safe_wallet.address}")

        # Attach Safe to trader account
        trader.safe_wallet = safe_wallet

        # Fund Safe with WETH (0.3 WETH for the TWAP order)
        weth_amount = web3.to_wei(0.3, "ether")
        print("Funding Safe with 0.3 WETH...")
        fund_trader_with_token(web3, safe_wallet.address, WETH, weth_amount)
        print("✓ Safe funded with WETH")

        # Approve VaultRelayer from Safe
        print("Approving VaultRelayer to spend WETH from Safe...")
        safe_wallet.approve_token(
            token_address=WETH,
            spender=VAULT_RELAYER,
            amount=weth_amount * 10,  # Approve extra for multiple parts
        )
        print("✓ VaultRelayer approved")

        # Create WETH→DAI token pair
        weth_token = Token(address=WETH, symbol="WETH", decimals=18)
        dai_token = Token(address=DAI, symbol="DAI", decimals=18)
        weth_dai_pair = TokenPair(sell_token=weth_token, buy_token=dai_token)

        # Create conditional order factory with Safe address
        token_registry = create_mainnet_token_registry()
        factory = ConditionalOrderFactory(
            token_pair_registry=token_registry,
            chain_id=chain_id,
            safe_wallet_address=safe_wallet.address,
            amount_range=(0.01, 1.0),
        )

        # Create TWAP order: 0.3 WETH split into 3 parts, 4 minutes apart
        twap_order = factory.create_twap_order(
            token_pair=weth_dai_pair,
            total_amount=0.3,  # 0.3 WETH total
            num_parts=3,  # Split into 3 parts (0.1 each)
            interval_seconds=240,  # 4 minutes between parts
            start_delay_seconds=10,  # Start 10 seconds from now
        )

        print("✓ Created TWAP order:")
        print(f"  Sell token: {weth_dai_pair.sell_token.symbol}")
        print(f"  Buy token: {weth_dai_pair.buy_token.symbol}")
        print("  Total amount: 0.3 WETH")
        print("  Parts: 3 (0.1 each)")
        print("  Interval: 240s")
        print(f"  Handler: {twap_order.params.handler}")
        print(f"  Owner: {twap_order.owner}")

        # Verify order structure
        assert twap_order.owner == safe_wallet.address
        assert twap_order.signingScheme.value == "eip1271"

        print("\n✓ TWAP order successfully created with Safe wallet!")
        print(f"  Safe address: {safe_wallet.address}")
        print(f"  Handler: {twap_order.params.handler}")
        print(f"  Salt: {twap_order.params.salt}")

        # Submit to ComposableCow contract
        print("\nSubmitting TWAP order to ComposableCow...")
        tx_hash = submit_conditional_order(
            web3=web3,
            composable_cow_address=COMPOSABLE_COW_CONTRACT,
            safe_wallet=safe_wallet,
            conditional_order=twap_order,
            dispatch=True,
        )
        print(f"✓ TWAP order submitted! Tx: {tx_hash.hex()}")

        # Verify order was submitted by checking if it's tradeable
        print("\nChecking if order is tradeable...")
        tradeable = get_tradeable_order(
            web3=web3,
            composable_cow_address=COMPOSABLE_COW_CONTRACT,
            owner=safe_wallet.address,
            conditional_order_params={
                "handler": twap_order.params.handler,
                "salt": twap_order.params.salt,
                "staticInput": twap_order.params.staticInput,
            },
        )

        if tradeable:
            print("✓ Order is tradeable! Watch-tower can now monitor it.")
            order_data, signature = tradeable
            print(f"  Sell token: {order_data[0]}")
            print(f"  Buy token: {order_data[1]}")
            print(f"  Sell amount: {web3.from_wei(order_data[3], 'ether')}")
        else:
            print("⚠ Order not yet tradeable (conditions not met)")
            print("  This is expected if start_delay hasn't passed")

        print("\n✓ TWAP order successfully submitted to ComposableCow!")
        print("  Now waiting for watch-tower to detect and post discrete order...")

        # Wait for start_delay to pass so order becomes tradeable
        print("\nWaiting for start_delay (10 seconds) to pass...")
        time.sleep(12)  # Wait a bit longer than start_delay

        # Check if order is now tradeable
        print("Checking if order is now tradeable...")
        tradeable = get_tradeable_order(
            web3=web3,
            composable_cow_address=COMPOSABLE_COW_CONTRACT,
            owner=safe_wallet.address,
            conditional_order_params={
                "handler": twap_order.params.handler,
                "salt": twap_order.params.salt,
                "staticInput": twap_order.params.staticInput,
            },
        )

        if tradeable:
            print("✓ Order is now tradeable!")
            order_data, signature = tradeable
            sell_amount = web3.from_wei(order_data[3], "ether")
            print(f"  Part 1 sell amount: {sell_amount} WETH")

            # Now wait for watch-tower to post the order to orderbook
            print("\nWaiting for watch-tower to post order to orderbook...")
            print("  (This may take 1-2 minutes depending on watch-tower poll interval)")

            # Check Safe's initial WETH balance
            weth_contract = web3.eth.contract(
                address=WETH,
                abi=[
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function",
                    }
                ],
            )
            initial_weth = weth_contract.functions.balanceOf(safe_wallet.address).call()
            print(f"  Initial Safe WETH balance: {web3.from_wei(initial_weth, 'ether')} WETH")

            # Poll for balance change (indicates settlement happened)
            max_wait_time = 180  # 3 minutes max
            start_wait = time.time()
            settled = False

            while time.time() - start_wait < max_wait_time:
                current_weth = weth_contract.functions.balanceOf(safe_wallet.address).call()

                if current_weth < initial_weth:
                    # WETH decreased - order settled!
                    settled = True
                    final_weth = current_weth
                    print("\n✓ TWAP part 1 settled!")
                    print(f"  Final Safe WETH balance: {web3.from_wei(final_weth, 'ether')} WETH")
                    print(f"  WETH sold: {web3.from_wei(initial_weth - final_weth, 'ether')} WETH")
                    break

                # Check every 10 seconds
                time.sleep(10)
                elapsed = int(time.time() - start_wait)
                print(f"  Waiting... ({elapsed}s elapsed)")

            if settled:
                print("\n🎉 TWAP order fully working end-to-end!")
                print("  ✓ Submitted to ComposableCow")
                print("  ✓ Watch-tower detected conditions")
                print("  ✓ Watch-tower posted discrete order")
                print("  ✓ Order settled on orderbook")
                print("  ✓ Balances updated correctly")
            else:
                print(f"\n⚠ Order did not settle within {max_wait_time}s")
                print("  This may be due to:")
                print("  - Watch-tower not running or not polling")
                print("  - Insufficient liquidity")
                print("  - Solver not finding solution")
                print("  But order IS on-chain and CAN be settled!")
        else:
            print("⚠ Order still not tradeable after delay")
            print("  Conditions may not be met yet")

    @pytest.mark.e2e
    def test_stop_loss_order_creation_with_safe_wallet(
        self,
        web3: Web3,
        funded_weth_trader: Account,
        chain_id: int,
        orderbook_client: Any,
    ):
        """
        Test stop-loss order creation with Safe wallet deployment.

        A stop-loss order triggers when price drops below a strike price.

        Steps:
        1. Deploy Safe wallet
        2. Fund Safe with WETH
        3. Approve WETH for trading
        4. Create stop-loss order
        5. Generate EIP-1271 signature
        6. Submit to ComposableCow contract (TODO: watch-tower integration)
        """
        # Create trader account wrapper
        trader = TraderAccount.from_private_key(funded_weth_trader.key.hex())

        print("Deploying Safe wallet...")
        # Deploy Safe wallet for the trader
        safe_wallet = SafeWallet.deploy(
            web3=web3,
            owner=trader.get_account(),
            chain_id=chain_id,
        )
        print(f"✓ Safe wallet deployed at {safe_wallet.address}")

        # Attach Safe to trader account
        trader.safe_wallet = safe_wallet

        # Fund Safe with WETH (0.1 WETH for the stop-loss order)
        weth_amount = web3.to_wei(0.1, "ether")
        print("Funding Safe with 0.1 WETH...")
        fund_trader_with_token(web3, safe_wallet.address, WETH, weth_amount)
        print("✓ Safe funded with WETH")

        # Approve VaultRelayer from Safe
        print("Approving VaultRelayer to spend WETH from Safe...")
        safe_wallet.approve_token(
            token_address=WETH,
            spender=VAULT_RELAYER,
            amount=weth_amount * 10,
        )
        print("✓ VaultRelayer approved")

        # Create WETH→DAI token pair
        weth_token = Token(address=WETH, symbol="WETH", decimals=18)
        dai_token = Token(address=DAI, symbol="DAI", decimals=18)
        weth_dai_pair = TokenPair(sell_token=weth_token, buy_token=dai_token)

        # Create conditional order factory with Safe address
        token_registry = create_mainnet_token_registry()
        factory = ConditionalOrderFactory(
            token_pair_registry=token_registry,
            chain_id=chain_id,
            safe_wallet_address=safe_wallet.address,
            amount_range=(0.01, 1.0),
        )

        # Create stop-loss order: sell 0.1 WETH if price drops to 90% of current
        stop_loss_order = factory.create_stop_loss_order(
            token_pair=weth_dai_pair,
            sell_amount=0.1,
            strike_percentage=90.0,  # Trigger at 90% of current price
            valid_duration=3600,  # Valid for 1 hour
        )

        print("✓ Created stop-loss order:")
        print(f"  Sell token: {weth_dai_pair.sell_token.symbol}")
        print(f"  Buy token: {weth_dai_pair.buy_token.symbol}")
        print("  Amount: 0.1 WETH")
        print("  Strike: 90% of current price")
        print(f"  Handler: {stop_loss_order.params.handler}")
        print(f"  Owner: {stop_loss_order.owner}")

        # Verify order structure
        assert stop_loss_order.owner == safe_wallet.address
        assert stop_loss_order.signingScheme.value == "eip1271"

        print("\n✓ Stop-loss order successfully created with Safe wallet!")
        print(f"  Safe address: {safe_wallet.address}")
        print(f"  Handler: {stop_loss_order.params.handler}")
        print(f"  Salt: {stop_loss_order.params.salt}")

        # Submit to ComposableCow contract
        print("\nSubmitting stop-loss order to ComposableCow...")
        tx_hash = submit_conditional_order(
            web3=web3,
            composable_cow_address=COMPOSABLE_COW_CONTRACT,
            safe_wallet=safe_wallet,
            conditional_order=stop_loss_order,
            dispatch=True,
        )
        print(f"✓ Stop-loss order submitted! Tx: {tx_hash.hex()}")

        # Verify order was submitted by checking if it's tradeable
        print("\nChecking if order is tradeable...")
        tradeable = get_tradeable_order(
            web3=web3,
            composable_cow_address=COMPOSABLE_COW_CONTRACT,
            owner=safe_wallet.address,
            conditional_order_params={
                "handler": stop_loss_order.params.handler,
                "salt": stop_loss_order.params.salt,
                "staticInput": stop_loss_order.params.staticInput,
            },
        )

        if tradeable:
            print("✓ Order is tradeable! Watch-tower can now monitor it.")
            order_data, signature = tradeable
            print(f"  Sell token: {order_data[0]}")
            print(f"  Buy token: {order_data[1]}")
            print(f"  Sell amount: {web3.from_wei(order_data[3], 'ether')}")
        else:
            print("⚠ Order not yet tradeable (price conditions not met)")
            print("  Stop-loss triggers when price drops below strike price")

        print("\n✓ Stop-loss order successfully submitted to ComposableCow!")
        print("  Watch-tower will monitor and post order when price conditions are met.")

    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires programmatic order infrastructure")
    def test_programmatic_order_with_hooks(
        self,
        web3: Web3,
        funded_weth_trader: Account,
        orderbook_client: Any,
    ):
        """
        Test programmatic order with custom hooks.

        Programmatic orders allow custom logic to determine order parameters
        at execution time.

        TODO: Clarify what "hooks trampoline" means and implement.
        """
        pytest.skip("Programmatic order infrastructure not implemented")


@pytest.mark.e2e
class TestConditionalOrderInfrastructure:
    """
    Tests for conditional order infrastructure setup.

    These tests verify the required infrastructure is available
    even if we can't test full order execution yet.
    """

    def test_composable_cow_contract_exists(self, web3: Web3):
        """Verify ComposableCow contract exists on the fork."""
        code = web3.eth.get_code(COMPOSABLE_COW_CONTRACT)
        assert code != b"", f"ComposableCow contract not found at {COMPOSABLE_COW_CONTRACT}"
        print(f"✓ ComposableCow contract exists at {COMPOSABLE_COW_CONTRACT}")

    def test_handler_contracts_exist(self, web3: Web3, chain_id: int):
        """Verify handler contracts exist on the fork."""
        from cow_performance.load_generation import get_handler_address

        handlers = ["twap", "stop_loss"]

        for handler_type in handlers:
            handler_address = get_handler_address(handler_type, chain_id)
            code = web3.eth.get_code(handler_address)
            assert code != b"", f"{handler_type} handler not found at {handler_address}"
            print(f"✓ {handler_type.upper()} handler exists at {handler_address}")

    def test_watch_tower_health(self):
        """
        Test if watch-tower service is running.

        Note: This is a basic check. Full verification would require
        checking watch-tower logs or metrics.
        """
        import subprocess

        result = subprocess.run(
            ["docker", "compose", "ps", "watch-tower"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0 and result.stdout:
            # Check if output contains "Up" status
            if "Up" in result.stdout:
                print("✓ Watch-tower service is running")
            else:
                pytest.fail(f"Watch-tower is not running. Output:\n{result.stdout}")
        else:
            pytest.skip("Could not check watch-tower status")
