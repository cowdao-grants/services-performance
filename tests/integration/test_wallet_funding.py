"""Integration tests for wallet funding functionality.

These tests require Anvil running in fork mode.
Run with: pytest tests/integration/test_wallet_funding.py -v
"""

import pytest
from web3 import Web3

from cow_performance.cli.wallet_funding import (
    TOKEN_ADDRESSES,
    approve_token,
    fund_trader_pool,
    fund_wallet_with_eth,
    fund_wallet_with_token,
)
from cow_performance.load_generation import TraderPool


@pytest.fixture
def anvil_web3() -> Web3:
    """Connect to Anvil fork."""
    web3 = Web3(Web3.HTTPProvider("http://localhost:8545"))
    if not web3.is_connected():
        pytest.skip("Anvil is not running at http://localhost:8545")
    return web3


@pytest.fixture
def vault_relayer() -> str:
    """VaultRelayer contract address."""
    return "0xC92E8bdf79f0507f65a392b0ab4667716BFE0110"


# ERC20 ABI for balance and allowance checks
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


@pytest.mark.integration
class TestWalletFunding:
    """Test wallet funding functionality."""

    def test_fund_wallet_with_eth(self, anvil_web3: Web3) -> None:
        """Test funding a wallet with ETH."""
        # Create a new wallet
        trader_pool = TraderPool(num_traders=1)
        wallet_address = trader_pool.get_all_traders()[0].address

        # Check initial balance (should be 0)
        initial_balance = anvil_web3.eth.get_balance(wallet_address)
        assert initial_balance == 0

        # Fund with 10 ETH
        fund_wallet_with_eth(anvil_web3, wallet_address, 10.0)

        # Verify balance
        final_balance = anvil_web3.eth.get_balance(wallet_address)
        assert final_balance == anvil_web3.to_wei(10.0, "ether")

    def test_fund_wallet_with_weth(self, anvil_web3: Web3) -> None:
        """Test funding a wallet with WETH tokens."""
        # Create a new wallet
        trader_pool = TraderPool(num_traders=1)
        wallet_address = trader_pool.get_all_traders()[0].address

        # Get WETH contract
        weth_address = TOKEN_ADDRESSES["WETH"]
        weth_contract = anvil_web3.eth.contract(
            address=Web3.to_checksum_address(weth_address), abi=ERC20_ABI
        )

        # Check initial balance (should be 0)
        initial_balance = weth_contract.functions.balanceOf(wallet_address).call()
        assert initial_balance == 0

        # Fund with 5 WETH
        fund_wallet_with_token(anvil_web3, wallet_address, "WETH", 5.0)

        # Verify balance
        final_balance = weth_contract.functions.balanceOf(wallet_address).call()
        expected_balance = int(5.0 * 10**18)
        assert final_balance == expected_balance

    def test_fund_wallet_with_dai(self, anvil_web3: Web3) -> None:
        """Test funding a wallet with DAI tokens."""
        # Create a new wallet
        trader_pool = TraderPool(num_traders=1)
        wallet_address = trader_pool.get_all_traders()[0].address

        # Get DAI contract
        dai_address = TOKEN_ADDRESSES["DAI"]
        dai_contract = anvil_web3.eth.contract(
            address=Web3.to_checksum_address(dai_address), abi=ERC20_ABI
        )

        # Check initial balance (should be 0)
        initial_balance = dai_contract.functions.balanceOf(wallet_address).call()
        assert initial_balance == 0

        # Fund with 5000 DAI
        fund_wallet_with_token(anvil_web3, wallet_address, "DAI", 5000.0)

        # Verify balance
        final_balance = dai_contract.functions.balanceOf(wallet_address).call()
        expected_balance = int(5000.0 * 10**18)
        assert final_balance == expected_balance

    def test_fund_wallet_with_usdc(self, anvil_web3: Web3) -> None:
        """Test funding a wallet with USDC tokens (6 decimals)."""
        # Create a new wallet
        trader_pool = TraderPool(num_traders=1)
        wallet_address = trader_pool.get_all_traders()[0].address

        # Get USDC contract
        usdc_address = TOKEN_ADDRESSES["USDC"]
        usdc_contract = anvil_web3.eth.contract(
            address=Web3.to_checksum_address(usdc_address), abi=ERC20_ABI
        )

        # Check initial balance (should be 0)
        initial_balance = usdc_contract.functions.balanceOf(wallet_address).call()
        assert initial_balance == 0

        # Fund with 5000 USDC
        fund_wallet_with_token(anvil_web3, wallet_address, "USDC", 5000.0)

        # Verify balance (USDC has 6 decimals)
        final_balance = usdc_contract.functions.balanceOf(wallet_address).call()
        expected_balance = int(5000.0 * 10**6)
        assert final_balance == expected_balance

    def test_approve_token(self, anvil_web3: Web3, vault_relayer: str) -> None:
        """Test token approval functionality."""
        # Create a wallet with ETH for gas
        trader_pool = TraderPool(num_traders=1)
        trader = trader_pool.get_all_traders()[0]
        trader_account = trader.get_account()

        # Fund with ETH for gas
        fund_wallet_with_eth(anvil_web3, trader.address, 1.0)

        # Fund with WETH
        fund_wallet_with_token(anvil_web3, trader.address, "WETH", 10.0)

        # Get WETH contract
        weth_address = TOKEN_ADDRESSES["WETH"]
        weth_contract = anvil_web3.eth.contract(
            address=Web3.to_checksum_address(weth_address), abi=ERC20_ABI
        )

        # Check initial allowance (should be 0)
        initial_allowance = weth_contract.functions.allowance(trader.address, vault_relayer).call()
        assert initial_allowance == 0

        # Approve VaultRelayer to spend 100 WETH
        approve_token(anvil_web3, trader_account, "WETH", vault_relayer, 100.0)

        # Verify allowance
        final_allowance = weth_contract.functions.allowance(trader.address, vault_relayer).call()
        expected_allowance = int(100.0 * 10**18)
        assert final_allowance == expected_allowance

    def test_fund_trader_pool(self, anvil_web3: Web3, vault_relayer: str) -> None:
        """Test funding an entire trader pool."""
        # Create trader pool with 3 traders
        num_traders = 3
        trader_pool = TraderPool(num_traders=num_traders)

        # Define funding amounts
        eth_balance = 10.0
        token_balances = {
            "WETH": 5.0,
            "DAI": 5000.0,
            "USDC": 3000.0,
        }

        # Fund the entire pool
        fund_trader_pool(
            web3=anvil_web3,
            trader_pool=trader_pool,
            eth_balance=eth_balance,
            token_balances=token_balances,
            vault_relayer=vault_relayer,
        )

        # Verify all traders are funded correctly
        for trader in trader_pool.get_all_traders():
            # Check ETH balance
            eth_bal = anvil_web3.eth.get_balance(trader.address)
            # Allow for gas spent on approvals
            assert eth_bal > anvil_web3.to_wei(9.9, "ether")

            # Check WETH
            weth_contract = anvil_web3.eth.contract(
                address=Web3.to_checksum_address(TOKEN_ADDRESSES["WETH"]), abi=ERC20_ABI
            )
            weth_balance = weth_contract.functions.balanceOf(trader.address).call()
            assert weth_balance == int(5.0 * 10**18)

            weth_allowance = weth_contract.functions.allowance(trader.address, vault_relayer).call()
            assert weth_allowance == int(50.0 * 10**18)  # 10x approval

            # Check DAI
            dai_contract = anvil_web3.eth.contract(
                address=Web3.to_checksum_address(TOKEN_ADDRESSES["DAI"]), abi=ERC20_ABI
            )
            dai_balance = dai_contract.functions.balanceOf(trader.address).call()
            assert dai_balance == int(5000.0 * 10**18)

            dai_allowance = dai_contract.functions.allowance(trader.address, vault_relayer).call()
            assert dai_allowance == int(50000.0 * 10**18)  # 10x approval

            # Check USDC
            usdc_contract = anvil_web3.eth.contract(
                address=Web3.to_checksum_address(TOKEN_ADDRESSES["USDC"]), abi=ERC20_ABI
            )
            usdc_balance = usdc_contract.functions.balanceOf(trader.address).call()
            assert usdc_balance == int(3000.0 * 10**6)  # 6 decimals

            usdc_allowance = usdc_contract.functions.allowance(trader.address, vault_relayer).call()
            assert usdc_allowance == int(30000.0 * 10**6)  # 10x approval

    def test_unsupported_token_raises_error(self, anvil_web3: Web3) -> None:
        """Test that unsupported token raises ValueError."""
        trader_pool = TraderPool(num_traders=1)
        wallet_address = trader_pool.get_all_traders()[0].address

        with pytest.raises(ValueError, match="Unsupported token: INVALID"):
            fund_wallet_with_token(anvil_web3, wallet_address, "INVALID", 100.0)
