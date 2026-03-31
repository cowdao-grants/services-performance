# Wallet Funding

Automatic wallet funding for testing with Anvil (forked Ethereum node).

## Overview

The wallet funding system automatically funds test wallets with ETH and tokens using Anvil's JSON-RPC methods. This eliminates manual setup and enables fully automated testing.

## How It Works

### ETH Funding

ETH is transferred from Anvil's default account (funded with 10,000 ETH):

```bash
# Anvil provides default account: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
# Balance: 10,000 ETH
```

### Token Funding

Tokens are added by manipulating storage slots:

1. **Find Token Balance Slot**: Each ERC-20 token stores balances at a specific storage slot (varies by token)
2. **Calculate Wallet Slot**: `keccak256(wallet_address, balance_slot)`
3. **Set Balance**: Use `anvil_setStorageAt` RPC method to set balance

**Example** (WETH at 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2):
```python
# WETH balance slot: 3
wallet_slot = keccak256(wallet_address, 3)
anvil_setStorageAt(WETH_address, wallet_slot, encoded_balance)
```

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
- WBTC (Wrapped Bitcoin)
- COW (CoW Protocol Token)

**Storage Slots** (Ethereum Mainnet):
- WETH: slot 3
- DAI: slot 2
- USDC: slot 9
- USDT: slot 2
- WBTC: slot 0
- COW: slot 5

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
- Main logic: `src/cow_performance/cli/commands/wallet_funding.py`
- Trader pool: `src/cow_performance/load_generation/trader_pool.py`
- Configuration: `src/cow_performance/config.py` (WalletConfig)

**Key Functions:**
- `fund_wallet_eth()` - Transfer ETH from Anvil default account
- `fund_wallet_token()` - Manipulate storage slot for token balance
- `approve_token_for_trading()` - Approve VaultRelayer
- `create_trader_pool_from_config()` - Create and fund trader pool

## Limitations

**Anvil Only**: Wallet funding only works with Anvil (local forked node). Does not work with:
- Real Ethereum mainnet
- Testnets (Goerli, Sepolia, etc.)
- Other local nodes (Ganache, Hardhat Network)

**Why**: Uses Anvil-specific RPC methods (`anvil_setStorageAt`, `anvil_setBalance`)

## Troubleshooting

**"Wallet funding failed: connection refused"**
- Ensure Anvil is running: `docker compose ps chain`
- Check RPC URL: `http://localhost:8545`

**"Token balance not updated"**
- Verify storage slot for token (may vary by deployment)
- Check token address matches mainnet fork
- Ensure Anvil is in fork mode

**"Insufficient funds for trading"**
- Increase `eth_balance` for gas costs
- Increase token amounts in `token_balances`
- Check that tokens were approved for VaultRelayer

## See Also

- [CLI Reference](cli.md#wallet-configuration) - Wallet config options
- [Configuration Reference](configuration-reference.md) - Full schema
- [Development Guide](development.md#wallet-funding-integration-tests) - Testing wallet funding
