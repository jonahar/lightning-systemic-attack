from math import floor
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np

from bitcoin_cli import get_tx_feerate, get_tx_weight, get_txs_in_block, set_bitcoin_cli
from datatypes import BlockHeight, Feerate
from feerates import logger
from feerates.graphs.estimated_feerates import get_top_p_minimal_feerate, parse_estimation_files
from feerates.graphs.f_function import get_first_block_after_time_t
from feerates.graphs.plot_utils import PlotData
from utils import leveldb_cache, timeit

BLOCK_MAX_WEIGHT = 4_000_000


@timeit(logger=logger, print_args=True)
@leveldb_cache(value_to_str=str, str_to_value=float)
def get_block_space_for_feerate(height: BlockHeight, feerate: Feerate) -> float:
    """
    return the portion of the block (percentage: a number between 0 and 100) that
    may be filled with a transaction with feerate 'feerate'.
    that is the amount of the block that contains transactions with feerate less
    than 'feerate', or an empty part of the block (in case the block is less than 4M weight units)
    """
    txids = get_txs_in_block(height=height)
    
    # find transactions that pay MORE than 'feerate' and sum their weight
    occupied_part_weight = sum(map(
        lambda txid: get_tx_weight(txid),
        filter(lambda txid: get_tx_feerate(txid) > feerate, txids)
    ))
    
    return (1 - (occupied_part_weight / BLOCK_MAX_WEIGHT)) * 100


def get_block_space_data(block_heights: List[BlockHeight], feerate: float) -> List[float]:
    return [
        get_block_space_for_feerate(height=height, feerate=feerate)
        for height in block_heights
    ]


def plot_available_block_space_vs_height(
    block_heights: List[BlockHeight],
    feerates: List[Feerate],
):
    """
    how much of the block is available (percentage) for a given feerate.
    different plot for every feerate.
    """
    for feerate in feerates:
        plt.figure()
        plt.title(f"Available block space under feerate (feerate={feerate})")
        block_spaces: List[float] = get_block_space_data(
            block_heights=block_heights,
            feerate=feerate,
        )
        plt.plot(block_heights, block_spaces)
        plt.ylabel("available block space (percentage)")
        plt.xlabel("height")
        plt.legend(loc="best")


def plot_available_block_space_upper_bound_vs_block_count(
    block_heights: List[BlockHeight],
    feerates: List[Feerate],
):
    """
    how many blocks are there that have at most X percent available space.
    different graph for every feerate, all on the same plot
    """
    plt.figure()
    plt.title(f"Number of blocks with at most p available space (blocks {block_heights[0]}-{block_heights[-1]})")
    percentages = list(range(0, 100 + 1))
    for feerate in feerates:
        block_spaces: List[float] = get_block_space_data(
            block_heights=block_heights,
            feerate=feerate,
        )
        # how many blocks have less than X% available
        blocks_count = [
            len([1 for space in block_spaces if space <= percentage])
            for percentage in percentages
        ]
        plt.plot(blocks_count, percentages, label=f"feerate={feerate}")
    
    plt.grid()
    plt.ylabel("block space (percentage)")
    plt.xlabel("number of blocks")
    plt.legend(loc="best")


def plot_available_block_space_lower_bound_vs_block_count(
    block_heights: List[BlockHeight],
    feerates: List[Feerate],
):
    """
    how many blocks are there that have at least X percent available space.
    different graph for every feerate, all on the same plot
    """
    plt.figure()
    plt.title(f"Number of blocks with at least p available space (blocks {block_heights[0]}-{block_heights[-1]})")
    percentages = list(range(0, 100 + 1))
    for feerate in feerates:
        block_spaces: List[float] = get_block_space_data(
            block_heights=block_heights,
            feerate=feerate,
        )
        # how many blocks have more than X% available
        blocks_count = [
            len([1 for space in block_spaces if space >= percentage])
            for percentage in percentages
        ]
        plt.plot(blocks_count, percentages, label=f"feerate={feerate}")
    
    plt.grid()
    plt.ylabel("block space (percentage)")
    plt.xlabel("number of blocks")
    plt.legend(loc="best")


def plot_percent_of_blocks_vs_available_space(
    block_heights: List[BlockHeight],
    feerates: List[Feerate],
):
    """
    what percentage of blocks have at least X percent available space.
    different graph for every feerate, all on the same plot
    """
    plt.figure()
    plt.title(f"Percentage of blocks with at least X% available space (blocks {block_heights[0]}-{block_heights[-1]})")
    percentages = np.arange(0, 100 + 1)
    for feerate in feerates:
        block_spaces: List[float] = get_block_space_data(
            block_heights=block_heights,
            feerate=feerate,
        )
        # how many blocks have at least X% available space
        percentage_of_blocks = [
            (len([1 for space in block_spaces if space >= percentage]) / len(block_heights)) * 100
            for percentage in percentages
        ]
        plt.plot(percentages, percentage_of_blocks, label=f"feerate={feerate}")
    
    plt.grid()
    plt.ylabel("percentage of blocks")
    plt.xlabel("available block space (percentage)")
    plt.legend(loc="best")


def htlcs_success_that_fit_in(weight_units: int) -> int:
    """
    return the number of HTLC-success txs that fit in the given weight units
    """
    HTLC_SUCCESS_WEIGHT = 703  # expected weight of htlc-success according to BOLT
    return floor(weight_units / HTLC_SUCCESS_WEIGHT)


def plot_htlc_success_space_vs_percent_of_blocks(
    block_heights: List[BlockHeight],
    feerates: List[Feerate],
):
    """
    how many block are there (percent) that can contain X HTLC-success txs that pays such feerate.
    different graph for every feerate, all on the same plot
    """
    plt.figure()
    plt.title(f"Number of blocks that have room for X HTLC-success txs (blocks {block_heights[0]}-{block_heights[-1]})")
    for feerate in feerates:
        block_spaces: List[float] = get_block_space_data(
            block_heights=block_heights,
            feerate=feerate,
        )
        htlcs_capacity = [
            htlcs_success_that_fit_in(weight_units=int((block_space * BLOCK_MAX_WEIGHT) / 100))
            for block_space in block_spaces
        ]
        htlcs_count = np.arange(0, max(htlcs_capacity) + 1)
        
        # we intentionally use max+2, so the last bin includes the elements
        # which are between max and max+1 (this includes max)
        htlcs_capacity_hist, bins = np.histogram(htlcs_capacity, bins=np.arange(max(htlcs_capacity) + 2))
        htlcs_capacity_hist_cumsum = np.cumsum(htlcs_capacity_hist[::-1])[::-1]
        assert len(htlcs_count) == len(htlcs_capacity_hist_cumsum)
        
        # htlcs_capacity_hist_cumsum[n] = number of blocks that have room for n HTLCs
        
        # normalize, so the data is in percentages
        htlcs_capacity_hist_cumsum_normalized = (htlcs_capacity_hist_cumsum / len(block_heights)) * 100
        plt.plot(htlcs_count, htlcs_capacity_hist_cumsum_normalized, label=f"feerate={feerate}")
    
    plt.grid()
    plt.xlabel("#HTLC-success transactions")
    plt.ylabel("percentage of blocks")
    plt.legend(loc="best")


def main():
    set_bitcoin_cli("user")
    
    # we only want this data to know the timestamps where to evaluate our function
    data: Dict[int, List[PlotData]] = parse_estimation_files()
    
    num_blocks = 2
    assert data[num_blocks][0].label == "estimatesmartfee(n=2,mode=CONSERVATIVE)"
    timestamps = data[num_blocks][0].timestamps
    feerates = data[num_blocks][0].feerates
    
    t_min = min(timestamps)
    t_max = max(timestamps)
    
    first_block = get_first_block_after_time_t(t_min)
    last_block = get_first_block_after_time_t(t_max)
    
    block_heights = list(range(first_block, last_block))
    
    p_values = [0.2, 0.5, 0.8]
    
    feerates_to_eval = [
        get_top_p_minimal_feerate(samples=feerates, p=p)
        for p in p_values
    ]
    # feerates_to_eval may be a little different in different runs due to numerical issues
    # (e.g. in one run we'll have feerate of 20.075, and in another run 20.076)
    # we round it to benefit the cache of get_block_space_for_feerate
    feerates_to_eval = [round(f, 1) for f in feerates_to_eval]
    
    # this graph is very noisy
    # plot_available_block_space_vs_height(block_heights=block_heights, feerates=feerates_to_eval)
    
    # plot_available_block_space_lower_bound_vs_block_count(block_heights=block_heights, feerates=feerates_to_eval)
    # plot_available_block_space_upper_bound_vs_block_count(block_heights=block_heights, feerates=feerates_to_eval)
    plot_htlc_success_space_vs_percent_of_blocks(block_heights=block_heights, feerates=feerates_to_eval)
    plot_percent_of_blocks_vs_available_space(block_heights=block_heights, feerates=feerates_to_eval)
    
    plt.show()


if __name__ == "__main__":
    main()
