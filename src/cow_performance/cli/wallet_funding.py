"""Wallet funding utilities for Anvil fork mode.

This module provides functionality to fund trader wallets with ETH and tokens
before running performance tests. This requires Anvil running in fork mode.
"""

from typing import Any

from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.types import Nonce, RPCEndpoint, Wei

from cow_performance.load_generation import TraderPool

# Token addresses on mainnet
TOKEN_ADDRESSES = {
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "GNO": "0x6810e776880C02933D47DB1b9fc05908e5386b96",
}

# Addresses used as the caller for token minting/transfer.
# DAI: MCD_JOIN_DAI is an authorized ward of the Dai contract — can call mint() directly.
# USDC: minted via masterMinter → configureMinter → mint() (no whale balance needed).
# USDT/GNO: Curve 3pool is a large stable holder.
_WHALE_ADDRESSES: dict[str, str] = {
    "DAI": "0x9759A6Ac90977b93B58547b4A71c78317f391A28",  # MCD_JOIN_DAI (ward → can mint)
    "USDT": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",  # Curve 3pool
    "GNO": "0x4f8AD938ebA0CD19155a835f617317a6E788c868",  # GNO holder
}

# DAI has a mint(address, uint) function restricted to authorized wards.
# MCD_JOIN_DAI is a ward, so we call mint instead of transfer.
_DAI_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
_DAI_MINT_ABI = [
    {
        "inputs": [
            {"name": "usr", "type": "address"},
            {"name": "wad", "type": "uint256"},
        ],
        "name": "mint",
        "outputs": [],
        "type": "function",
        "stateMutability": "nonpayable",
    }
]

# USDC FiatToken ABI — masterMinter query + configureMinter + mint.
# USDC uses a permissioned minting system: masterMinter configures minters,
# minters call mint(). We impersonate masterMinter to configure itself as a
# minter, then call mint() for each trader — no whale balance needed.
_USDC_ABI = [
    {
        "inputs": [],
        "name": "masterMinter",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
        "stateMutability": "view",
    },
    {
        "inputs": [
            {"name": "minter", "type": "address"},
            {"name": "minterAllowedAmount", "type": "uint256"},
        ],
        "name": "configureMinter",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
        "stateMutability": "nonpayable",
    },
    {
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_amount", "type": "uint256"},
        ],
        "name": "mint",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
        "stateMutability": "nonpayable",
    },
]

# ERC20 ABI — approve + transfer
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
        "stateMutability": "nonpayable",
    },
]

# WETH9 deposit ABI
_WETH9_ABI = [
    {
        "name": "deposit",
        "type": "function",
        "inputs": [],
        "outputs": [],
        "stateMutability": "payable",
    }
]


def _token_amount_wei(token_symbol: str, amount: float) -> int:
    """Convert a human-readable token amount to the token's base unit (wei)."""
    if token_symbol in ("USDC", "USDT"):
        return int(amount * 10**6)
    return int(amount * 10**18)


def fund_wallet_with_token(
    web3: Web3, wallet_address: str, token_symbol: str, amount: float
) -> None:
    """Fund a single wallet address with tokens using Anvil impersonation.

    Args:
        web3: Web3 instance connected to Anvil
        wallet_address: Address to fund
        token_symbol: Token symbol (WETH, DAI, USDC, USDT, or GNO)
        amount: Amount to fund in standard units

    Raises:
        ValueError: If token is not supported or funding fails
    """
    if token_symbol not in TOKEN_ADDRESSES:
        supported = ", ".join(TOKEN_ADDRESSES.keys())
        raise ValueError(f"Unsupported token: {token_symbol}. Supported: {supported}")

    amount_wei = _token_amount_wei(token_symbol, amount)
    checksum_address = Web3.to_checksum_address(wallet_address)
    gas_price: int = max(1, web3.eth.gas_price)

    if token_symbol == "WETH":
        weth_address = Web3.to_checksum_address(TOKEN_ADDRESSES["WETH"])
        extra_eth = web3.eth.get_balance(checksum_address) + amount_wei + web3.to_wei(0.1, "ether")
        web3.provider.make_request(
            RPCEndpoint("anvil_setBalance"), [wallet_address, hex(extra_eth)]
        )
        web3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [wallet_address])
        deposit_nonce: int = web3.eth.get_transaction_count(checksum_address)
        tx_hash = web3.eth.send_transaction(
            {
                "from": wallet_address,
                "to": weth_address,
                "value": Wei(amount_wei),
                "data": bytes.fromhex("d0e30db0"),
                "gas": 60000,
                "gasPrice": Wei(gas_price),
                "nonce": Nonce(deposit_nonce),
            }
        )
        web3.provider.make_request(RPCEndpoint("evm_mine"), [])
        web3.provider.make_request(RPCEndpoint("anvil_stopImpersonatingAccount"), [wallet_address])
        receipt = web3.eth.get_transaction_receipt(tx_hash)
        if receipt is None or receipt["status"] != 1:
            raise ValueError(f"WETH deposit failed for {wallet_address}")

    elif token_symbol == "DAI":
        dai_address = Web3.to_checksum_address(_DAI_ADDRESS)
        dai_contract = web3.eth.contract(address=dai_address, abi=_DAI_MINT_ABI)
        dai_minter = _WHALE_ADDRESSES["DAI"]
        web3.provider.make_request(
            RPCEndpoint("anvil_setBalance"), [dai_minter, hex(web3.to_wei(1, "ether"))]
        )
        web3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [dai_minter])
        dai_nonce: int = web3.eth.get_transaction_count(Web3.to_checksum_address(dai_minter))
        tx_hash = web3.eth.send_transaction(
            {
                "from": dai_minter,
                "to": dai_address,
                "data": dai_contract.encodeABI(fn_name="mint", args=[checksum_address, amount_wei]),
                "gas": 100000,
                "gasPrice": Wei(gas_price),
                "nonce": Nonce(dai_nonce),
            }
        )
        web3.provider.make_request(RPCEndpoint("evm_mine"), [])
        web3.provider.make_request(RPCEndpoint("anvil_stopImpersonatingAccount"), [dai_minter])
        receipt = web3.eth.get_transaction_receipt(tx_hash)
        if receipt is None or receipt["status"] != 1:
            raise ValueError(f"DAI mint failed for {wallet_address}")

    elif token_symbol == "USDC":
        usdc_address = Web3.to_checksum_address(TOKEN_ADDRESSES["USDC"])
        usdc_contract = web3.eth.contract(address=usdc_address, abi=_USDC_ABI)
        master_minter = usdc_contract.functions.masterMinter().call()
        web3.provider.make_request(
            RPCEndpoint("anvil_setBalance"), [master_minter, hex(web3.to_wei(1, "ether"))]
        )
        web3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [master_minter])
        mm_nonce: int = web3.eth.get_transaction_count(Web3.to_checksum_address(master_minter))
        configure_hash = web3.eth.send_transaction(
            {
                "from": master_minter,
                "to": usdc_address,
                "data": usdc_contract.encodeABI(
                    fn_name="configureMinter", args=[master_minter, 2**256 - 1]
                ),
                "gas": 100000,
                "gasPrice": Wei(gas_price),
                "nonce": Nonce(mm_nonce),
            }
        )
        mm_nonce += 1
        web3.provider.make_request(RPCEndpoint("evm_mine"), [])
        configure_receipt = web3.eth.get_transaction_receipt(configure_hash)
        if configure_receipt is None or configure_receipt["status"] != 1:
            raise ValueError("USDC configureMinter failed")
        tx_hash = web3.eth.send_transaction(
            {
                "from": master_minter,
                "to": usdc_address,
                "data": usdc_contract.encodeABI(
                    fn_name="mint", args=[checksum_address, amount_wei]
                ),
                "gas": 100000,
                "gasPrice": Wei(gas_price),
                "nonce": Nonce(mm_nonce),
            }
        )
        web3.provider.make_request(RPCEndpoint("evm_mine"), [])
        web3.provider.make_request(RPCEndpoint("anvil_stopImpersonatingAccount"), [master_minter])
        receipt = web3.eth.get_transaction_receipt(tx_hash)
        if receipt is None or receipt["status"] != 1:
            raise ValueError(f"USDC mint failed for {wallet_address}")

    else:
        whale = _WHALE_ADDRESSES.get(token_symbol)
        if not whale:
            raise ValueError(f"No whale configured for token: {token_symbol}")
        token_address = Web3.to_checksum_address(TOKEN_ADDRESSES[token_symbol])
        token_contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)
        web3.provider.make_request(
            RPCEndpoint("anvil_setBalance"), [whale, hex(web3.to_wei(1, "ether"))]
        )
        web3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [whale])
        whale_nonce: int = web3.eth.get_transaction_count(Web3.to_checksum_address(whale))
        tx_hash = web3.eth.send_transaction(
            {
                "from": whale,
                "to": token_address,
                "data": token_contract.encodeABI(
                    fn_name="transfer", args=[checksum_address, amount_wei]
                ),
                "gas": 100000,
                "gasPrice": Wei(gas_price),
                "nonce": Nonce(whale_nonce),
            }
        )
        web3.provider.make_request(RPCEndpoint("evm_mine"), [])
        web3.provider.make_request(RPCEndpoint("anvil_stopImpersonatingAccount"), [whale])
        receipt = web3.eth.get_transaction_receipt(tx_hash)
        if receipt is None or receipt["status"] != 1:
            raise ValueError(f"{token_symbol} transfer failed for {wallet_address}")


def fund_wallet_with_eth(web3: Web3, wallet_address: str, amount_eth: float) -> None:
    """Fund a wallet with ETH using Anvil's anvil_setBalance (instant, no mining).

    Args:
        web3: Web3 instance connected to Anvil
        wallet_address: Address to fund
        amount_eth: Amount of ETH to send
    """
    amount_wei = web3.to_wei(amount_eth, "ether")
    web3.provider.make_request(RPCEndpoint("anvil_setBalance"), [wallet_address, hex(amount_wei)])


def _submit_approve_transaction(
    web3: Web3,
    trader_account: LocalAccount,
    token_symbol: str,
    spender: str,
    amount: float,
    nonce: int | None = None,
) -> Any:
    """Submit an ERC20 approve transaction and return the tx hash (does not wait for mining).

    Args:
        web3: Web3 instance
        trader_account: The trader's eth_account.Account instance
        token_symbol: Token symbol (WETH, DAI, USDC, USDT, or GNO)
        spender: Address to approve (usually VaultRelayer)
        amount: Amount to approve (in standard units)

    Returns:
        Transaction hash bytes
    """
    if token_symbol not in TOKEN_ADDRESSES:
        supported = ", ".join(TOKEN_ADDRESSES.keys())
        raise ValueError(f"Unsupported token: {token_symbol}. Supported: {supported}")

    token_address = TOKEN_ADDRESSES[token_symbol]
    amount_wei = _token_amount_wei(token_symbol, amount)

    token_contract = web3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
    )

    if nonce is None:
        nonce = web3.eth.get_transaction_count(Web3.to_checksum_address(trader_account.address))
    tx = token_contract.functions.approve(spender, amount_wei).build_transaction(
        {
            "from": trader_account.address,
            "nonce": Nonce(nonce),
            "gas": 100000,
            "gasPrice": Wei(max(1, web3.eth.gas_price)),
        }
    )

    signed_tx = web3.eth.account.sign_transaction(tx, trader_account.key)
    return web3.eth.send_raw_transaction(signed_tx.rawTransaction)


def approve_token(
    web3: Web3, trader_account: LocalAccount, token_symbol: str, spender: str, amount: float
) -> None:
    """Approve a spender to use tokens (submit and wait for receipt).

    Args:
        web3: Web3 instance
        trader_account: The trader's eth_account.Account instance
        token_symbol: Token symbol (WETH, DAI, USDC, USDT, or GNO)
        spender: Address to approve (usually VaultRelayer)
        amount: Amount to approve (in standard units)

    Raises:
        ValueError: If token is not supported or approval fails
    """
    tx_hash = _submit_approve_transaction(web3, trader_account, token_symbol, spender, amount)
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt["status"] != 1:
        raise ValueError(
            f"Failed to approve {token_symbol} for {spender} from {trader_account.address}"
        )


def fund_trader_pool(
    web3: Web3,
    trader_pool: TraderPool,
    eth_balance: float,
    token_balances: dict[str, float],
    vault_relayer: str,
) -> None:
    """Fund all traders in a pool with ETH and tokens.

    Strategy:
    - ETH: set instantly via anvil_setBalance
    - WETH: each trader deposits their own ETH into the WETH9 contract
      (traders are given extra ETH = eth_balance + weth_amount so they can wrap it)
    - Other tokens (DAI, USDC, ...): impersonate a large whale and transfer
    - All funding transactions are submitted in batch and mined in one forced block
    - Token approvals are then submitted and waited on in bulk

    Args:
        web3: Web3 instance connected to Anvil
        trader_pool: Pool of traders to fund
        eth_balance: ETH amount per trader (for operational use, not counting WETH wrap)
        token_balances: Dict of token symbol to amount per trader
        vault_relayer: VaultRelayer address for approvals

    Raises:
        ValueError: If funding or approval fails
    """
    traders = trader_pool.get_all_traders()

    weth_amount_wei = _token_amount_wei("WETH", token_balances.get("WETH", 0.0))

    # Step 1 — set ETH balances instantly.
    # If WETH funding is requested, extra ETH equal to the WETH amount is added
    # so traders can deposit it into the WETH9 contract.
    for trader in traders:
        total_eth_wei = web3.to_wei(eth_balance, "ether") + weth_amount_wei
        web3.provider.make_request(
            RPCEndpoint("anvil_setBalance"), [trader.address, hex(total_eth_wei)]
        )

    # Step 2 — submit all token-funding transactions without waiting for mining.
    # Each entry is (description, tx_hash) so failures are easy to diagnose.
    funding_ops: list[tuple[str, Any]] = []
    gas_price: int = max(1, web3.eth.gas_price)

    # WETH: each trader deposits their own ETH → WETH
    if weth_amount_wei > 0:
        weth_address = Web3.to_checksum_address(TOKEN_ADDRESSES["WETH"])
        # deposit() selector: keccak256("deposit()") = 0xd0e30db0
        for trader in traders:
            web3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [trader.address])
            trader_nonce: int = web3.eth.get_transaction_count(
                Web3.to_checksum_address(trader.address)
            )
            tx_hash = web3.eth.send_transaction(
                {
                    "from": trader.address,
                    "to": weth_address,
                    "value": Wei(weth_amount_wei),
                    "data": bytes.fromhex("d0e30db0"),
                    "gas": 60000,
                    "gasPrice": Wei(gas_price),
                    "nonce": Nonce(trader_nonce),
                }
            )
            funding_ops.append((f"WETH deposit for {trader.address[:10]}", tx_hash))
            web3.provider.make_request(
                RPCEndpoint("anvil_stopImpersonatingAccount"), [trader.address]
            )

    # DAI: impersonate MCD_JOIN_DAI (an authorized ward) and call mint() directly.
    # This is unlimited — no external whale balance needed.
    if "DAI" in token_balances and token_balances["DAI"] > 0:
        dai_address = Web3.to_checksum_address(_DAI_ADDRESS)
        dai_contract = web3.eth.contract(address=dai_address, abi=_DAI_MINT_ABI)
        dai_minter = _WHALE_ADDRESSES["DAI"]
        dai_amount_wei = _token_amount_wei("DAI", token_balances["DAI"])

        web3.provider.make_request(
            RPCEndpoint("anvil_setBalance"), [dai_minter, hex(web3.to_wei(1, "ether"))]
        )
        web3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [dai_minter])

        minter_nonce: int = web3.eth.get_transaction_count(Web3.to_checksum_address(dai_minter))
        for trader in traders:
            tx_hash = web3.eth.send_transaction(
                {
                    "from": dai_minter,
                    "to": dai_address,
                    "data": dai_contract.encodeABI(
                        fn_name="mint",
                        args=[Web3.to_checksum_address(trader.address), dai_amount_wei],
                    ),
                    "gas": 100000,
                    "gasPrice": Wei(gas_price),
                    "nonce": Nonce(minter_nonce),
                }
            )
            funding_ops.append((f"DAI mint for {trader.address[:10]}", tx_hash))
            minter_nonce += 1

        web3.provider.make_request(RPCEndpoint("anvil_stopImpersonatingAccount"), [dai_minter])

    # USDC: use the FiatToken masterMinter to configure itself as a minter, then
    # call mint() for each trader. This requires a separate evm_mine for the
    # configureMinter step before minting can proceed.
    if "USDC" in token_balances and token_balances["USDC"] > 0:
        usdc_address = Web3.to_checksum_address(TOKEN_ADDRESSES["USDC"])
        usdc_contract = web3.eth.contract(address=usdc_address, abi=_USDC_ABI)
        usdc_amount_wei = _token_amount_wei("USDC", token_balances["USDC"])

        master_minter = usdc_contract.functions.masterMinter().call()
        web3.provider.make_request(
            RPCEndpoint("anvil_setBalance"), [master_minter, hex(web3.to_wei(1, "ether"))]
        )
        web3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [master_minter])

        mm_nonce: int = web3.eth.get_transaction_count(Web3.to_checksum_address(master_minter))
        # Configure masterMinter itself as a minter with unlimited allowance.
        configure_hash = web3.eth.send_transaction(
            {
                "from": master_minter,
                "to": usdc_address,
                "data": usdc_contract.encodeABI(
                    fn_name="configureMinter",
                    args=[master_minter, 2**256 - 1],
                ),
                "gas": 100000,
                "gasPrice": Wei(gas_price),
                "nonce": Nonce(mm_nonce),
            }
        )
        mm_nonce += 1
        # Mine the configure tx before submitting mints — mints will fail if not a minter yet.
        web3.provider.make_request(RPCEndpoint("evm_mine"), [])
        configure_receipt = web3.eth.get_transaction_receipt(configure_hash)
        if configure_receipt is None or configure_receipt["status"] != 1:
            raise ValueError("USDC configureMinter failed — cannot mint USDC")

        for trader in traders:
            tx_hash = web3.eth.send_transaction(
                {
                    "from": master_minter,
                    "to": usdc_address,
                    "data": usdc_contract.encodeABI(
                        fn_name="mint",
                        args=[Web3.to_checksum_address(trader.address), usdc_amount_wei],
                    ),
                    "gas": 100000,
                    "gasPrice": Wei(gas_price),
                    "nonce": Nonce(mm_nonce),
                }
            )
            funding_ops.append((f"USDC mint for {trader.address[:10]}", tx_hash))
            mm_nonce += 1

        web3.provider.make_request(RPCEndpoint("anvil_stopImpersonatingAccount"), [master_minter])

    # Other tokens (USDT, GNO): impersonate a whale and transfer.
    # Multiple tokens may share the same whale, so nonces are tracked across the loop.
    whale_nonces: dict[str, int] = {}
    for token_symbol, amount in token_balances.items():
        if token_symbol in ("WETH", "DAI", "USDC") or amount <= 0:
            continue
        if token_symbol not in TOKEN_ADDRESSES:
            continue
        whale = _WHALE_ADDRESSES.get(token_symbol)
        if not whale:
            continue

        token_address = Web3.to_checksum_address(TOKEN_ADDRESSES[token_symbol])
        amount_wei = _token_amount_wei(token_symbol, amount)
        token_contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)

        if whale not in whale_nonces:
            web3.provider.make_request(
                RPCEndpoint("anvil_setBalance"), [whale, hex(web3.to_wei(1, "ether"))]
            )
            whale_nonces[whale] = web3.eth.get_transaction_count(Web3.to_checksum_address(whale))

        web3.provider.make_request(RPCEndpoint("anvil_impersonateAccount"), [whale])

        whale_nonce = whale_nonces[whale]
        for trader in traders:
            tx_hash = web3.eth.send_transaction(
                {
                    "from": whale,
                    "to": token_address,
                    "data": token_contract.encodeABI(
                        fn_name="transfer",
                        args=[Web3.to_checksum_address(trader.address), amount_wei],
                    ),
                    "gas": 100000,
                    "gasPrice": Wei(gas_price),
                    "nonce": Nonce(whale_nonce),
                }
            )
            funding_ops.append((f"{token_symbol} transfer for {trader.address[:10]}", tx_hash))
            whale_nonce += 1

        whale_nonces[whale] = whale_nonce
        web3.provider.make_request(RPCEndpoint("anvil_stopImpersonatingAccount"), [whale])

    # Step 3 — force-mine one block to include all funding transactions
    if funding_ops:
        web3.provider.make_request(RPCEndpoint("evm_mine"), [])
        for description, tx_hash in funding_ops:
            receipt = web3.eth.get_transaction_receipt(tx_hash)
            if receipt is None or receipt["status"] != 1:
                raise ValueError(f"Token funding failed — {description} (tx: {tx_hash.hex()})")

    # Step 4 — submit all approve transactions, then wait for all receipts in bulk.
    # Nonces are tracked manually per trader to avoid mempool collisions.
    approval_hashes: list[Any] = []
    for trader in traders:
        trader_account = trader.get_account()
        nonce: int = web3.eth.get_transaction_count(
            Web3.to_checksum_address(trader_account.address)
        )
        for token_symbol, amount in token_balances.items():
            if amount > 0:
                tx_hash = _submit_approve_transaction(
                    web3, trader_account, token_symbol, vault_relayer, amount * 10, nonce=nonce
                )
                approval_hashes.append(tx_hash)
                nonce += 1

    for tx_hash in approval_hashes:
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            raise ValueError(f"Approval transaction {tx_hash.hex()} failed")


def create_trader_pool_from_config(
    wallet_config: Any,  # WalletConfig type
    num_traders: int,
) -> TraderPool:
    """Create a trader pool based on wallet configuration.

    Args:
        wallet_config: Wallet configuration object
        num_traders: Number of traders needed (from orchestration config)

    Returns:
        TraderPool with the specified traders

    Raises:
        ValueError: If configuration is invalid
    """
    # If private keys are specified, use them
    if wallet_config.private_keys:
        if len(wallet_config.private_keys) < num_traders:
            raise ValueError(
                f"Not enough private keys provided: need {num_traders}, got {len(wallet_config.private_keys)}"
            )
        # Use first num_traders keys
        private_keys = wallet_config.private_keys[:num_traders]
        return TraderPool(num_traders=num_traders, private_keys=private_keys)

    # If generate_count is specified and > 0, generate that many
    if wallet_config.generate_count > 0:
        actual_count = min(wallet_config.generate_count, num_traders)
        return TraderPool(num_traders=actual_count)

    # Otherwise, use default generation
    return TraderPool(num_traders=num_traders)
