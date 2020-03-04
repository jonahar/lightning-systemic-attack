from typing import Dict, List

import matplotlib.pyplot as plt

from bitcoin_cli import get_tx_feerate, get_tx_weight, get_txs_in_block, set_bitcoin_cli
from datatypes import BlockHeight, Feerate
from feerates import logger
from feerates.graphs.estimated_feerates import get_top_p_minimal_feerate, parse_estimation_files
from feerates.graphs.f_function import get_first_block_after_time_t
from feerates.graphs.plot_utils import PlotData
from utils import leveldb_cache, timeit


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
    
    total_block_weight = 4_000_000
    
    return (1 - (occupied_part_weight / total_block_weight)) * 100


def get_block_space_data(block_heights: List[BlockHeight], feerate: float) -> List[float]:
    return [
        get_block_space_for_feerate(height=height, feerate=feerate)
        for height in block_heights
    ]


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

    feerates_to_eval = {
        p: get_top_p_minimal_feerate(samples=feerates, p=p)
        for p in p_values
    }
    # feerates_to_eval may be a little different in different runs due to numerical issues
    # (e.g. in one run we'll have feerate of 20.075, and in another run 20.076)
    # we round it to benefit the cache of get_block_space_for_feerate
    feerates_to_eval = {p: round(f, 1) for p, f in feerates_to_eval.items()}

    percentages = list(range(0, 100 + 1))

    for p, feerate in feerates_to_eval.items():
        plt.figure()
        plt.title(f"Available block space under feerate (feerate={feerate})")
        block_spaces: List[float] = get_block_space_data(
            block_heights=block_heights,
            feerate=feerate,
        )
        plt.plot(block_heights, block_spaces)

    # -----------

    plt.figure()
    plt.title(f"Number of blocks with available space")
    for p, feerate in feerates_to_eval.items():
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
    
    plt.ylabel("available block space")
    plt.xlabel("number of blocks")
    plt.legend(loc="best")

    plt.show()


if __name__ == "__main__":
    main()
