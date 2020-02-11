from functools import lru_cache
from typing import List

import plyvel

from bitcoin_cli import blockchain_height, get_block_by_height, get_transaction, set_bitcoin_cli
from datatypes import Block, BlockHeight, FEERATE, TIMESTAMP, TXID
from feerates.feerates_logger import logger
from feerates.oracle_factory import get_f_values_db, get_multi_layer_oracle
from utils import timeit

"""
This module is responsible for computing the F function. this is defined as
  F(t,n,p) = min{ feerate(tx) | M <= height(tx) < M+n, tx ∈ G(height(tx), p) }

Where M is the first block height that came after time t
and G(b,p) is the set of the p top paying transactions in block height b
"""

feerate_oracle = get_multi_layer_oracle()
f_values_db: plyvel.DB = get_f_values_db()

set_bitcoin_cli("user")


@lru_cache(maxsize=2048)
def get_block_time(h: BlockHeight) -> TIMESTAMP:
    return get_block_by_height(h)["time"]


@timeit(logger=logger, print_args=True)
def get_first_block_after_time_t(t: TIMESTAMP) -> BlockHeight:
    """
    return the height of the first block with timestamp greater or equal to
    the given timestamp
    """
    low: int = 0
    high = blockchain_height()
    
    # simple binary search
    while low < high:
        m = (low + high) // 2
        m_time = get_block_time(m)
        if m_time < t:
            low = m + 1
        else:
            high = m
    
    return low


def remove_coinbase_txid(txids: List[TXID]) -> List[TXID]:
    """
    remove the txid of a coinbase transaction from the given list and return the
    modified list.
    this function assumes there is at most one such txid
    """
    for i, txid in enumerate(txids):
        if "coinbase" in get_transaction(txid)["vin"][0]:
            del txids[i]
            return txids
    return txids


@lru_cache()
@timeit(logger=logger, print_args=True)
def get_sorted_feerates_in_block(b: BlockHeight) -> List[FEERATE]:
    """
    return a sorted list (descending order) of the feerates of all transactions in block b.
    coinbase transaction is excluded!
    """
    block: Block = get_block_by_height(height=b)
    txids_in_block = remove_coinbase_txid(block["tx"])
    return sorted(map(lambda txid: feerate_oracle.get_tx_feerate(txid), txids_in_block), reverse=True)


@lru_cache()
@timeit(logger=logger, print_args=True)
def get_feerates_in_G_b_p(b: BlockHeight, p: float) -> List[FEERATE]:
    """
    return the feerates of the p top paying transactions in block b.
    i.e. the feerates of all transactions in the set G(b,p) (defined in the paper)
    """
    feerates = get_sorted_feerates_in_block(b)
    # FIXME: finding the p prefix by transactions size is expensive. instead we compute p prefix by tx count
    return feerates[:int(p * len(feerates))]


def get_db_key(t, n, p) -> bytes:
    return f"{t}-{n}-{p}".encode("utf8")


@timeit(logger=logger, print_args=True)
def F(t: TIMESTAMP, n: int, p: float) -> FEERATE:
    """
    See F doc in the top of this file
    """
    db_key = get_db_key(t=t, n=n, p=p)
    value: bytes = f_values_db.get(db_key)
    if value:
        return float(value.decode("utf8"))
    
    M = get_first_block_after_time_t(t)
    
    # G(b,p) might be empty if the block has no transactions. in that case we set
    # its minimal fee to float("inf")
    
    value: float = min(
        min(get_feerates_in_G_b_p(b, p))
        if len(get_feerates_in_G_b_p(b, p)) > 0 else float("inf")
        for b in range(M, M + n)
    )
    f_values_db.put(db_key, str(value).encode("utf8"))
    return value
