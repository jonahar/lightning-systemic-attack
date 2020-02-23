from typing import Any, Dict

Json = Dict[str, Any]
Address = str
BlockHash = str
BlockHeight = int
Block = Json
BTC = float
Feerate = float  # in satoshi per byte
MSatoshi = int
NodeIndex = int
NodeIndexStr = str
Satoshi = int
Timestamp = int
TXID = str
TX = Json


def msat_to_sat(msat: MSatoshi) -> Satoshi:
    return Satoshi(msat / 1000)


def btc_to_sat(amount: BTC) -> Satoshi:
    return Satoshi(amount * (10 ** 8))


def sat_to_btc(amount: Satoshi) -> BTC:
    return amount * (10 * -8)
