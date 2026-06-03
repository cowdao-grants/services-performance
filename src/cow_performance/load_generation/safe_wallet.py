"""
Safe wallet deployment and management for CoW Protocol conditional orders.

This module provides Safe wallet deployment and EIP-1271 signature generation,
enabling conditional orders (TWAP, Stop-Loss) that require Safe wallet owners.
"""

import secrets
from dataclasses import dataclass
from typing import cast

from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract
from web3.types import HexStr

# Safe contract addresses on Ethereum mainnet
# These are the official Safe contracts that exist on mainnet and our fork
SAFE_SINGLETON_ADDRESS = "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"
SAFE_PROXY_FACTORY_ADDRESS = "0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2"
SAFE_FALLBACK_HANDLER_ADDRESS = "0xf48f2B2d2a534e402487b3ee7C18c33Aec0Fe5e4"

# Safe contract ABIs (minimal, just what we need)
SAFE_PROXY_FACTORY_ABI = [
    {
        "inputs": [
            {"name": "singleton", "type": "address"},
            {"name": "initializer", "type": "bytes"},
            {"name": "saltNonce", "type": "uint256"},
        ],
        "name": "createProxyWithNonce",
        "outputs": [{"name": "proxy", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

SAFE_ABI = [
    {
        "inputs": [
            {"name": "_owners", "type": "address[]"},
            {"name": "_threshold", "type": "uint256"},
            {"name": "to", "type": "address"},
            {"name": "data", "type": "bytes"},
            {"name": "fallbackHandler", "type": "address"},
            {"name": "paymentToken", "type": "address"},
            {"name": "payment", "type": "uint256"},
            {"name": "paymentReceiver", "type": "address"},
        ],
        "name": "setup",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "nonce",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "operation", "type": "uint8"},
            {"name": "safeTxGas", "type": "uint256"},
            {"name": "baseGas", "type": "uint256"},
            {"name": "gasPrice", "type": "uint256"},
            {"name": "gasToken", "type": "address"},
            {"name": "refundReceiver", "type": "address"},
            {"name": "signatures", "type": "bytes"},
        ],
        "name": "execTransaction",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "domainSeparator",
        "outputs": [{"name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "_dataHash", "type": "bytes32"},
            {"name": "_signature", "type": "bytes"},
        ],
        "name": "isValidSignature",
        "outputs": [{"name": "", "type": "bytes4"}],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass
class SafeWallet:
    """
    Represents a deployed Safe wallet.

    Attributes:
        address: Safe wallet address
        owner: Owner account (EOA that controls the Safe)
        web3: Web3 instance for blockchain interaction
        contract: Safe contract instance
        chain_id: Chain ID
    """

    address: str
    owner: LocalAccount
    web3: Web3
    contract: Contract
    chain_id: int

    @classmethod
    def deploy(cls, web3: Web3, owner: LocalAccount, chain_id: int | None = None) -> "SafeWallet":
        """
        Deploy a new Safe wallet with a single owner.

        Args:
            web3: Web3 instance
            owner: Owner account (EOA that will control the Safe)
            chain_id: Chain ID (auto-detected if not provided)

        Returns:
            Deployed Safe wallet instance
        """
        if chain_id is None:
            chain_id = web3.eth.chain_id

        # Get factory contract
        factory = web3.eth.contract(
            address=Web3.to_checksum_address(SAFE_PROXY_FACTORY_ADDRESS),
            abi=SAFE_PROXY_FACTORY_ABI,
        )

        # Prepare Safe setup data
        # This initializes the Safe with the owner
        safe_singleton = web3.eth.contract(
            address=Web3.to_checksum_address(SAFE_SINGLETON_ADDRESS), abi=SAFE_ABI
        )

        setup_data = safe_singleton.encodeABI(
            fn_name="setup",
            args=[
                [owner.address],  # owners (single owner)
                1,  # threshold (1 signature required)
                Web3.to_checksum_address("0x" + "00" * 20),  # to (no delegate call)
                b"",  # data (no delegate call)
                Web3.to_checksum_address(SAFE_FALLBACK_HANDLER_ADDRESS),  # fallback handler
                Web3.to_checksum_address("0x" + "00" * 20),  # payment token (none)
                0,  # payment (0)
                Web3.to_checksum_address("0x" + "00" * 20),  # payment receiver (none)
            ],
        )

        # Generate random salt for unique address
        salt_nonce = secrets.randbelow(2**256)

        # Deploy Safe proxy
        tx = factory.functions.createProxyWithNonce(
            Web3.to_checksum_address(SAFE_SINGLETON_ADDRESS), setup_data, salt_nonce
        ).build_transaction(
            {
                "from": owner.address,
                "nonce": web3.eth.get_transaction_count(owner.address),
                "gas": 3000000,
                "gasPrice": web3.eth.gas_price,
            }
        )

        # Sign and send transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key=owner.key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        # Get Safe address from logs
        # The factory emits a ProxyCreation event with the Safe address
        # ProxyCreation(address proxy, address singleton)
        safe_address = None
        proxy_creation_topic = Web3.keccak(text="ProxyCreation(address,address)")

        for log in receipt["logs"]:
            if len(log["topics"]) > 0 and log["topics"][0] == proxy_creation_topic:
                # The proxy address is encoded in the data field, not topics
                # Extract first 32 bytes of data as the proxy address
                if log["data"]:
                    # data is already HexBytes, convert to bytes directly
                    data_bytes = bytes(log["data"])
                    if len(data_bytes) >= 32:
                        # First 32 bytes contain the proxy address (padded)
                        address_bytes = data_bytes[12:32]  # Take last 20 bytes of first 32
                        safe_address = Web3.to_checksum_address("0x" + address_bytes.hex())
                        break

        if not safe_address:
            # Fallback: compute the address deterministically
            # For ProxyFactory v1.3.0+, we can compute the proxy address
            # This is more reliable than parsing logs
            raise RuntimeError(
                "Failed to get Safe address from deployment logs. "
                "Check that Safe Proxy Factory is deployed and compatible."
            )

        # Create contract instance
        safe_contract = web3.eth.contract(address=safe_address, abi=SAFE_ABI)

        return cls(
            address=safe_address,
            owner=owner,
            web3=web3,
            contract=safe_contract,
            chain_id=chain_id,
        )

    def get_nonce(self) -> int:
        """Get the current Safe nonce."""
        return int(self.contract.functions.nonce().call())

    def exec_transaction(self, to: str, value: int, data: bytes | str, operation: int = 0) -> bytes:
        """
        Execute a transaction from the Safe wallet.

        Args:
            to: Target address
            value: ETH value to send
            data: Call data (bytes or hex string)
            operation: Operation type (0=call, 1=delegatecall)

        Returns:
            Transaction hash
        """
        # Convert data to bytes if it's a hex string
        if isinstance(data, str):
            data = Web3.to_bytes(hexstr=cast(HexStr, data))

        nonce = self.get_nonce()

        # Build transaction hash for signing
        # SafeTx struct hash from Safe contracts
        safe_tx_type_hash = Web3.keccak(
            text="SafeTx(address to,uint256 value,bytes data,uint8 operation,"
            "uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,"
            "address refundReceiver,uint256 nonce)"
        )

        safe_tx_hash = Web3.keccak(
            b"".join(
                [
                    safe_tx_type_hash,
                    Web3.to_bytes(hexstr=cast(HexStr, to)).rjust(32, b"\x00"),
                    value.to_bytes(32, byteorder="big"),
                    Web3.keccak(data),
                    operation.to_bytes(32, byteorder="big"),
                    (0).to_bytes(32, byteorder="big"),  # safeTxGas
                    (0).to_bytes(32, byteorder="big"),  # baseGas
                    (0).to_bytes(32, byteorder="big"),  # gasPrice
                    Web3.to_bytes(hexstr=cast(HexStr, "0x" + "00" * 20)).rjust(
                        32, b"\x00"
                    ),  # gasToken
                    Web3.to_bytes(hexstr=cast(HexStr, "0x" + "00" * 20)).rjust(
                        32, b"\x00"
                    ),  # refundReceiver
                    nonce.to_bytes(32, byteorder="big"),
                ]
            )
        )

        # Get domain separator
        domain_separator = self.contract.functions.domainSeparator().call()

        # Create EIP-191 message
        message_hash = Web3.keccak(
            b"".join(
                [
                    b"\x19\x01",
                    domain_separator,
                    safe_tx_hash,
                ]
            )
        )

        # Sign with owner
        signature = self.owner.signHash(message_hash)  # type: ignore[no-untyped-call]

        # Format signature for Safe (v, r, s)
        # Safe expects: r (32) + s (32) + v (1)
        r = signature.r.to_bytes(32, byteorder="big")
        s = signature.s.to_bytes(32, byteorder="big")
        v = signature.v.to_bytes(1, byteorder="big")
        signatures = r + s + v

        # Execute transaction
        tx = self.contract.functions.execTransaction(
            Web3.to_checksum_address(to),
            value,
            data,
            operation,
            0,  # safeTxGas
            0,  # baseGas
            0,  # gasPrice
            Web3.to_checksum_address("0x" + "00" * 20),  # gasToken
            Web3.to_checksum_address("0x" + "00" * 20),  # refundReceiver
            signatures,
        ).build_transaction(
            {
                "from": self.owner.address,
                "nonce": self.web3.eth.get_transaction_count(self.owner.address),
                "gas": 500000,
                "gasPrice": self.web3.eth.gas_price,
            }
        )

        # Sign and send
        signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=self.owner.key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        self.web3.eth.wait_for_transaction_receipt(tx_hash)

        return tx_hash

    def sign_message(self, message_hash: bytes) -> bytes:
        """
        Create EIP-1271 signature for a message.

        Args:
            message_hash: 32-byte message hash to sign

        Returns:
            EIP-1271 signature bytes
        """
        # SafeMessage struct hash from Safe contracts
        safe_message_type_hash = Web3.keccak(text="SafeMessage(bytes message)")

        safe_message_hash = Web3.keccak(
            b"".join([safe_message_type_hash, Web3.keccak(message_hash)])
        )

        # Get domain separator
        domain_separator = self.contract.functions.domainSeparator().call()

        # Create EIP-191 message
        final_hash = Web3.keccak(b"".join([b"\x19\x01", domain_separator, safe_message_hash]))

        # Sign with owner
        signature = self.owner.signHash(final_hash)  # type: ignore[no-untyped-call]

        # Format signature for Safe (v, r, s)
        r = signature.r.to_bytes(32, byteorder="big")
        s = signature.s.to_bytes(32, byteorder="big")
        v = signature.v.to_bytes(1, byteorder="big")

        return bytes(r + s + v)

    def approve_token(self, token_address: str, spender: str, amount: int) -> bytes:
        """
        Approve a spender to use tokens from the Safe.

        Args:
            token_address: Token contract address
            spender: Spender address
            amount: Amount to approve

        Returns:
            Transaction hash
        """
        # ERC20 approve function selector
        approve_selector = Web3.keccak(text="approve(address,uint256)")[:4]

        # Encode parameters
        approve_data = (
            approve_selector
            + Web3.to_bytes(hexstr=cast(HexStr, spender)).rjust(32, b"\x00")
            + amount.to_bytes(32, byteorder="big")
        )

        return self.exec_transaction(
            to=token_address,
            value=0,
            data=approve_data,
            operation=0,  # CALL
        )


def deploy_safe_wallet(web3: Web3, owner: LocalAccount) -> SafeWallet:
    """
    Deploy a Safe wallet for a trader account.

    This is a convenience function for deploying Safe wallets
    in user simulation scenarios.

    Args:
        web3: Web3 instance
        owner: Owner account (EOA that will control the Safe)

    Returns:
        Deployed Safe wallet
    """
    return SafeWallet.deploy(web3, owner)
