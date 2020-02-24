from typing import Dict, List

import matplotlib.pyplot as plt

from bitcoin_cli import get_tx_size, get_txs_in_block
from datatypes import BlockHeight, Feerate
from feerates.graphs.estimated_feerates import get_top_p_minimal_feerate, parse_estimation_files
from feerates.graphs.f_function import get_first_block_after_time_t
from feerates.graphs.plot_f_function import block_heights_to_timestamps
from feerates.graphs.plot_utils import PlotData
from feerates.oracles.oracle_factory import get_multi_layer_oracle

feerates_oracle = get_multi_layer_oracle()


def get_block_space_for_feerate(height: BlockHeight, feerate: Feerate) -> float:
    """
    return the portion of the block (percentage: a number between 0 and 100) that
    contains transactions with feerate at most 'feerate'.
    That is the part of the block that a transaction with feerate 'feerate' could've
    have occupy
    
    This portion is defined by the size of all
    
    """
    txids = get_txs_in_block(height=height, include_coinbase=False)
    
    if len(txids) == 0:
        # there are no non-coinbase transactions in this block. no transactions
        # entered this block, and it's assumed that we could'nt occupy any space
        # in the block
        return 0
    
    # the size of all non-coinbase txs in the block
    all_txs_size_bytes = sum(map(lambda txid: get_tx_size(txid), txids))
    
    # the size of txs whose feerate is smaller than the given feerate
    counted_txs_size_bytes = sum(
        map(
            lambda txid: get_tx_size(txid),
            filter(
                lambda txid: feerates_oracle.get_tx_feerate(txid) <= feerate,
                txids,
            )
        )
    )
    
    return (counted_txs_size_bytes / all_txs_size_bytes) * 100


def get_block_space_data(block_heights: List[BlockHeight], minimal_feerate: float) -> List[float]:
    return [
        get_block_space_for_feerate(height=height, feerate=minimal_feerate)
        for height in block_heights
    ]


if __name__ == "__main__":
    # we only want this data to know the timestamps where to evaluate our function
    data: Dict[int, List[PlotData]] = parse_estimation_files()
    
    t_min = min(data[2][0].timestamps)
    t_max = max(data[2][0].timestamps)
    
    first_block = get_first_block_after_time_t(t_min)
    last_block = get_first_block_after_time_t(t_max)
    
    timestamps = block_heights_to_timestamps(
        first_height=first_block,
        last_height=last_block,
    )
    block_heights = list(range(first_block, last_block))
    
    assert len(timestamps) == len(block_heights)
    
    for num_blocks, plot_data_list in data.items():
        for plot_data in plot_data_list:
            p_values = [0.2, 0.5, 0.8]
            for p in p_values:
                block_spaces: List[float] = get_block_space_data(
                    block_heights=block_heights,
                    minimal_feerate=get_top_p_minimal_feerate(plot_data.feerates, p=p)
                )
                plt.plot(timestamps, block_spaces, label=plot_data.label)
