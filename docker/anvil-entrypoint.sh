#!/bin/sh
# Anvil entrypoint script with conditional fork block number

set -e

# Build the anvil command
ANVIL_CMD="/usr/local/bin/anvil \
  --fork-url ${ETH_RPC_URL} \
  --host 0.0.0.0 \
  --port 8545 \
  --chain-id 1 \
  --block-time 1 \
  --gas-limit 30000000 \
  --code-size-limit 50000 \
  --accounts 10 \
  --balance 10000 \
  --prune-history \
  --silent"

# Add fork-block-number if ETH_BLOCKNUMBER is set
if [ -n "${ETH_BLOCKNUMBER}" ]; then
  echo "Forking from block number: ${ETH_BLOCKNUMBER}"
  ANVIL_CMD="${ANVIL_CMD} --fork-block-number ${ETH_BLOCKNUMBER}"
else
  echo "Forking from latest block"
fi

# Execute anvil
exec $ANVIL_CMD
