import os
import re
from collections import defaultdict
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt

from datatypes import Feerate, btc_to_sat
from feerates import logger
from feerates.graphs.plot_utils import PlotData, plot_figure
from paths import FEE_ESTIMATIONS_DIR

BYTE_IN_KBYTE = 1000

estimation_sample_file_regex = re.compile("estimatesmartfee_blocks=(\\d+)_mode=(\\w+)")

# only estimation in this time window will be included by the parse_estimation_files
# method. set both to None to include all estimations
MIN_TIMESTAMP = 1580224726
MAX_TIMESTAMP = 1582829418

# only show graphs for these values of num_blocks. set to None to include all
num_blocks_to_include = [2]


def parse_estimation_files() -> Dict[int, List[PlotData]]:
    """
    read all fee estimation files and prepare the plot data
    
    returns a dictionary from blocks_count (number of blocks used for the estimation)
    to a list of 'graphs' (represented by PLOT_DATA)
    """
    data = defaultdict(list)
    for entry in os.listdir(FEE_ESTIMATIONS_DIR):
        match = estimation_sample_file_regex.match(entry)
        if not match:
            continue  # not an estimation file
        num_blocks: int = int(match.group(1))
        mode: str = match.group(2)
        if num_blocks_to_include is not None and num_blocks not in num_blocks_to_include:
            continue

        timestamps = []
        feerates = []
        with open(os.path.join(FEE_ESTIMATIONS_DIR, entry)) as f:
            for line in f.readlines():
                try:
                    timestamp_str, feerate_str = line.strip().split(",")
                    # feerate returned by `estimatesmartfee` is in BTC/kB
                    feerate_btc_kb = float(feerate_str)
                    feerate: Feerate = btc_to_sat(feerate_btc_kb) / BYTE_IN_KBYTE
                    timestamp = int(timestamp_str)
                    if MIN_TIMESTAMP is None or MAX_TIMESTAMP is None or MIN_TIMESTAMP <= timestamp <= MAX_TIMESTAMP:
                        timestamps.append(timestamp)
                        feerates.append(feerate)
                except ValueError:
                    logger.error(f"ignoring line in file `{entry}` with unexpected format: `{line}`")

        data[num_blocks].append(
            PlotData(timestamps=timestamps, feerates=feerates, label=f"estimatesmartfee(n={num_blocks},mode={mode})")
        )
    
    return data


def get_top_p_minimal_feerate(samples: Iterable[float], p: float) -> float:
    """
    return the minimal feerate among the p top feerates.
    0 < p < 1
    """
    sorted_samples = sorted(samples)
    return sorted_samples[-int(len(sorted_samples) * p):][0]


def main():
    data = parse_estimation_files()
    
    p_values = [0.2, 0.5, 0.8]
    for num_blocks, plot_data_list in data.items():
        for plot_data in plot_data_list:
            fig = plot_figure(title=f"estimated feerates", plot_data_list=[plot_data])
            plt.figure(fig.number)
            for p in p_values:
                generalized_median = get_top_p_minimal_feerate(plot_data.feerates, p=p)
                plt.hlines(
                    y=generalized_median,
                    xmin=plot_data.timestamps[0],
                    xmax=plot_data.timestamps[-1],
                    label=f"top {p} estimates ({round(generalized_median, 1)})",
                )
            plt.legend(loc="best")
    
    plt.show()


if __name__ == "__main__":
    main()
