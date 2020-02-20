from dataclasses import dataclass
from typing import Any, Dict, List

Json = Dict[str, Any]
Address = str
BlockHash = str
BlockHeight = int
Block = Json
BTC = float
FEERATE = float  # in satoshi per byte
MSATOSHI = int
NodeIndex = int
NodeIndexStr = str
SATOSHI = int
TIMESTAMP = int
TXID = str
TX = Json


@dataclass
class PlotData:
    """PlotData represents data for a single graph - feerate as a function of timestamp"""
    timestamps: List[TIMESTAMP]
    feerates: List[FEERATE]
    label: str


def msat_to_sat(msat: MSATOSHI) -> SATOSHI:
    return SATOSHI(msat / 1000)


def btc_to_sat(amount: BTC) -> SATOSHI:
    return SATOSHI(amount * (10 ** 8))


def sat_to_btc(amount: SATOSHI) -> BTC:
    return amount * (10 * -8)
