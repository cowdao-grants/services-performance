"""
Unit tests for trader account management.

Tests trader account creation, private key management, and trader pool functionality.
"""

import pytest
from eth_account import Account

from cow_performance.load_generation import TraderAccount, TraderPool


class TestTraderAccount:
    """Tests for TraderAccount class."""

    def test_generate_creates_valid_account(self):
        """Test that generate creates a valid trader account."""
        trader = TraderAccount.generate()

        assert trader.address is not None
        assert trader.private_key is not None
        assert trader.nonce == 0
        assert trader.orders_submitted == 0
        assert trader.address.startswith("0x")
        assert len(trader.address) == 42

    def test_from_private_key_creates_account(self):
        """Test creating account from private key."""
        # Create a known account
        account = Account.create()
        private_key = account.key.hex()

        trader = TraderAccount.from_private_key(private_key)

        assert trader.address == account.address
        assert trader.private_key == private_key

    def test_from_private_key_without_prefix(self):
        """Test creating account from private key without 0x prefix."""
        account = Account.create()
        private_key = account.key.hex().removeprefix("0x")

        trader = TraderAccount.from_private_key(private_key)

        assert trader.address == account.address
        assert trader.private_key.startswith("0x")

    def test_invalid_private_key_raises_error(self):
        """Test that invalid private key raises error."""
        with pytest.raises((ValueError, TypeError)):
            TraderAccount.from_private_key("invalid_key")

    def test_address_mismatch_raises_error(self):
        """Test that mismatched address and private key raises error."""
        account = Account.create()
        wrong_address = "0x0000000000000000000000000000000000000001"

        with pytest.raises(ValueError, match="Private key does not match address"):
            TraderAccount(
                address=wrong_address,
                private_key=account.key.hex(),
            )

    def test_increment_nonce(self):
        """Test nonce increment."""
        trader = TraderAccount.generate()
        assert trader.nonce == 0

        trader.increment_nonce()
        assert trader.nonce == 1

        trader.increment_nonce()
        assert trader.nonce == 2

    def test_increment_orders_submitted(self):
        """Test orders submitted increment."""
        trader = TraderAccount.generate()
        assert trader.orders_submitted == 0

        trader.increment_orders_submitted()
        assert trader.orders_submitted == 1

        trader.increment_orders_submitted()
        assert trader.orders_submitted == 2

    def test_get_account_returns_local_account(self):
        """Test that get_account returns valid LocalAccount."""
        trader = TraderAccount.generate()
        local_account = trader.get_account()

        assert local_account.address == trader.address
        assert local_account.key.hex() == trader.private_key


class TestTraderPool:
    """Tests for TraderPool class."""

    def test_init_generates_traders(self):
        """Test that initialization generates specified number of traders."""
        pool = TraderPool(num_traders=5)

        assert pool.get_pool_size() == 5
        assert len(pool.get_all_traders()) == 5

    def test_init_with_private_keys(self):
        """Test initialization with provided private keys."""
        accounts = [Account.create() for _ in range(3)]
        private_keys = [acc.key.hex() for acc in accounts]

        pool = TraderPool(num_traders=3, private_keys=private_keys)

        assert pool.get_pool_size() == 3
        for i, account in enumerate(accounts):
            trader = pool.get_trader(i)
            assert trader.address == account.address

    def test_mismatched_num_traders_and_keys_raises_error(self):
        """Test that mismatched num_traders and private_keys raises error."""
        private_keys = [Account.create().key.hex() for _ in range(3)]

        with pytest.raises(ValueError, match="does not match"):
            TraderPool(num_traders=5, private_keys=private_keys)

    def test_get_trader_by_index(self):
        """Test getting trader by index."""
        pool = TraderPool(num_traders=3)

        trader0 = pool.get_trader(0)
        trader1 = pool.get_trader(1)
        trader2 = pool.get_trader(2)

        assert trader0 is not None
        assert trader1 is not None
        assert trader2 is not None
        assert trader0.address != trader1.address
        assert trader1.address != trader2.address

    def test_get_trader_out_of_range_raises_error(self):
        """Test that out of range index raises error."""
        pool = TraderPool(num_traders=3)

        with pytest.raises(IndexError):
            pool.get_trader(5)

    def test_get_random_trader(self):
        """Test getting random trader."""
        pool = TraderPool(num_traders=10)

        trader = pool.get_random_trader()
        assert trader is not None
        assert trader in pool.get_all_traders()

    def test_get_next_trader_rotates(self):
        """Test that get_next_trader rotates through traders."""
        pool = TraderPool(num_traders=3)

        trader0 = pool.get_next_trader()
        trader1 = pool.get_next_trader()
        trader2 = pool.get_next_trader()
        trader3 = pool.get_next_trader()  # Should wrap back to first

        assert trader0 == pool.get_trader(0)
        assert trader1 == pool.get_trader(1)
        assert trader2 == pool.get_trader(2)
        assert trader3 == pool.get_trader(0)  # Wrapped around

    def test_get_all_traders(self):
        """Test getting all traders."""
        pool = TraderPool(num_traders=5)

        all_traders = pool.get_all_traders()
        assert len(all_traders) == 5
        assert all(isinstance(t, TraderAccount) for t in all_traders)

    def test_get_total_orders_submitted(self):
        """Test getting total orders submitted across all traders."""
        pool = TraderPool(num_traders=3)

        assert pool.get_total_orders_submitted() == 0

        pool.get_trader(0).increment_orders_submitted()
        pool.get_trader(0).increment_orders_submitted()
        pool.get_trader(1).increment_orders_submitted()

        assert pool.get_total_orders_submitted() == 3

    def test_deterministic_seed_generation(self):
        """Test deterministic trader generation with seed."""
        TraderPool.set_deterministic_seed(12345)

        pool1 = TraderPool(num_traders=3)
        pool2 = TraderPool(num_traders=3)

        # Same seed should produce same addresses
        for i in range(3):
            assert pool1.get_trader(i).address == pool2.get_trader(i).address

        # Clean up
        TraderPool.set_deterministic_seed(None)

    def test_random_generation_produces_different_addresses(self):
        """Test that random generation produces different addresses."""
        TraderPool.set_deterministic_seed(None)

        pool1 = TraderPool(num_traders=3)
        pool2 = TraderPool(num_traders=3)

        # Different pools should have different addresses
        addresses1 = {pool1.get_trader(i).address for i in range(3)}
        addresses2 = {pool2.get_trader(i).address for i in range(3)}

        # Very unlikely to collide
        assert addresses1 != addresses2
