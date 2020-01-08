import os
import re
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np

TIMESTAMPS = List[float]
FEERATES = List[float]  # in sat/vbyte
LABEL = str

estimation_sample_file_regex = re.compile("estimatesmartfee_blocks=(\\d+)_mode=(\\w+)")


def parse_estimations(estimation_files_dir: str) -> List[Tuple[TIMESTAMPS, FEERATES, LABEL]]:
    data = []
    for entry in os.listdir(estimation_files_dir):
        match = estimation_sample_file_regex.match(entry)
        if not match:
            continue  # not an estimation file
        blocks: str = match.group(1)
        mode: str = match.group(2)
        with open(os.path.join(estimation_files_dir, entry)) as f:
            lines = f.read().splitlines()
        
        timestamps = []
        feerates = []
        for line in lines:
            timestamp, feerate_str = line.split(",")
            # convert feerate from btc/kb to sat/vbyte
            # https://bitcoin.stackexchange.com/questions/87291
            feerate = int(float(feerate_str) * (10 ** 8) * (10 ** -3))
            timestamps.append(timestamps)
            feerates.append(feerate)
        
        data.append(
            (timestamps, feerates, f"estimatesmartfee(blocks={blocks}, mode={mode})")
        )
    return data


def parse_minfeerates(filename: str) -> List[Tuple[TIMESTAMPS, FEERATES, LABEL]]:
    with open(filename) as f:
        lines = f.read().splitlines()
    if lines[0] != "block_timestamp,minfeerate":
        raise ValueError(f"Unrecognized first line for minfeerates file: '{lines[0]}'")
    lines = lines[1:]
    timestamps = list(map(lambda line: int(line.split(",")[0]), lines))
    feerates = list(map(lambda line: float(line.split(",")[1]), lines))
    # feerates are already in sat/vbyte
    return [(
        (timestamps, feerates, "minfeerate")
    )]


def draw(data: List[Tuple[TIMESTAMPS, FEERATES, LABEL]]) -> None:
    for timestamps, feerates, label in data:
        plt.plot(timestamps, feerates, label=label)
    
    min_timestamp = min(min(t) for t, f, l in data)
    max_timestamp = max(max(t) for t, f, l in data)
    min_feerate = min(min(f) for t, f, l in data)
    max_feerate = max(max(f) for t, f, l in data)
    
    # graph config
    plt.legend(loc='best')
    plt.title('estimated feerate')
    
    plt.xlabel('timestamp')
    plt.xticks(np.linspace(start=min_timestamp, stop=max_timestamp, num=10))
    
    plt.ylabel('feerate')
    plt.yticks(np.linspace(start=min_feerate, stop=max_feerate, num=10))
    plt.show()


def main():
    ln = os.path.expandvars("$LN")
    fee_stats_dir = os.path.join(ln, "fee-statistics")
    minfeerates_file = os.path.join(fee_stats_dir, "minfeerates")
    data = parse_estimations(fee_stats_dir)
    data += parse_minfeerates(minfeerates_file)
    draw(data)


if __name__ == "__main__":
    main()
