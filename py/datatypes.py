from typing import Any, Dict, TypeVar

Json = TypeVar("Json", bound=Dict[str, Any])
TXID = TypeVar("TXID", bound=str)
Address = TypeVar("Address", bound=str)
Block = TypeVar("Block", bound=Json)
