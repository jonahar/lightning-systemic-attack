from typing import Dict, List

import matplotlib.pyplot as plt

from bitcoin_cli import get_tx_size, get_txs_in_block, set_bitcoin_cli
from datatypes import BlockHeight, Feerate
from feerates import logger
from feerates.graphs.estimated_feerates import get_top_p_minimal_feerate, parse_estimation_files
from feerates.graphs.f_function import get_first_block_after_time_t
from feerates.graphs.plot_f_function import block_heights_to_timestamps
from feerates.graphs.plot_utils import PlotData, plot_figure
from feerates.oracles.oracle_factory import get_multi_layer_oracle
from utils import leveldb_cache, timeit

feerates_oracle = get_multi_layer_oracle()


@timeit(logger=logger, print_args=True)
@leveldb_cache
def get_block_space_for_feerate(height: BlockHeight, feerate: Feerate) -> float:
    """
    return the portion of the block (percentage: a number between 0 and 100) that
    contains transactions with feerate at most 'feerate'.
    That is the part of the block that a transaction with feerate 'feerate' could've occupy
    
    """
    txids = get_txs_in_block(height=height, include_coinbase=False)
    
    if len(txids) == 0:
        # there are no non-coinbase transactions in this block. no transactions
        # entered this block, and it's assumed that we could'nt occupy any space
        # in the block
        return 0
    
    # the size of all non-coinbase txs in the block
    all_txs_size_bytes: int = sum(map(lambda txid: get_tx_size(txid), txids))
    
    # the size of txs whose feerate is smaller than the given feerate
    counted_txs_size_bytes: float = sum(
        map(
            lambda txid: get_tx_size(txid),
            filter(
                lambda txid: feerates_oracle.get_tx_feerate(txid) <= feerate,
                txids,
            )
        )
    )
    
    return (counted_txs_size_bytes / all_txs_size_bytes) * 100


def get_block_space_data(block_heights: List[BlockHeight], feerate: float) -> List[float]:
    return [
        get_block_space_for_feerate(height=height, feerate=feerate)
        for height in block_heights
    ]


if __name__ == "__main__":
    set_bitcoin_cli("user")
    
    # we only want this data to know the timestamps where to evaluate our function
    data: Dict[int, List[PlotData]] = parse_estimation_files()
    
    t_min = min(data[2][0].timestamps)
    t_max = max(data[2][0].timestamps)
    
    first_block = get_first_block_after_time_t(t_min)
    last_block = get_first_block_after_time_t(t_max)
    
    # we use constant block heights so the arguments to the cached function
    # get_block_space_for_feerate will stay the same
    first_block = 614000
    last_block = 617600
    
    timestamps = block_heights_to_timestamps(
        first_height=first_block,
        last_height=last_block,
    )
    block_heights = list(range(first_block, last_block))
    
    assert len(timestamps) == len(block_heights)
    
    p_values = [0.2, 0.5, 0.8]
    
    assert data[2][0].label == "estimatesmartfee(mode=CONSERVATIVE)"
    
    feerates_to_eval = [
        get_top_p_minimal_feerate(samples=data[2][0].feerates, p=p)
        for p in p_values
    ]
    
    for feerate in feerates_to_eval:
        block_spaces: List[float] = get_block_space_data(
            block_heights=block_heights,
            feerate=feerate,
        )
        plot_figure(
            title="Available block space under feerate",
            plot_data_list=[PlotData(timestamps, block_spaces, f"feerate={feerate}")],
        )
        plt.ylabel("block space")
        plt.legend(loc="best")
    
    plt.show()
