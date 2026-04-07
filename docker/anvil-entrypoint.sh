#!/bin/sh
# Anvil entrypoint script with conditional fork block number

set -e

# Build the anvil command
ANVIL_CMD="/usr/local/bin/anvil \
  --fork-url ${ETH_RPC_URL} \
  --host 0.0.0.0 \
  --port 8545 \
  --chain-id 1 \
  --block-time 10 \
  --gas-limit 30000000 \
  --block-base-fee-per-gas 0 \
  --code-size-limit 50000 \
  --accounts 10 \
  --balance 10000 \
  --silent"

# Add fork-block-number if ETH_BLOCKNUMBER is set
if [ -n "${ETH_BLOCKNUMBER}" ]; then
  echo "Forking from block number: ${ETH_BLOCKNUMBER}"
  ANVIL_CMD="${ANVIL_CMD} --fork-block-number ${ETH_BLOCKNUMBER}"
else
  echo "Forking from latest block"
fi

# Start anvil in background
$ANVIL_CMD &
ANVIL_PID=$!

# Wait for anvil to be ready
echo "Waiting for Anvil to start..."
for i in $(seq 1 30); do
  if /usr/local/bin/cast block-number --rpc-url http://127.0.0.1:8545 >/dev/null 2>&1; then
    echo "Anvil is ready"
    break
  fi
  sleep 1
done

# Wait for anvil process
wait $ANVIL_PID
