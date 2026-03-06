"""
Trader account management for simulating multiple concurrent users.

This module provides classes for managing trader accounts with private key generation,
account metadata tracking, and pool management for concurrent trading simulations.
Supports both EOA (Externally Owned Accounts) and Safe wallets for conditional orders.
"""

import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from eth_account import Account
from eth_account.signers.local import LocalAccount

if TYPE_CHECKING:
    from .safe_wallet import SafeWallet


@dataclass
class TraderAccount:
    """
    Represents a single trader account with private key management.

    This class manages trader-specific data including address, private key,
    and metadata such as nonce and order submission count.

    Supports both EOA (Externally Owned Accounts) and Safe wallets.
    When a Safe wallet is attached, the account can submit conditional orders
    (TWAP, Stop-Loss) that require EIP-1271 signatures.
    """

    address: str
    private_key: str
    nonce: int = 0
    orders_submitted: int = 0
    safe_wallet: "SafeWallet | None" = None
    _account: LocalAccount = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the LocalAccount from private key."""
        # Create LocalAccount from private key for signing operations
        self._account = Account.from_key(self.private_key)
        # Validate address matches private key
        if self._account.address != self.address:
            raise ValueError(
                f"Private key does not match address. "
                f"Expected: {self.address}, Got: {self._account.address}"
            )

    @classmethod
    def generate(cls) -> "TraderAccount":
        """
        Generate a new trader account with a random private key.

        Returns:
            A new TraderAccount instance with a randomly generated key
        """
        account = Account.create()
        return cls(
            address=account.address,
            private_key=account.key.hex(),
        )

    @classmethod
    def from_private_key(cls, private_key: str) -> "TraderAccount":
        """
        Create a trader account from an existing private key.

        Args:
            private_key: The private key as hex string (with or without 0x prefix)

        Returns:
            A new TraderAccount instance
        """
        # Ensure private key has 0x prefix
        if not private_key.startswith("0x"):
            private_key = f"0x{private_key}"

        account = Account.from_key(private_key)
        return cls(
            address=account.address,
            private_key=private_key,
        )

    def increment_nonce(self) -> None:
        """Increment the account nonce."""
        self.nonce += 1

    def increment_orders_submitted(self) -> None:
        """Increment the count of submitted orders."""
        self.orders_submitted += 1

    def get_account(self) -> LocalAccount:
        """
        Get the underlying eth_account LocalAccount for signing operations.

        Returns:
            The LocalAccount instance
        """
        return self._account

    def has_safe_wallet(self) -> bool:
        """
        Check if this account has a Safe wallet attached.

        Returns:
            True if Safe wallet is attached, False otherwise
        """
        return self.safe_wallet is not None

    def get_safe_address(self) -> str:
        """
        Get the Safe wallet address.

        Returns:
            Safe wallet address

        Raises:
            ValueError: If no Safe wallet is attached
        """
        if not self.safe_wallet:
            raise ValueError("No Safe wallet attached to this account")
        return self.safe_wallet.address

    def get_trading_address(self) -> str:
        """
        Get the address to use for trading.

        Returns Safe address if available, otherwise returns EOA address.

        Returns:
            Trading address (Safe or EOA)
        """
        if self.safe_wallet:
            return self.safe_wallet.address
        return self.address


class TraderPool:
    """
    Manages a pool of trader accounts for concurrent trading simulations.

    This class provides account rotation strategies and random trader selection
    for distributing load across multiple accounts.
    """

    # Class variable for deterministic key generation in tests
    _deterministic_seed: ClassVar[int | None] = None

    def __init__(self, num_traders: int = 10, private_keys: list[str] | None = None):
        """
        Initialize trader pool with generated or provided accounts.

        Args:
            num_traders: Number of trader accounts to generate (if private_keys not provided)
            private_keys: Optional list of private keys to use instead of generating new ones

        Raises:
            ValueError: If both num_traders and private_keys are provided with mismatched counts
        """
        if private_keys:
            if num_traders != len(private_keys):
                raise ValueError(
                    f"num_traders ({num_traders}) does not match "
                    f"private_keys length ({len(private_keys)})"
                )
            self.traders = [TraderAccount.from_private_key(pk) for pk in private_keys]
        else:
            self.traders = [self._generate_trader(i) for i in range(num_traders)]

        self._current_index = 0

    def _generate_trader(self, index: int) -> TraderAccount:
        """
        Generate a trader account, optionally using deterministic generation for tests.

        Args:
            index: The trader index (used for deterministic generation)

        Returns:
            A new TraderAccount
        """
        if self._deterministic_seed is not None:
            # Deterministic generation for reproducible tests
            seed = self._deterministic_seed + index
            private_key_int = int.from_bytes(seed.to_bytes(32, "big"), byteorder="big") % (2**256)
            private_key = f"0x{private_key_int:064x}"
            return TraderAccount.from_private_key(private_key)
        else:
            # Random generation for normal use
            return TraderAccount.generate()

    @classmethod
    def set_deterministic_seed(cls, seed: int | None) -> None:
        """
        Set a deterministic seed for reproducible trader generation in tests.

        Args:
            seed: The seed value, or None to use random generation
        """
        cls._deterministic_seed = seed

    def get_trader(self, index: int) -> TraderAccount:
        """
        Get trader by index.

        Args:
            index: The trader index

        Returns:
            The TraderAccount at the specified index

        Raises:
            IndexError: If index is out of range
        """
        return self.traders[index]

    def get_random_trader(self) -> TraderAccount:
        """
        Get a random trader from the pool.

        Returns:
            A randomly selected TraderAccount
        """
        index = secrets.randbelow(len(self.traders))
        return self.traders[index]

    def get_next_trader(self) -> TraderAccount:
        """
        Get the next trader using round-robin rotation.

        Returns:
            The next TraderAccount in rotation
        """
        trader = self.traders[self._current_index]
        self._current_index = (self._current_index + 1) % len(self.traders)
        return trader

    def get_all_traders(self) -> list[TraderAccount]:
        """
        Get all traders in the pool.

        Returns:
            List of all TraderAccount instances
        """
        return self.traders.copy()

    def get_pool_size(self) -> int:
        """
        Get the number of traders in the pool.

        Returns:
            The number of traders
        """
        return len(self.traders)

    def get_total_orders_submitted(self) -> int:
        """
        Get the total number of orders submitted by all traders.

        Returns:
            Sum of orders_submitted across all traders
        """
        return sum(trader.orders_submitted for trader in self.traders)
