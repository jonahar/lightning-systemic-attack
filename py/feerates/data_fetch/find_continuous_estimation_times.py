import os
import re
from typing import List, Set

from datatypes import Timestamp
from paths import FEE_ESTIMATIONS_DIR

estimation_sample_file_regex = re.compile("estimatesmartfee_blocks=(\\d+)_mode=(\\w+)")

MAX_DIFF_BETWEEN_SAMPLE_TIMESTAMPS = 120  # 2 minutes

"""
go over the feerate estimations and find time windows in which we have
continuous estimations
"""


def find_ranges_in_single_file(estimation_file_fullpath: str) -> List[Set[Timestamp]]:
    """
    return a list of sets. each set is a collection of timestamps which are close
    enough to each other - less than MAX_DIFF_BETWEEN_SAMPLE_TIMESTAMPS between
    each two consecutive samples
    """
    ranges = []
    with open(estimation_file_fullpath) as f:
        timestamp_str, feerate_str = f.readline().strip().split(",")
        start = Timestamp(timestamp_str)
        end = start
        curr_range = {start}
        for line in f:
            try:
                timestamp_str, feerate_str = line.strip().split(",")
            except ValueError:
                continue  # line in bad format. skip
            
            timestamp = Timestamp(timestamp_str)
            if timestamp - end < MAX_DIFF_BETWEEN_SAMPLE_TIMESTAMPS:
                curr_range.add(timestamp)
                end = timestamp
            else:
                ranges.append(curr_range)
                start = timestamp
                end = timestamp
                curr_range = {start}
        
        ranges.append(curr_range)
    
    return ranges


def find():
    for entry in os.listdir(FEE_ESTIMATIONS_DIR):
        match = estimation_sample_file_regex.match(entry)
        if match:
            ranges = find_ranges_in_single_file(os.path.join(FEE_ESTIMATIONS_DIR, entry))
            print(f"{entry}:")
            for range in ranges:
                print(f"[{min(range)}, {max(range)}] (len={len(range)})")


if __name__ == "__main__":
    find()
