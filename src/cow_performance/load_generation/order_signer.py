"""
Order signing utilities for CoW Protocol orders.

This module provides signing functionality for standard orders (EIP-712).
"""

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_account.signers.local import LocalAccount
from web3 import Web3

from .order_schema import (
    OrderParameters,
    SignedOrder,
    SigningScheme,
    get_order_domain,
    get_order_types,
)


class OrderSigner:
    """
    Handles signing of CoW Protocol orders using EIP-712.

    This class manages the domain configuration and signing process for
    standard CoW Protocol orders (market and limit orders).
    """

    def __init__(self, chain_id: int, settlement_contract: str):
        """
        Initialize the order signer with EIP-712 domain parameters.

        Args:
            chain_id: The chain ID (1 for mainnet, 100 for Gnosis Chain, etc.)
            settlement_contract: Address of the CoW Protocol settlement contract
        """
        self.chain_id = chain_id
        self.settlement_contract = Web3.to_checksum_address(settlement_contract)
        self.domain = get_order_domain(chain_id, settlement_contract)
        self.types = get_order_types()

    def sign_order(
        self,
        order_params: OrderParameters,
        trader_account: LocalAccount,
    ) -> SignedOrder:
        """
        Sign a standard order (market or limit) using EIP-712.

        Args:
            order_params: The order parameters to sign
            trader_account: The LocalAccount to sign with

        Returns:
            A SignedOrder with signature included
        """
        # Create the message to sign
        # Handle both enum and string values
        kind_value = (
            order_params.kind.value if hasattr(order_params.kind, "value") else order_params.kind
        )
        sell_balance_value = (
            order_params.sellTokenBalance.value
            if hasattr(order_params.sellTokenBalance, "value")
            else order_params.sellTokenBalance
        )
        buy_balance_value = (
            order_params.buyTokenBalance.value
            if hasattr(order_params.buyTokenBalance, "value")
            else order_params.buyTokenBalance
        )

        message = {
            "sellToken": order_params.sellToken,
            "buyToken": order_params.buyToken,
            "receiver": order_params.receiver or "0x0000000000000000000000000000000000000000",
            "sellAmount": int(order_params.sellAmount),
            "buyAmount": int(order_params.buyAmount),
            "validTo": order_params.validTo,
            "appData": order_params.appData,
            "feeAmount": int(order_params.feeAmount),
            "kind": kind_value,
            "partiallyFillable": order_params.partiallyFillable,
            "sellTokenBalance": sell_balance_value,
            "buyTokenBalance": buy_balance_value,
        }

        # Create typed data structure
        typed_data = {
            "types": {
                **self.types,
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
            },
            "primaryType": "Order",
            "domain": self.domain,
            "message": message,
        }

        # Sign the typed data
        encoded_data = encode_typed_data(full_message=typed_data)
        signed_message = trader_account.sign_message(encoded_data)  # type: ignore[no-untyped-call]

        # Create SignedOrder
        return SignedOrder(  # type: ignore[call-arg]
            sellToken=order_params.sellToken,
            buyToken=order_params.buyToken,
            sellAmount=order_params.sellAmount,
            buyAmount=order_params.buyAmount,
            validTo=order_params.validTo,
            appData=order_params.appData,
            feeAmount=order_params.feeAmount,
            kind=order_params.kind,
            partiallyFillable=order_params.partiallyFillable,
            sellTokenBalance=order_params.sellTokenBalance,
            buyTokenBalance=order_params.buyTokenBalance,
            receiver=order_params.receiver,
            from_=trader_account.address,
            signingScheme=SigningScheme.EIP712,
            signature=signed_message.signature.hex(),
        )

    def verify_signature(
        self,
        signed_order: SignedOrder,
    ) -> bool:
        """
        Verify that an order signature is valid.

        Args:
            signed_order: The signed order to verify

        Returns:
            True if signature is valid, False otherwise
        """
        # Recreate the typed data
        kind_value = (
            signed_order.kind.value if hasattr(signed_order.kind, "value") else signed_order.kind
        )
        sell_balance_value = (
            signed_order.sellTokenBalance.value
            if hasattr(signed_order.sellTokenBalance, "value")
            else signed_order.sellTokenBalance
        )
        buy_balance_value = (
            signed_order.buyTokenBalance.value
            if hasattr(signed_order.buyTokenBalance, "value")
            else signed_order.buyTokenBalance
        )

        message = {
            "sellToken": signed_order.sellToken,
            "buyToken": signed_order.buyToken,
            "receiver": signed_order.receiver or "0x0000000000000000000000000000000000000000",
            "sellAmount": int(signed_order.sellAmount),
            "buyAmount": int(signed_order.buyAmount),
            "validTo": signed_order.validTo,
            "appData": signed_order.appData,
            "feeAmount": int(signed_order.feeAmount),
            "kind": kind_value,
            "partiallyFillable": signed_order.partiallyFillable,
            "sellTokenBalance": sell_balance_value,
            "buyTokenBalance": buy_balance_value,
        }

        # Create typed data structure
        typed_data = {
            "types": {
                **self.types,
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
            },
            "primaryType": "Order",
            "domain": self.domain,
            "message": message,
        }

        # Encode the typed data
        encoded_data = encode_typed_data(full_message=typed_data)

        # Recover the signer address from the signature
        signature_bytes = bytes.fromhex(signed_order.signature.removeprefix("0x"))
        recovered_address = Account.recover_message(
            encoded_data,
            signature=signature_bytes,
        )

        # Verify the recovered address matches the order owner
        return bool(recovered_address.lower() == signed_order.from_.lower())


def sign_order_cancellations(
    order_uids: list[str],
    trader_account: LocalAccount,
    chain_id: int,
    settlement_contract: str,
) -> str:
    """Sign order cancellations using EIP-712.

    Args:
        order_uids: List of order UIDs to cancel
        trader_account: Trader's account for signing
        chain_id: Network chain ID
        settlement_contract: Settlement contract address

    Returns:
        Signature as hex string (with 0x prefix)
    """
    # EIP-712 domain
    domain = {
        "name": "Gnosis Protocol",
        "version": "v2",
        "chainId": chain_id,
        "verifyingContract": Web3.to_checksum_address(settlement_contract),
    }

    # EIP-712 message types
    message_types = {
        "OrderCancellations": [
            {"name": "orderUids", "type": "bytes[]"},
        ]
    }

    # Convert order UIDs to bytes
    order_uid_bytes = [
        bytes.fromhex(uid[2:] if uid.startswith("0x") else uid) for uid in order_uids
    ]

    # Message data
    message_data = {
        "orderUids": order_uid_bytes,
    }

    # Sign using EIP-712
    signable_message = encode_typed_data(
        domain_data=domain,
        message_types=message_types,
        message_data=message_data,
    )

    signed_message = Account.sign_message(
        signable_message,
        private_key=trader_account.key,
    )

    return str("0x" + signed_message.signature.hex())
