from typing import Any, Dict

Json = Dict[str, Any]
TXID = str
TX = Json
Address = str
BlockHash = str
Block = Json
BlockHeight = int
BTC = float
SATOSHI = int
MSATOSHI = int


def btc_to_satoshi(amount: BTC) -> SATOSHI:
    return SATOSHI(amount * (10 ** 8))
