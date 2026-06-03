#!/bin/sh
# Driver entrypoint script with environment variable substitution in config

set -e

# Check if envsubst is available, install if not
if ! command -v envsubst >/dev/null 2>&1; then
    echo "Installing gettext for envsubst..."
    apk add --no-cache gettext
fi

# Substitute environment variables in the config template
echo "Processing driver config with environment variables..."
envsubst < /driver.toml.template > /driver.toml

# Start the driver with the processed config
exec /usr/local/bin/driver "$@"
