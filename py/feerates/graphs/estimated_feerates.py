import os
import re
from collections import defaultdict
from typing import Dict, Iterable, List

import matplotlib
import matplotlib.pyplot as plt

from datatypes import Feerate, btc_to_sat
from feerates import logger
from feerates.graphs.graph_utils import PlotData, plot_figure
from paths import FEE_ESTIMATIONS_DIR

matplotlib.rcParams.update({'font.size': 10})

BYTE_IN_KBYTE = 1000

estimation_sample_file_regex = re.compile("estimatesmartfee_blocks=(\\d+)_mode=(\\w+)")

# only estimations in the time window [MIN_TIMESTAMP, MAX_TIMESTAMP] will be included
# by the parse_estimation_files method. set both to None to include all estimations


# this range gives us blocks 620136-630247
MIN_TIMESTAMP = 1583317269
MAX_TIMESTAMP = 1589384721

# only show graphs for these values of num_blocks. set to None to include all
num_blocks_to_include = [1]


def parse_estimation_files() -> Dict[int, List[PlotData]]:
    """
    read all fee estimation files and prepare the plot data
    
    returns a dictionary from blocks_count (number of blocks used for the estimation)
    to a list of 'graphs' (represented by PLOT_DATA)
    """
    data = defaultdict(list)
    for entry in os.listdir(FEE_ESTIMATIONS_DIR):
        match = estimation_sample_file_regex.fullmatch(entry)
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


def get_feerates_percentile(samples: Iterable[float], p: float) -> float:
    """
    return the p'th percentile of the samples
    0 < p < 1
    """
    sorted_samples = sorted(samples)
    return sorted_samples[:int(len(sorted_samples) * p)][-1]


def main():
    data = parse_estimation_files()
    
    p_values = [0.2, 0.5, 0.8]
    for num_blocks, plot_data_list in data.items():
        for plot_data in plot_data_list:
            fig = plot_figure(title="", plot_data_list=[plot_data], figsize=(6.66, 3.75))
            plt.figure(fig.number)
            # for p in p_values:
            #     percentile = get_feerates_percentile(plot_data.feerates, p=p)
            #     plt.hlines(
            #         y=percentile,
            #         xmin=plot_data.timestamps[0],
            #         xmax=plot_data.timestamps[-1],
            #         label=f"{int(p * 100)}'th percentile ({round(percentile, 1)})",
            #     )
            plt.legend(loc="best")
            plt.grid()
            plt.xlabel("Estimation time")
            plt.ylabel("Estimated feerate (sat/B)")
    plt.savefig("estimated-feerates.svg", bbox_inches='tight')
    # plt.show()


if __name__ == "__main__":
    main()
