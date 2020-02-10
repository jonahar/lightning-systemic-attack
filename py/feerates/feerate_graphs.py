import os
import pickle
import re
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np

from bitcoin_cli import blockchain_height, get_block_by_height, get_transaction
from datatypes import Block, BlockHeight, FEERATE, TXID, btc_to_sat
from feerates.oracle_factory import get_multi_layer_oracle
from utils import now, setup_logging, timeit

TIMESTAMP = int

TIMESTAMPS = List[TIMESTAMP]
FEERATES = List[FEERATE]
LABEL = str

BYTE_IN_KBYTE = 1000

# PLOT_DATA represents data for a single graph - feerate as a function of timestamp
PLOT_DATA = Tuple[TIMESTAMPS, FEERATES, LABEL]

estimation_sample_file_regex = re.compile("estimatesmartfee_blocks=(\\d+)_mode=(\\w+)")

feerate_oracle = get_multi_layer_oracle()

logger = setup_logging(logger_name=__name__)


def parse_estimation_files(estimation_files_dir: str) -> Dict[int, List[PLOT_DATA]]:
    """
    read all fee estimation files and prepare the plot data
    
    returns a dictionary from blocks_count (number of blocks used for the estimation)
    to a list of 'graphs' (represented by PLOT_DATA)
    """
    data = defaultdict(list)
    for entry in os.listdir(estimation_files_dir):
        match = estimation_sample_file_regex.match(entry)
        if not match:
            continue  # not an estimation file
        blocks: int = int(match.group(1))
        mode: str = match.group(2)
        timestamps = []
        feerates = []
        with open(os.path.join(estimation_files_dir, entry)) as f:
            for line in f.readlines():
                try:
                    line_strip = line.strip()  # remove newline if exists
                    timestamp_str, feerate_str = line_strip.split(",")
                    timestamps.append(int(timestamp_str))
                    # feerate returned by `estimatesmartfee` is in BTC/kB
                    feerate_btc_kb = float(feerate_str)
                    feerate: FEERATE = btc_to_sat(feerate_btc_kb) / BYTE_IN_KBYTE
                    feerates.append(feerate)
                except ValueError:
                    logger.error(f"ignoring line in file `{entry}` with unexpected format: `{line_strip}`")
        
        data[blocks].append(
            (timestamps, feerates, f"estimatesmartfee(mode={mode})")
        )
    
    return data


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


@timeit(logger=logger, print_args=False)
def get_largest_prefix(txids: List[TXID], max_size: float) -> List[TXID]:
    """
    return the largest prefix of the given list such that the total size of
    transactions in the prefix is less than or equal to max_size
    """
    total_size = 0
    for i, txid in enumerate(txids):
        if total_size + get_transaction(txid)["size"] > max_size:
            return txids[:i]
    return txids


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


@timeit(logger=logger, print_args=True)
@lru_cache(8192)
def G(b: int, p: float) -> List[TXID]:
    """
    the function G(b,p), which is defined as the set of the `p` top paying transactions
    in block `b` (in terms of feerate)
    """
    block: Block = get_block_by_height(height=b)
    # remove the coinbase transaction
    txids_in_block = remove_coinbase_txid(block["tx"])
    txids_sorted = sorted(
        txids_in_block,
        key=lambda txid: feerate_oracle.get_tx_feerate(txid),
        reverse=True
    )
    return get_largest_prefix(txids=txids_sorted, max_size=p * block["size"])


@timeit(logger=logger, print_args=True)
def F(t: TIMESTAMP, n: int, p: float) -> FEERATE:
    """
    The function F(t,n,p) which is defined as:
        F(t,n,p) = min{ feerate(tx) | M <= height(tx) < M+n, tx ∈ G(b, p) }
    
    Where M is the first block height that came after time t
    """
    first_block = get_first_block_after_time_t(t=t)
    return min(
        feerate_oracle.get_tx_feerate(txid)
        for b in range(first_block, first_block + n)
        for txid in G(b=b, p=p)
    )


def make_F_graph(timestamps: TIMESTAMPS, n: int, p: float) -> PLOT_DATA:
    """
    create plot-data for the F(t,n,p) function
    """
    feerates = [F(t, n, p) for t in timestamps]
    return timestamps, feerates, f"F(t,n={n},p={p})"


def plot_figure(title: str, data: List[PLOT_DATA]):
    """
    add the given plot data to a new figure. all graphs on the same figure
    """
    plt.figure()
    for timestamps, feerates, label in data:
        plt.plot(timestamps, feerates, label=label)
    
    min_timestamp = min(min(t) for t, f, l in data)
    max_timestamp = max(max(t) for t, f, l in data)
    min_feerate = min(min(f) for t, f, l in data)
    max_feerate = max(max(f) for t, f, l in data)
    # graph config
    plt.legend(loc="best")
    plt.title(title)
    
    xticks = np.linspace(start=min_timestamp, stop=max_timestamp, num=10)
    yticks = np.linspace(start=min_feerate, stop=max_feerate, num=10)
    
    timestamp_to_date_str = lambda t: datetime.utcfromtimestamp(t).strftime('%Y-%m-%d %H:%M')
    plt.xticks(
        ticks=xticks,
        labels=[timestamp_to_date_str(t) for t in xticks]
    )
    plt.xlabel("timestamp")
    
    plt.yticks(ticks=yticks)
    plt.ylabel("feerate")


def main():
    ln = os.path.expandvars("$LN")
    fee_stats_dir = os.path.join(ln, "data/fee-statistics")
    data = parse_estimation_files(fee_stats_dir)
    
    for num_blocks, plot_data_list in data.items():
        # we compute F at the timestamps of the first graph. they should all
        # have the same timestamps anyway, but it doesn't really matter
        timestamps = plot_data_list[0][0]
        for p in [1, 0.9, 0.8]:
            plot_data_list.append(make_F_graph(timestamps=timestamps, n=num_blocks, p=p))
            # make_F_graph is computationally expensive. we don't want to lost it.
            # dump the precomputed data
            with open(f"{fee_stats_dir}/plot_data_{now()}.pickle", mode="wb") as f:
                pickle.dump(data, f)
    
    for num_blocks, plot_data_list in data.items():
        # sort by label before drawing, so similar labels in different graphs will
        # share the same color
        plot_data_list.sort(key=lambda tuple: tuple[2])
        plot_figure(title=f"feerate(n={num_blocks})", data=plot_data_list)
    
    plt.show()


if __name__ == "__main__":
    main()
