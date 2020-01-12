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

NodeIndex = int
NodeIndexStr = str


def msat_to_sat(msat: MSATOSHI) -> SATOSHI:
    return int(msat / 1000)
