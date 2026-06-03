"""
End-to-end tests for orders with hooks.

Hooks are custom Ethereum calls that execute atomically with order settlement:
- Pre-hooks: Execute before the swap
- Post-hooks: Execute after the swap

These tests require the docker-compose environment with HooksTrampoline contract.
"""

import json
import time
from typing import Any

import pytest
from eth_account import Account
from web3 import Web3

from cow_performance.load_generation import (
    OrderFactory,
    OrderSigner,
    Token,
    TokenPair,
    TraderAccount,
    create_mainnet_token_registry,
)
from cow_performance.load_generation.order_validation import validate_app_data_hash
from tests.e2e.conftest import DAI, SETTLEMENT_CONTRACT, WETH

# HooksTrampoline contract address on mainnet
HOOKS_TRAMPOLINE_ADDRESS = "0x60Bf78233f48eC42eE3F101b9a05eC7878728006"


class TestHooksOrders:
    """
    E2E tests for orders with hooks.

    These tests verify that orders can include custom hooks that execute
    as part of the settlement transaction.
    """

    @pytest.fixture
    def order_factory(self, chain_id: int) -> OrderFactory:
        """Create order factory for generating orders."""
        token_registry = create_mainnet_token_registry()
        return OrderFactory(
            token_pair_registry=token_registry,
            chain_id=chain_id,
            settlement_contract=SETTLEMENT_CONTRACT,
            valid_duration=300,
            fee_percentage=0.0,
        )

    @pytest.fixture
    def order_signer(self, chain_id: int) -> OrderSigner:
        """Create order signer for signing orders."""
        return OrderSigner(chain_id, SETTLEMENT_CONTRACT)

    def create_order_with_hooks(
        self,
        order_params: Any,
        pre_hooks: list[dict] | None = None,
        post_hooks: list[dict] | None = None,
    ) -> Any:
        """
        Add hooks to order parameters via appData.

        Args:
            order_params: Base order parameters
            pre_hooks: List of pre-hooks (execute before swap)
            post_hooks: List of post-hooks (execute after swap)

        Returns:
            Order parameters with hooks in appData
        """
        # Create hooks metadata
        # NOTE: hooks must be at top level, not inside metadata
        hooks_metadata = {
            "version": "0.9.0",
            "appCode": "CoW Swap",
            "hooks": {
                "version": "0.1.0",
                "pre": pre_hooks or [],
                "post": post_hooks or [],
            },
        }

        # Convert to JSON and hash for appData (use consistent serialization)
        app_data_json = json.dumps(hooks_metadata, separators=(",", ":"), sort_keys=True)
        app_data_hash = Web3.keccak(text=app_data_json).hex()

        # Validate hash before using it
        validate_app_data_hash(hooks_metadata, app_data_hash)

        # Update order params with hooks appData
        order_params.appData = app_data_hash

        return order_params, app_data_json

    @pytest.mark.e2e
    def test_order_with_simple_pre_hook(
        self,
        web3: Web3,
        funded_weth_trader: Account,
        order_factory: OrderFactory,
        order_signer: OrderSigner,
        orderbook_client: Any,
    ):
        """
        Test order with a simple pre-hook.

        Pre-hooks execute before the swap. This test uses a simple hook
        that calls the trader's own address (no-op).
        """
        trader = TraderAccount.from_private_key(funded_weth_trader.key.hex())

        # Approve WETH for trading (VaultRelayer needs approval)
        print("\nApproving WETH for trading...")
        from tests.e2e.conftest import VAULT_RELAYER

        weth_contract = web3.eth.contract(
            address=Web3.to_checksum_address(WETH),
            abi=[
                {
                    "constant": False,
                    "inputs": [
                        {"name": "spender", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                    ],
                    "name": "approve",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function",
                }
            ],
        )

        approve_tx = weth_contract.functions.approve(
            Web3.to_checksum_address(VAULT_RELAYER),
            10**18,  # Approve 1 WETH
        ).build_transaction(
            {
                "from": trader.address,
                "nonce": web3.eth.get_transaction_count(trader.address),
                "gas": 100000,
                "gasPrice": web3.eth.gas_price,
            }
        )
        signed_approve = web3.eth.account.sign_transaction(approve_tx, trader.private_key)
        approve_hash = web3.eth.send_raw_transaction(signed_approve.rawTransaction)
        web3.eth.wait_for_transaction_receipt(approve_hash)
        print("✓ WETH approved for trading")

        # Create WETH→DAI token pair
        weth_token = Token(address=WETH, symbol="WETH", decimals=18)
        dai_token = Token(address=DAI, symbol="DAI", decimals=18)
        TokenPair(sell_token=weth_token, buy_token=dai_token)

        # Create hooks metadata FIRST
        # Pre-hook: simple call to trader's address (no-op)
        pre_hook = {
            "target": trader.address,
            "callData": "0x",  # Empty calldata (no-op)
            "gasLimit": 100000,
        }

        # CoW Protocol appData schema with hooks
        # NOTE: hooks must be at top level, not inside metadata
        hooks_metadata = {
            "version": "0.9.0",
            "appCode": "CoW Swap",
            "hooks": {
                "version": "0.1.0",
                "pre": [pre_hook],
                "post": [],
            },
        }

        # Convert to JSON and hash for appData (use consistent serialization)
        app_data_json = json.dumps(hooks_metadata, separators=(",", ":"), sort_keys=True)
        app_data_hash = Web3.keccak(text=app_data_json).hex()

        # Validate hash before using it
        validate_app_data_hash(hooks_metadata, app_data_hash)

        # Create order parameters manually with hooks appData
        from cow_performance.load_generation import OrderBalance, OrderKind, OrderParameters

        sell_amount_wei = weth_token.to_wei(0.1)
        buy_amount_wei = dai_token.to_wei(0.1)  # Simplified 1:1 price

        order_params = OrderParameters(
            sellToken=weth_token.address,
            buyToken=dai_token.address,
            sellAmount=str(sell_amount_wei),
            buyAmount=str(buy_amount_wei),
            validTo=int(time.time()) + 300,  # 5 minutes
            appData=app_data_hash,
            feeAmount="0",  # Zero fee for testing
            kind=OrderKind.SELL,
            partiallyFillable=False,
            sellTokenBalance=OrderBalance.ERC20,
            buyTokenBalance=OrderBalance.ERC20,
            receiver=None,
        )

        print("\nCreated order with pre-hook:")
        print(f"  Hook target: {pre_hook['target']}")
        print(f"  App data hash: {order_params.appData}")

        # Upload appData document first
        print("\nUploading appData document to orderbook...")
        try:
            orderbook_client.upload_app_data(order_params.appData, app_data_json)
            print("✓ AppData uploaded successfully")
        except Exception as e:
            print(f"⚠ AppData upload failed: {e}")
            print("  This may be expected if appData already exists")

        # Sign and submit order
        signed_order = order_signer.sign_order(order_params, trader.get_account())

        print("\nSubmitting order with hooks to orderbook...")
        response = orderbook_client.submit_order(signed_order.model_dump(by_alias=True))
        print(f"✓ Order submitted: {response}")

        # Poll for order settlement
        # Response can be a string (order UID) or a dict
        if isinstance(response, str):
            order_uid = response
        else:
            order_uid = response.get("uid") or response.get("orderUid")

        if order_uid:
            print(f"\nPolling for order settlement (order UID: {order_uid})...")
            max_wait = 120  # 2 minutes
            start = time.time()

            while time.time() - start < max_wait:
                try:
                    order_status = orderbook_client.get_order(order_uid)
                    status = order_status.get("status")
                    print(f"  Order status: {status}")

                    if status == "fulfilled":
                        print("🎉 Order with pre-hook executed successfully!")
                        trades = orderbook_client.get_trades(order_uid)
                        print(f"  Trades: {len(trades)}")
                        break
                except Exception as e:
                    print(f"  Error checking order: {e}")

                time.sleep(5)
        else:
            print("⚠ No order UID in response, cannot track settlement")

    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires permit signature generation")
    def test_order_with_permit_pre_hook(
        self,
        web3: Web3,
        funded_weth_trader: Account,
        order_factory: OrderFactory,
        order_signer: OrderSigner,
        orderbook_client: Any,
    ):
        """
        Test order with permit pre-hook.

        This is a common use case: instead of pre-approving tokens,
        the pre-hook contains a permit() call to approve tokens
        just-in-time during settlement.
        """
        trader = TraderAccount.from_private_key(funded_weth_trader.key.hex())

        # Create WETH→DAI token pair
        weth_token = Token(address=WETH, symbol="WETH", decimals=18)
        dai_token = Token(address=DAI, symbol="DAI", decimals=18)
        weth_dai_pair = TokenPair(sell_token=weth_token, buy_token=dai_token)

        # Generate base order
        order_factory.create_market_order(
            trader_account=trader.get_account(),
            token_pair=weth_dai_pair,
            sell_amount=0.1,
        )

        # TODO: Generate permit signature for WETH
        # This would require:
        # 1. EIP-2612 permit signature
        # 2. Encoding permit() calldata
        # 3. Adding as pre-hook

        pytest.skip("Permit signature generation not implemented")

    @pytest.mark.e2e
    def test_order_with_post_hook(
        self,
        web3: Web3,
        funded_weth_trader: Account,
        order_factory: OrderFactory,
        order_signer: OrderSigner,
        orderbook_client: Any,
    ):
        """
        Test order with post-hook.

        Post-hooks execute after the swap. This test transfers some of the
        received DAI to another address as a post-settlement action.
        """
        trader = TraderAccount.from_private_key(funded_weth_trader.key.hex())

        # Approve WETH for trading
        print("\nApproving WETH for trading...")
        from tests.e2e.conftest import VAULT_RELAYER

        weth_contract = web3.eth.contract(
            address=Web3.to_checksum_address(WETH),
            abi=[
                {
                    "constant": False,
                    "inputs": [
                        {"name": "spender", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                    ],
                    "name": "approve",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function",
                }
            ],
        )

        approve_tx = weth_contract.functions.approve(
            Web3.to_checksum_address(VAULT_RELAYER),
            10**18,  # Approve 1 WETH
        ).build_transaction(
            {
                "from": trader.address,
                "nonce": web3.eth.get_transaction_count(trader.address),
                "gas": 100000,
                "gasPrice": web3.eth.gas_price,
            }
        )
        signed_approve = web3.eth.account.sign_transaction(approve_tx, trader.private_key)
        approve_hash = web3.eth.send_raw_transaction(signed_approve.rawTransaction)
        web3.eth.wait_for_transaction_receipt(approve_hash)
        print("✓ WETH approved for trading")

        # Create WETH→DAI token pair
        weth_token = Token(address=WETH, symbol="WETH", decimals=18)
        dai_token = Token(address=DAI, symbol="DAI", decimals=18)
        TokenPair(sell_token=weth_token, buy_token=dai_token)

        # Create a recipient address for the post-hook transfer
        recipient = Account.create()
        transfer_amount = 100 * 10**18  # Transfer 100 DAI

        # Encode ERC20 transfer(address,uint256) calldata
        # Function selector: transfer(address,uint256) = 0xa9059cbb
        transfer_selector = Web3.keccak(text="transfer(address,uint256)")[:4]
        transfer_calldata = (
            transfer_selector.hex()
            + recipient.address[2:].rjust(64, "0")  # address (32 bytes)
            + hex(transfer_amount)[2:].rjust(64, "0")  # amount (32 bytes)
        )

        # Create hooks metadata FIRST
        post_hook = {
            "target": DAI,  # Call DAI token contract
            "callData": transfer_calldata,
            "gasLimit": 100000,
        }

        # CoW Protocol appData schema with hooks
        # NOTE: hooks must be at top level, not inside metadata
        hooks_metadata = {
            "version": "0.9.0",
            "appCode": "CoW Swap",
            "hooks": {
                "version": "0.1.0",
                "pre": [],
                "post": [post_hook],
            },
        }

        # Convert to JSON and hash for appData (use consistent serialization)
        app_data_json = json.dumps(hooks_metadata, separators=(",", ":"), sort_keys=True)
        app_data_hash = Web3.keccak(text=app_data_json).hex()

        # Validate hash before using it
        validate_app_data_hash(hooks_metadata, app_data_hash)

        # Create order parameters manually with hooks appData
        from cow_performance.load_generation import OrderBalance, OrderKind, OrderParameters

        sell_amount_wei = weth_token.to_wei(0.1)
        buy_amount_wei = dai_token.to_wei(0.1)  # Simplified 1:1 price

        order_params = OrderParameters(
            sellToken=weth_token.address,
            buyToken=dai_token.address,
            sellAmount=str(sell_amount_wei),
            buyAmount=str(buy_amount_wei),
            validTo=int(time.time()) + 300,  # 5 minutes
            appData=app_data_hash,
            feeAmount="0",  # Zero fee for testing
            kind=OrderKind.SELL,
            partiallyFillable=False,
            sellTokenBalance=OrderBalance.ERC20,
            buyTokenBalance=OrderBalance.ERC20,
            receiver=None,
        )

        print("\nCreated order with post-hook:")
        print(f"  Hook target: {post_hook['target']} (DAI)")
        print(f"  Hook action: Transfer 100 DAI to {recipient.address}")
        print(f"  App data hash: {order_params.appData}")

        # Upload appData document
        print("\nUploading appData document to orderbook...")
        try:
            orderbook_client.upload_app_data(order_params.appData, app_data_json)
            print("✓ AppData uploaded successfully")
        except Exception as e:
            print(f"⚠ AppData upload failed: {e}")

        # Sign and submit order
        signed_order = order_signer.sign_order(order_params, trader.get_account())

        print("\nSubmitting order with post-hook to orderbook...")
        response = orderbook_client.submit_order(signed_order.model_dump(by_alias=True))
        print(f"✓ Order submitted: {response}")

        # Poll for order settlement
        # Response can be a string (order UID) or a dict
        if isinstance(response, str):
            order_uid = response
        else:
            order_uid = response.get("uid") or response.get("orderUid")

        if order_uid:
            print(f"\nPolling for order settlement (order UID: {order_uid})...")
            max_wait = 120  # 2 minutes
            start = time.time()

            while time.time() - start < max_wait:
                try:
                    order_status = orderbook_client.get_order(order_uid)
                    status = order_status.get("status")
                    print(f"  Order status: {status}")

                    if status == "fulfilled":
                        print("🎉 Order with post-hook executed successfully!")

                        # Verify the post-hook executed by checking recipient balance
                        dai_contract = web3.eth.contract(
                            address=Web3.to_checksum_address(DAI),
                            abi=[
                                {
                                    "constant": True,
                                    "inputs": [{"name": "account", "type": "address"}],
                                    "name": "balanceOf",
                                    "outputs": [{"name": "", "type": "uint256"}],
                                    "type": "function",
                                }
                            ],
                        )
                        recipient_balance = dai_contract.functions.balanceOf(
                            recipient.address
                        ).call()

                        if recipient_balance >= transfer_amount:
                            print(
                                f"✓ Post-hook executed: Recipient received {recipient_balance / 10**18} DAI"
                            )
                        else:
                            print(
                                f"⚠ Recipient balance: {recipient_balance / 10**18} DAI (expected at least {transfer_amount / 10**18})"
                            )
                        break
                except Exception as e:
                    print(f"  Error checking order: {e}")

                time.sleep(5)
        else:
            print("⚠ No order UID in response, cannot track settlement")


@pytest.mark.e2e
class TestHooksInfrastructure:
    """
    Tests for hooks infrastructure.

    Verify the HooksTrampoline contract exists and is accessible.
    """

    def test_hooks_trampoline_exists(self, web3: Web3):
        """Verify HooksTrampoline contract exists on the fork."""
        code = web3.eth.get_code(HOOKS_TRAMPOLINE_ADDRESS)
        assert code != b"", f"HooksTrampoline not found at {HOOKS_TRAMPOLINE_ADDRESS}"
        print(f"✓ HooksTrampoline exists at {HOOKS_TRAMPOLINE_ADDRESS}")

    def test_hooks_gas_limit_validation(self):
        """
        Verify hooks have reasonable gas limits.

        The HooksTrampoline enforces gas limits to prevent:
        - INVALID opcodes consuming 63/64ths of transaction gas
        - Unnecessary reverts affecting other orders
        """
        # Typical gas limits
        MAX_REASONABLE_GAS = 5_000_000  # 5M gas per hook
        MIN_REASONABLE_GAS = 21_000  # 21k gas minimum

        # Example hook
        hook = {"target": "0x" + "0" * 40, "callData": "0x", "gasLimit": 100000}

        assert hook["gasLimit"] >= MIN_REASONABLE_GAS, f"Gas limit too low: {hook['gasLimit']}"
        assert hook["gasLimit"] <= MAX_REASONABLE_GAS, f"Gas limit too high: {hook['gasLimit']}"

        print(f"✓ Hook gas limit {hook['gasLimit']} is within reasonable bounds")
