from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np

from bitcoin_cli import set_bitcoin_cli
from datatypes import Feerate, Timestamp
from feerates.graphs.block_space_graph import get_block_space_for_feerate
from feerates.graphs.estimated_feerates import parse_estimation_files
from feerates.graphs.graph_utils import get_first_block_after_time_t

num_blocks = 1
plot_data = parse_estimation_files()[num_blocks][1]
assert plot_data.label == "estimatesmartfee(n=1,mode=CONSERVATIVE)"
timestamps = np.array(plot_data.timestamps)
feerates = np.array(plot_data.feerates)

BITCOIN_BLOCK_MAX_WEIGHT = 4_000_000
HTLCS_PER_CHANNEL = 483
HTLC_SUCCESS_WEIGHT = 703
COMMITMENT_WEIGHT = 724 + 172 * HTLCS_PER_CHANNEL  # expected weight according to BOLTS


def how_many_htlcs_fit_in_weight(space: int) -> int:
    """
    return the number of HTLC-success that can be confirmed into the given
    space (in weight units).
    one commitment for every HTLCS_PER_CHANNEL htlcs is included in the calculation
    """
    confirmed_htlcs = 0
    
    # find out how many complete packages can be included - that is a commitment
    # and all of its htlcs
    complete_pkg_size = COMMITMENT_WEIGHT + HTLC_SUCCESS_WEIGHT * HTLCS_PER_CHANNEL
    complete_pkgs_to_include = space // complete_pkg_size
    space -= complete_pkgs_to_include * complete_pkg_size
    confirmed_htlcs += complete_pkgs_to_include * HTLCS_PER_CHANNEL
    
    assert space < complete_pkg_size
    
    # find out if we can include a part of another package
    
    if space >= COMMITMENT_WEIGHT:
        space -= COMMITMENT_WEIGHT
        num_htlc_to_include = space // HTLC_SUCCESS_WEIGHT
        assert num_htlc_to_include < HTLCS_PER_CHANNEL
        space -= num_htlc_to_include * HTLC_SUCCESS_WEIGHT
        assert space < HTLC_SUCCESS_WEIGHT
        
        confirmed_htlcs += num_htlc_to_include
    
    return confirmed_htlcs


def get_feerate_estimation_at_time_t(t: Timestamp) -> Feerate:
    """
    return the feerate that was estimated at time t, with (blocks=1, mode=CONSERVATIVE)
    """
    # find the first index of timestamp larger than t timestamp
    t = min(t, np.max(timestamps))
    timestamp_idx_to_eval = np.argmax(timestamps >= t)
    return feerates[timestamp_idx_to_eval]


def get_max_confirmed_htlcs(t: Timestamp) -> int:
    """
    return the maximum number of HTLCs that can be confirmed before expiration
    in an attack starting at time x.
    Assuming the channel's feerate was determined at time x by bitcoind
    """
    start_height = get_first_block_after_time_t(t)
    close_height = start_height + 90  # channels will be dropped 90 blocks after the opening time
    expiration_height = close_height + 10
    
    # we now need to find the amount of HTLC-success that can enter the
    # blockchain, from close_height+1 to expiration_height (including)
    channel_feerate = round(get_feerate_estimation_at_time_t(t), 1)
    
    avail_space = 0
    for h in range(close_height + 1, expiration_height + 1):
        block_avail_space_percent = get_block_space_for_feerate(height=h, feerate=channel_feerate)
        avail_space += (block_avail_space_percent * BITCOIN_BLOCK_MAX_WEIGHT) // 100
    
    max_confirmed_htlcs = how_many_htlcs_fit_in_weight(avail_space)
    return max_confirmed_htlcs


def plot_attack_start_time_vs_confirmed_htlcs():
    """
    For a given time X, if we open channels at time X and execute the attack
    on time X+24hour , Y is the minimal number of HTLCs to expire
    """
    # we want to exclude timestamps near the last 100 blocks.
    # 100 blocks ~ 1000 minutes ~ 1000 samples
    
    timestamps_values = timestamps[:-1000:5]
    max_confirmed_htlcs_values = list(
        map(lambda t: get_max_confirmed_htlcs(t), timestamps_values)
    )
    
    num_channels_values = [
        max_confirmed_htlcs // HTLCS_PER_CHANNEL
        for max_confirmed_htlcs in max_confirmed_htlcs_values
    ]
    
    xticks = np.linspace(start=timestamps_values[0], stop=timestamps_values[-1], num=10)
    timestamp_to_date_str = lambda t: datetime.utcfromtimestamp(t).strftime('%Y-%m-%d %H:%M')
    
    plt.figure()
    plt.plot(timestamps_values, max_confirmed_htlcs_values, label="")
    plt.grid()
    plt.xlabel("Attack start time")
    plt.ylabel("Maximum #HTLC-success to be confirmed before expiration")
    plt.xticks(
        ticks=xticks,
        labels=[timestamp_to_date_str(t) for t in xticks]
    )
    
    plt.figure()
    plt.plot(timestamps_values, num_channels_values, label="")
    plt.grid()
    plt.xlabel("Attack start time")
    plt.ylabel("Minimum #attacked-channels required for stealing")
    plt.xticks(
        ticks=xticks,
        labels=[timestamp_to_date_str(t) for t in xticks]
    )
    
    plt.show()


set_bitcoin_cli("user")
plot_attack_start_time_vs_confirmed_htlcs()
