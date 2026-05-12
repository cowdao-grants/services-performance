# Wallet Funding

Automatic wallet funding for testing with Anvil (forked Ethereum node).

## Overview

The wallet funding system automatically funds test wallets with ETH and tokens using Anvil's JSON-RPC methods. This eliminates manual setup and enables fully automated testing.

## How It Works

### ETH Funding

ETH balances are set instantly using Anvil's `anvil_setBalance` RPC method:

```bash
# anvil_setBalance sets the balance of any address to a specified amount
# No transaction is required — the balance is updated directly in Anvil's state
```

### Token Funding

Tokens are funded by impersonating privileged accounts and calling token contracts directly:

- **WETH**: Each wallet is given extra ETH and then calls `deposit()` on the WETH9 contract to wrap it.
- **DAI**: Impersonates `MCD_JOIN_DAI` (an authorized DAI ward) and calls `mint()` directly.
- **USDC**: Impersonates the USDC `masterMinter`, configures itself as a minter, then calls `mint()` for each wallet.
- **USDT / GNO**: Impersonates a large token holder (whale) and calls `transfer()`.

All funding transactions are submitted in batch and mined in a single forced block via `evm_mine`.

### Token Approvals

Tokens are automatically approved for VaultRelayer contract:

```python
# Approve VaultRelayer to spend tokens
token.approve(VaultRelayer, amount)
```

## Configuration

**File**: `.cow-perf.yml` or scenario YAML

```yaml
wallet:
  funding_enabled: true  # Enable automatic funding
  eth_balance: 10.0      # ETH per wallet
  token_balances:        # Token amounts per wallet
    WETH: 10.0           # 10 WETH
    DAI: 10000.0         # 10,000 DAI
    USDC: 5000.0         # 5,000 USDC
```

## Supported Tokens

Default configuration supports:
- WETH (Wrapped Ether)
- DAI (Dai Stablecoin)
- USDC (USD Coin)
- USDT (Tether)
- GNO (Gnosis Token)

## Usage

### Enable Funding

```bash
# Via config file
cat > .cow-perf.yml <<EOF
wallet:
  funding_enabled: true
  eth_balance: 10.0
  token_balances:
    WETH: 10.0
    DAI: 10000.0
EOF

# Run test (replace with your actual scenario path)
cow-perf run --config configs/scenarios/predefined/enhanced/regression-test.yml
```

### Verify Funding

```bash
# Check logs for funding confirmation (replace with your actual scenario path)
cow-perf run --config configs/scenarios/predefined/enhanced/regression-test.yml --verbose

# Look for:
# "Funded wallet 0x... with 10.0 ETH"
# "Funded wallet 0x... with 10.0 WETH"
# "Approved WETH for VaultRelayer"
```

## Implementation

**Source Files:**
- Main logic: `src/cow_performance/cli/wallet_funding.py`
- Trader pool: `src/cow_performance/load_generation/trader_account.py`

**Key Functions:**
- `fund_wallet_with_eth()` - Set ETH balance via `anvil_setBalance`
- `fund_wallet_with_token()` - Fund a single wallet with tokens via impersonation
- `approve_token()` - Approve VaultRelayer to spend tokens
- `fund_trader_pool()` - Fund all traders in a pool with ETH, tokens, and approvals in bulk
- `create_trader_pool_from_config()` - Create a trader pool from wallet configuration

## Limitations

**Anvil Only**: Wallet funding only works with Anvil (local forked node). Does not work with:
- Real Ethereum mainnet
- Testnets (Goerli, Sepolia, etc.)
- Other local nodes (Ganache, Hardhat Network)

**Why**: Uses Anvil-specific RPC methods (`anvil_setBalance`, `anvil_impersonateAccount`, `evm_mine`)

## Troubleshooting

**"Wallet funding failed: connection refused"**
- Ensure Anvil is running: `docker compose ps chain`
- Check RPC URL: `http://localhost:8545`

**"Token balance not updated"**
- Check that Anvil is running in fork mode (impersonation requires forked state)
- Check token address matches mainnet fork
- Ensure the whale/minter account used still holds the expected balance on the forked block

**"Insufficient funds for trading"**
- Increase `eth_balance` for gas costs
- Increase token amounts in `token_balances`
- Check that tokens were approved for VaultRelayer

## See Also

- [CLI Reference](cli.md#wallet-configuration) - Wallet config options
- [Configuration Reference](configuration-reference.md) - Full schema
- [Development Guide](development.md#wallet-funding-integration-tests) - Testing wallet funding
