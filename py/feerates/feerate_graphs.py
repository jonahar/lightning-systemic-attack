import os
import re
from collections import defaultdict, namedtuple
from datetime import datetime
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np

from blockchain_parser.blockchain import Blockchain
from datatypes import BlockHeight, FEERATE, TIMESTAMP, btc_to_sat
from feerates.f_function import F, get_first_block_after_time_t
from feerates.feerates_logger import logger
from feerates.oracle_factory import blocks_dir, index_dir
from utils import timeit

TIMESTAMPS = List[TIMESTAMP]
FEERATES = List[FEERATE]
LABEL = str

BYTE_IN_KBYTE = 1000

# PlotData represents data for a single graph - feerate as a function of timestamp
PlotData = namedtuple("PlotData", ["timestamps", "feerates", "label"])

estimation_sample_file_regex = re.compile("estimatesmartfee_blocks=(\\d+)_mode=(\\w+)")


def parse_estimation_files(estimation_files_dir: str) -> Dict[int, List[PlotData]]:
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
            PlotData(timestamps=timestamps, feerates=feerates, label=f"estimatesmartfee(mode={mode})")
        )
    
    return data


def compute_F_values(
    timestamps: TIMESTAMPS,
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
def block_heights_to_timestamps(first_height: BlockHeight, last_height: BlockHeight) -> TIMESTAMPS:
    """
    return a list with the timestamps of all blocks from first_height to last_height (excluding)
    """
    blockchain = Blockchain(blocks_dir)
    blocks_gen = blockchain.get_ordered_blocks(
        index=index_dir,
        start=first_height,
        end=last_height,
    )
    res = [
        int(datetime.timestamp(block.header.timestamp))
        for block in blocks_gen
    ]
    if len(res) != (last_height - first_height):
        logger.warning(
            f"extracted timestamps for {len(res)} blocks. "
            f"expected number was {last_height - first_height}"
        )
    return res


def plot_figure(title: str, data: List[PlotData]):
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
    
    # find the timestamps in which to evaluate F
    start_time = min(
        min(plot_data[0])
        for n, plot_data_list in data.items()
        for plot_data in plot_data_list
    )
    end_time = max(
        max(plot_data[0])
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
        plot_data_list.sort(key=lambda tuple: tuple[2])
        plot_figure(title=f"feerate(n={num_blocks})", data=plot_data_list)
    
    plt.show()


if __name__ == "__main__":
    main()
