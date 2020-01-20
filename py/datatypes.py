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
FEERATE = float  # in satoshi per byte

NodeIndex = int
NodeIndexStr = str


def msat_to_sat(msat: MSATOSHI) -> SATOSHI:
    return SATOSHI(msat / 1000)


def btc_to_sat(amount: BTC) -> SATOSHI:
    return SATOSHI(amount * (10 ** 8))
