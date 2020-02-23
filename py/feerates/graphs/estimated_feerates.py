import os
import re
from collections import defaultdict
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt

from datatypes import FEERATE, btc_to_sat
from feerates import logger
from feerates.graphs.plot_utils import PlotData, plot_figure
from paths import LN

BYTE_IN_KBYTE = 1000

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


def get_top_p_minimal_feerate(samples: Iterable[float], p: float) -> float:
    """
    return the minimal feerate among the p top feerates.
    0 < p < 1
    """
    sorted_samples = sorted(samples)
    return sorted_samples[-int(len(sorted_samples) * p):][0]


if __name__ == "__main__":
    fee_stats_dir = os.path.join(LN, "data/fee-statistics")
    data = parse_estimation_files(fee_stats_dir)
    
    p_values = [0.2, 0.5, 0.8]
    for num_blocks, plot_data_list in data.items():
        for plot_data in plot_data_list:
            fig = plot_figure(title=f"estimated feerates(n={num_blocks})", plot_data_list=[plot_data])
            plt.figure(fig.number)
            for p in p_values:
                generalized_median = get_top_p_minimal_feerate(plot_data.feerates, p=p)
                plt.hlines(
                    y=generalized_median,
                    xmin=plot_data.timestamps[0],
                    xmax=plot_data.timestamps[-1],
                    label=f"top {p} estimates",
                )
            plt.legend(loc="best")
    
    plt.show()
