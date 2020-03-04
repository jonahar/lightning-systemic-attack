import os
import re
from dataclasses import dataclass
from typing import List

from datatypes import Timestamp
from paths import FEE_ESTIMATIONS_DIR

estimation_sample_file_regex = re.compile("estimatesmartfee_blocks=(\\d+)_mode=(\\w+)")

MAX_DIFF_BETWEEN_SAMPLE_TIMESTAMPS = 120  # 2 minutes

"""
go over the feerate estimations and find time windows in which we have
continuous estimations
"""


@dataclass(frozen=True, eq=True)
class Range:
    start: int
    end: int
    
    def __len__(self):
        return self.end - self.start
    
    def __repr__(self):
        return f"[{self.start}, {self.end}] (len={len(self)})"


def find_ranges_in_single_file(estimation_file_fullpath: str) -> List[Range]:
    ranges = []
    with open(estimation_file_fullpath) as f:
        timestamp_str, feerate_str = f.readline().strip().split(",")
        start = Timestamp(timestamp_str)
        end = start
        for line in f:
            timestamp_str, feerate_str = line.strip().split(",")
            timestamp = Timestamp(timestamp_str)
            if timestamp - end < MAX_DIFF_BETWEEN_SAMPLE_TIMESTAMPS:
                end = timestamp
            else:
                ranges.append(Range(start, end))
                start = timestamp
                end = timestamp
        
        ranges.append(Range(start, end))
    
    return ranges


def find():
    for entry in os.listdir(FEE_ESTIMATIONS_DIR):
        match = estimation_sample_file_regex.match(entry)
        if match:
            ranges = find_ranges_in_single_file(os.path.join(FEE_ESTIMATIONS_DIR, entry))
            print(f"{entry}:")
            for range in ranges:
                print(range)


if __name__ == "__main__":
    find()
