import os
import re
from collections import defaultdict
from typing import Dict, List

from datatypes import FEERATE, btc_to_sat
from feerates.draw_plot import PlotData
from feerates.feerates_logger import logger

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
