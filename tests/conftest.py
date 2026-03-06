"""Shared test fixtures for the CoW Performance Testing Suite."""

import pytest


@pytest.fixture
def sample_trader_address() -> str:
    """Return a sample Ethereum address for testing."""
    return "0x0000000000000000000000000000000000000001"


@pytest.fixture
def sample_token_addresses() -> dict[str, str]:
    """Return sample token addresses for testing."""
    return {
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    }
