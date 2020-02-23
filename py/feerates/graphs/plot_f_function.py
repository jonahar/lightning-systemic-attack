import os
from typing import List

import matplotlib.pyplot as plt
import numpy as np

from bitcoin_cli import get_block_time, set_bitcoin_cli
from datatypes import BlockHeight, TIMESTAMP
from feerates import logger
from feerates.graphs.plot_utils import PlotData, plot_figure
from feerates.graphs.estimated_feerates import parse_estimation_files
from feerates.graphs.f_function import F, get_first_block_after_time_t
from utils import timeit


def compute_F_values(
    timestamps: List[TIMESTAMP],
    n_values: List[int],
    p_values: List[float],
) -> np.ndarray:
    """
    compute the function F for each combination of points.
    return a 3-dimensional array with shape:
        ( len(timestamps), len(n_values), len(p_values) )
        
    """
    try:
        # there are many timestamps but only a few n and p values.
        # to benefit the cache we should iterate timestamps in the outer loop
        f_values = np.zeros(shape=(len(timestamps), len(n_values), len(p_values)))
        for t_idx, t in enumerate(timestamps):
            for n_idx, n in enumerate(n_values):
                for p_idx, p in enumerate(p_values):
                    f_values[t_idx, n_idx, p_idx] = F(t, n, p)
        
        return f_values
    except KeyboardInterrupt:
        values_computed = (t_idx + 1) * (n_idx + 1) * (p_idx + 1)
        total_needed_values = len(timestamps) * len(n_values) * len(p_values)
        print(
            f"Terminating compute_F_values. "
            f"Total values computed: {values_computed} out of {total_needed_values}"
        )


@timeit(logger=logger)
def block_heights_to_timestamps(first_height: BlockHeight, last_height: BlockHeight) -> List[TIMESTAMP]:
    """
    return a list with the timestamps of all blocks from first_height to last_height (excluding)
    """
    
    return [
        get_block_time(h=h)
        for h in range(first_height, last_height)
    ]


def main():
    set_bitcoin_cli("user")
    
    ln = os.path.expandvars("$LN")
    fee_stats_dir = os.path.join(ln, "data/fee-statistics")
    data = parse_estimation_files(fee_stats_dir)
    
    # find the timestamps in which to evaluate F
    start_time = min(
        min(plot_data.timestamps)
        for n, plot_data_list in data.items()
        for plot_data in plot_data_list
    )
    end_time = max(
        max(plot_data.timestamps)
        for n, plot_data_list in data.items()
        for plot_data in plot_data_list
    )
    
    timestamps_to_eval_F = block_heights_to_timestamps(
        first_height=get_first_block_after_time_t(start_time),
        last_height=get_first_block_after_time_t(end_time),
    )
    
    p_values = [1, 0.9, 0.5, 0.1, 0.01]
    n_values = sorted(data.keys())
    
    f_values = compute_F_values(
        timestamps=timestamps_to_eval_F,
        n_values=n_values,
        p_values=p_values,
    )
    
    # add the computed F values to the graphs data
    for n_idx, n in enumerate(n_values):
        for p_idx, p in enumerate(p_values):
            data[n].append(
                PlotData(
                    timestamps=timestamps_to_eval_F,
                    feerates=f_values[:, n_idx, p_idx],
                    label=f"F(t,n={n},p={p})",
                )
            )
    
    # plot all
    for num_blocks, plot_data_list in data.items():
        # sort by label before drawing, so similar labels in different graphs will
        # share the same color
        plot_data_list.sort(key=lambda plot_data: plot_data.label)
        plot_figure(title=f"feerate(n={num_blocks})", plot_data_list=plot_data_list)
    
    plt.show()


if __name__ == "__main__":
    main()
