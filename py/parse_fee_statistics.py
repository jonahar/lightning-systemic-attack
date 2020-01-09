import os
import re
from collections import defaultdict
from math import ceil
from typing import Callable, List, Mapping, Tuple

import matplotlib.pyplot as plt
import numpy as np

TIMESTAMP = float
FEERATE = int  # in sat/vbyte
TIMESTAMPS = List[TIMESTAMP]
FEERATES = List[FEERATE]
LABEL = str

# PLOT_DATA is a mapping from num_blocks to a list of tuples, each tuple represents
# data for a single graph - feerate as a function of a timestamp
PLOT_DATA = Mapping[int, List[Tuple[TIMESTAMPS, FEERATES, LABEL]]]

estimation_sample_file_regex = re.compile("estimatesmartfee_blocks=(\\d+)_mode=(\\w+)")


def parse_estimations(estimation_files_dir: str) -> PLOT_DATA:
    data: PLOT_DATA = defaultdict(list)
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
                line = line[:-1] if line[-1] == "\n" else line
                timestamp_str, feerate_str = line.split(",")
                timestamps.append(int(timestamp_str))
                feerate = ceil(float(feerate_str) * (10 ** 8) * (10 ** -3))
                feerates.append(feerate)
        data[blocks].append(
            (timestamps, feerates, f"estimatesmartfee(mode={mode})")
        )
    
    return data


def get_F_t_n(
    block_timestamp_to_minfeerate: Mapping[TIMESTAMP, FEERATE],
) -> Callable[[TIMESTAMP, int], FEERATE]:
    """
    return the function F(t,n) which is defined as the minimal fee required for
        a transaction published at time t, to be mined in the next n blocks
        
    Parameters
    ----------
    block_timestamp_to_minfeerate : mapping
        maps block timestamp to the minimal feerate of a transaction in that block

    """
    blocks_timestamps = np.fromiter(block_timestamp_to_minfeerate.keys(), dtype=np.int)
    
    def F(t: TIMESTAMP, n: int) -> FEERATE:
        # TODO maybe we could preprocess block_timestamp_to_minfeerate to save work
        #  in this method
        
        # find the n minimal timestamps that are greater than t
        future_timestamps = blocks_timestamps[np.where(blocks_timestamps > t)]
        n = min(n, len(future_timestamps))
        timestamps_to_consider = np.partition(future_timestamps, n - 1)[:n]
        return min([
            block_timestamp_to_minfeerate[timestamp]
            for timestamp in timestamps_to_consider
        ])
    
    return F


def test_F_t_n() -> None:
    block_timestamp_to_minfeerate = {
        0: 4,
        10: 9,
        20: 4,
        30: 6,
        40: 10,
        50: 9,
        60: 1,
        70: 8,
        80: 5,
        90: 9,
        100: 7,
        110: 5,
        120: 8,
        130: 9,
        140: 8,
        150: 7,
        160: 5,
        170: 3,
        180: 1,
        190: 7,
        200: 2,
    }
    F = get_F_t_n(block_timestamp_to_minfeerate)
    
    assert F(3, 3) == 4
    assert F(25, 1) == 6
    assert F(42, 1) == 9
    assert F(42, 2) == 1
    assert F(42, 3) == 1
    assert F(100, 7) == 3
    assert F(171, 2) == 1
    assert F(171, 10) == 1


def gen_minfeerates_from_F_t_n(
    F: Callable[[TIMESTAMP, int], FEERATE],
    n: int,
    timestamps: TIMESTAMPS
) -> Tuple[TIMESTAMPS, FEERATES, LABEL]:
    return (
        timestamps, [F(t, n) for t in timestamps], f"actual minimal feerate required for {n} blocks"
    )


def parse_minfeerates_file(filename: str) -> Mapping[TIMESTAMP, FEERATE]:
    with open(filename) as f:
        lines = f.read().splitlines()
    if lines[0] != "block_timestamp,minfeerate":
        raise ValueError(f"Unrecognized first line for minfeerates file: '{lines[0]}'")
    lines = lines[1:]
    
    # feerates are already in sat/vbyte
    return {
        int(line.split(",")[0]): int(line.split(",")[1])
        for line in lines
    }


def draw(data: PLOT_DATA) -> None:
    """
    draw plots according to the given data.
    A new plot is created for each num_blocks
    """
    for n in data.keys():
        plt.figure()
        # sort by label before drawing, so similar labels in different graphs will
        # share the same color
        data[n].sort(key=lambda tuple: tuple[2])
        for timestamps, feerates, label in sorted(data[n]):
            plt.plot(timestamps, feerates, label=label)
        
        min_timestamp = min(min(t) for t, f, l in data[n])
        max_timestamp = max(max(t) for t, f, l in data[n])
        min_feerate = min(min(f) for t, f, l in data[n])
        max_feerate = max(max(f) for t, f, l in data[n])
        # graph config
        plt.legend(loc="best")
        plt.title(f"minimal feerate required to enter in {n} blocks")
        
        plt.xlabel("timestamp")
        plt.xticks(np.linspace(start=min_timestamp, stop=max_timestamp, num=10))
        
        plt.ylabel("feerate")
        plt.yticks(np.linspace(start=min_feerate, stop=max_feerate, num=10))
    
    plt.show()


def main():
    ln = os.path.expandvars("$LN")
    fee_stats_dir = os.path.join(ln, "fee-statistics")
    minfeerates_file = os.path.join(fee_stats_dir, "minfeerates")
    data = parse_estimations(fee_stats_dir)
    
    block_timestamp_to_minfeerate = parse_minfeerates_file(minfeerates_file)
    F = get_F_t_n(block_timestamp_to_minfeerate=block_timestamp_to_minfeerate)
    
    for n in data:
        # we compute the real feerate data at the timestamps of the first graph. it doesn't matter
        FIRST = 0
        data[n].append(
            gen_minfeerates_from_F_t_n(F=F, n=n, timestamps=data[n][FIRST][1])
        )
    
    draw(data)


if __name__ == "__main__":
    main()
