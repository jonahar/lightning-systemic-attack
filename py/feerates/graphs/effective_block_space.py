from datetime import datetime
from functools import lru_cache
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np

from bitcoin_cli import get_block_time, get_tx_feerate, get_tx_weight, get_txs_in_block, set_bitcoin_cli
from datatypes import BlockHeight, Feerate, Timestamp
from feerates import logger
from feerates.graphs.estimated_feerates import parse_estimation_files
from feerates.graphs.graph_utils import get_first_block_after_time_t
from utils import leveldb_cache, timeit

set_bitcoin_cli("user")

BLOCK_MAX_WEIGHT = 4_000_000

num_blocks = 1
plot_data = parse_estimation_files()[num_blocks][1]
assert plot_data.label == "estimatesmartfee(n=1,mode=CONSERVATIVE)"
timestamps = np.array(plot_data.timestamps)
feerates = np.array(plot_data.feerates)


def get_feerate_estimation_at_time_t(t: Timestamp) -> Feerate:
    """
    return the feerate that was estimated at time t, with (blocks=1, mode=CONSERVATIVE)
    """
    # find the first index of timestamps larger than t
    t = min(t, np.max(timestamps))
    timestamp_idx_to_eval = np.argmax(timestamps >= t)
    return feerates[timestamp_idx_to_eval]


@lru_cache()
@timeit(logger=logger, print_args=True)
@leveldb_cache(value_to_str=str, str_to_value=float)
def get_block_space_for_feerate(height: BlockHeight, feerate: Feerate) -> int:
    """
    Return the part of block 'height' that may be filled with
    transactions with feerate 'feerate' (in weight units).
    That is the amount of the block that contains transactions with feerate less
    than 'feerate', or an empty part of the block (in case the block is less
    than 4M weight units)
    """
    txids = get_txs_in_block(height=height)
    
    # find transactions that pay MORE than 'feerate' and sum their weight
    occupied_part_weight = sum(map(
        lambda txid: get_tx_weight(txid),
        filter(lambda txid: get_tx_feerate(txid) > feerate, txids)
    ))
    
    return BLOCK_MAX_WEIGHT - occupied_part_weight


@lru_cache()
@leveldb_cache(value_to_str=str, str_to_value=float)
def get_average_block_space_for_feerate(
    first_block: BlockHeight,
    last_block: BlockHeight,
    feerate: Feerate,
) -> float:
    """
    return the average available block space of blocks in the
    range [first_blocks, last_block) under the given feerate
    this includes first_blocks and excludes last_block
    """
    return np.average([
        get_block_space_for_feerate(height=h, feerate=feerate)
        for h in range(first_block, last_block)
    ])


@lru_cache()
@leveldb_cache(value_to_str=str, str_to_value=float)
def how_much_space_victims_have(attack_start_timestamp: int) -> float:
    """
    Return the average available block space
    that victims will have if the attack starts at the given time.
    
    Attack starting at time t, means that the channel's feerate is determined
    at time t and the HTLCs are expired 100 blocks later.
    Therefore, the channels will be closed (100-10 = 90) blocks after time t,
    and victims will have 10 blocks to confirm their transactions.
    These are the blocks on which we check the available space.
    """
    # feerate is determined at the attack start time
    channel_feerate = round(get_feerate_estimation_at_time_t(t=attack_start_timestamp), 1)
    
    start_height = get_first_block_after_time_t(attack_start_timestamp)
    expiration_height = start_height + 100  # HTLCs expire in 100 blocks
    close_height = expiration_height - 10  # victims release 10 blocks before expiration
    
    return get_average_block_space_for_feerate(
        first_block=close_height + 1,
        last_block=expiration_height + 1,
        feerate=channel_feerate,
    )


@lru_cache()
@leveldb_cache(value_to_str=str, str_to_value=float)
def how_much_space_victims_have_improved_strategy(
    attack_start_timestamp: int,
    pre_payment_period_in_blocks: int,
) -> float:
    """
    In the improved strategy, the attacker tries to minimize the channel's feerate
    for a period of 'pre_payment_period_in_blocks' blocks, and then makes many
    payments that will expire in 100 blocks.
    
    Other than the way to determine the channel's feerate, this function is similar
    to 'how_much_space_victims_have()',
    """
    # the feerate that will be used is the minimum feerate that was estimated
    # between time t and t + pre_payment_period_in_blocks blocks
    channel_open_height = get_first_block_after_time_t(attack_start_timestamp)
    first_estimation_time = attack_start_timestamp
    last_estimation_time = get_block_time(channel_open_height + pre_payment_period_in_blocks - 1)
    # all feerates that were estimated in that period
    feerates_estimated_in_period = feerates[
        np.where((timestamps >= first_estimation_time) & (timestamps <= last_estimation_time))
    ]
    channel_feerate = round(np.min(feerates_estimated_in_period), 1)
    
    payments_height = get_first_block_after_time_t(last_estimation_time)
    expiration_height = payments_height + 100  # HTLCs expire in 100 blocks
    close_height = expiration_height - 10  # victims release 10 blocks before expiration
    
    return get_average_block_space_for_feerate(
        first_block=close_height + 1,
        last_block=expiration_height + 1,
        feerate=channel_feerate,
    )


# ------------------------------- plot functions -------------------------------


def plot_attack_start_time_vs_avg_block_weight_for_victim(
    avg_available_space_in_attack: np.ndarray,
    time_values: np.ndarray,
    time_ticks: np.ndarray,
    time_labels: List[str],
) -> None:
    plt.figure(figsize=(6.00, 2.14))
    # this graph is very noisy, linewidth=0.5 makes it a bit clearer
    plt.plot(time_values, avg_available_space_in_attack, linewidth=0.5)
    plt.xlabel("Attack start time")
    plt.xticks(ticks=time_ticks, labels=time_labels)
    plt.ylabel("Average block weight available")
    plt.grid()
    plt.savefig("attack-start-time-vs-avg-block-space.svg", bbox_inches='tight')


def plot_avg_block_space_for_victim_vs_number_of_times(
    avg_available_space_in_attack: np.ndarray,
    space_ticks: np.ndarray,
    space_ticks_labels: List[str],
) -> None:
    """
    the histogram of plot_attack_start_time_vs_avg_block_weight_for_victim
    """
    hist, bins = np.histogram(avg_available_space_in_attack, bins=100)
    # hist[i]: the number of attack start times in which the avg block space
    # available to the victims was between bins[i] and bins[i+1]
    
    plt.figure(figsize=(6.66, 3.75))
    plt.plot(bins[1:], hist)
    plt.xlabel("Average block weight available")
    plt.xticks(space_ticks, labels=space_ticks_labels)
    plt.ylabel("Number of times")
    plt.grid()
    plt.savefig("avg-block-space-vs-number-of-times.svg", bbox_inches='tight')


def plot_avg_block_space_vs_percent_of_time(
    avg_available_space_in_attack_list: List[Tuple[np.ndarray, str]],
    space_ticks: np.ndarray,
    space_ticks_labels: List[str],
) -> None:
    """
    Each item in avg_available_space_in_attack_list is a 2-elements tuple:
        1. an array with average available block space values
        2. label for the data in the array
    """
    plt.figure(figsize=(6.66, 3.75))
    
    for avg_available_space_in_attack, label in avg_available_space_in_attack_list:
        bins = np.array(range(0, 100 + 1), dtype=np.float) * BLOCK_MAX_WEIGHT / 100
        hist, bins = np.histogram(avg_available_space_in_attack, bins=bins)
        bins = bins[1:]
        cumsum = np.cumsum(hist[::-1])[::-1]
        # cumsum[i]: number of times that the average available block weight
        # was at least bins[i]
        
        cumsum_normalized = (cumsum * 100) / len(avg_available_space_in_attack)
        cumsum_normalized_2 = (cumsum * 100) / np.sum(hist)
        assert np.allclose(cumsum_normalized, cumsum_normalized_2)
        plt.plot(bins, cumsum_normalized, label=label)
    
    plt.xlabel("Average block weight available for victims")
    plt.xticks(space_ticks, labels=space_ticks_labels)
    plt.ylabel("Percent of time")
    plt.grid()
    plt.legend(loc="best")
    plt.savefig("avg-block-space-bound-vs-percent-of-time.svg", bbox_inches='tight')


# ==============================================================================


time_ticks = np.linspace(start=timestamps[0], stop=timestamps[-1], num=5)
time_labels = [
    datetime.utcfromtimestamp(t).strftime('%Y-%m-%d')
    for t in time_ticks
]
space_ticks = np.array([0, 1_000_000, 2_000_000, 3_000_000, 4_000_000])
space_ticks_labels = ["0", "1M", "2M", "3M", "4M"]

attack_start_timestamps = timestamps[::5]  # attack start times to evaluate

avg_available_space_in_attack = np.array([
    how_much_space_victims_have(attack_start_timestamp=t)
    for t in attack_start_timestamps
])

avg_available_space_in_attack_improved_200 = np.array([
    how_much_space_victims_have_improved_strategy(
        attack_start_timestamp=t,
        pre_payment_period_in_blocks=200,
    )
    for t in attack_start_timestamps
])

avg_available_space_in_attack_improved_400 = np.array([
    how_much_space_victims_have_improved_strategy(
        attack_start_timestamp=t,
        pre_payment_period_in_blocks=400,
    )
    for t in attack_start_timestamps
])

# plot_attack_start_time_vs_avg_block_weight_for_victim(
#     avg_available_space_in_attack=avg_available_space_in_attack,
#     time_values=attack_start_timestamps,
#     time_ticks=time_ticks,
#     time_labels=time_labels,
# )
#
# plot_avg_block_space_for_victim_vs_number_of_times(
#     avg_available_space_in_attack=avg_available_space_in_attack,
#     space_ticks=space_ticks,
#     space_ticks_labels=space_ticks_labels,
# )


plot_avg_block_space_vs_percent_of_time(
    avg_available_space_in_attack_list=[
        (avg_available_space_in_attack, "naive attack strategy"),
        (avg_available_space_in_attack_improved_200, "200 blocks fee minimization"),
        (avg_available_space_in_attack_improved_400, "400 blocks fee minimization"),
    ],
    space_ticks=space_ticks,
    space_ticks_labels=space_ticks_labels,
)

plt.show()
