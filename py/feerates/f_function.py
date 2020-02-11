from functools import lru_cache
from typing import List

from bitcoin_cli import blockchain_height, get_block_by_height, get_transaction
from datatypes import Block, BlockHeight, FEERATE, TIMESTAMP, TXID
from feerates.feerates_logger import logger
from feerates.oracle_factory import get_multi_layer_oracle
from utils import timeit

"""
This module is responsible for computing the F function. this is defined as
  F(t,n,p) = min{ feerate(tx) | M <= height(tx) < M+n, tx ∈ G(height(tx), p) }

Where M is the first block height that came after time t
and G(b,p) is the set of the p top paying transactions in block height b
"""

feerate_oracle = get_multi_layer_oracle()


@lru_cache()
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
        m_time = get_block_by_height(m)["time"]
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
    return a sorted list of the feerates of all transactions in block b.
    coinbase transaction is excluded!
    """
    block: Block = get_block_by_height(height=b)
    txids_in_block = remove_coinbase_txid(block["tx"])
    return sorted(map(lambda txid: feerate_oracle.get_tx_feerate(txid), txids_in_block))


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


@timeit(logger=logger, print_args=True)
def F(t: TIMESTAMP, n: int, p: float) -> FEERATE:
    """
    See F doc in the top of this file
    """
    M = get_first_block_after_time_t(t)
    return min(
        min(get_feerates_in_G_b_p(b, p))
        for b in range(M, M + n)
    )
