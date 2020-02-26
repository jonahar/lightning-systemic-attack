import random
import string
from time import time
from typing import Callable, List

from utils import leveldb_cache, sqlite_cache


@leveldb_cache(value_to_str=str, str_to_value=str)
def test_method_with_leveldb_cache(x: str) -> str:
    return x


@sqlite_cache(value_to_str=str, str_to_value=str)
def test_method_with_sqlite_cache(x: str) -> str:
    return x


def time_method(method: Callable, inputs: List[str]) -> float:
    # make calls that will populate the caches
    for input in inputs:
        method(input)
    
    t0 = time()
    for input in inputs:
        method(input)
    t1 = time()
    return round(t1 - t0, 3)


def test():
    for num_inputs in [1000, 5000, 10000]:
        print(f"Testing for {num_inputs} inputs:")
        input_length = 64  # the length of a TXID
        inputs = [
            ''.join(random.choice(string.ascii_lowercase) for i in range(input_length))
            for _ in range(num_inputs)
        ]
        
        leveldb_total_time = time_method(test_method_with_leveldb_cache, inputs)
        sqlite_total_time = time_method(test_method_with_sqlite_cache, inputs)
        print(f"leveldb cache: {leveldb_total_time} sec")
        print(f"sqlite cache:  {sqlite_total_time} sec")
        
        if leveldb_total_time < sqlite_total_time:
            winner = "leveldb"
            ratio = sqlite_total_time / leveldb_total_time
        else:
            winner = "sqlite"
            ratio = leveldb_total_time / sqlite_total_time
        
        print(f"{winner} is {round(ratio, 2)} times faster")


if __name__ == "__main__":
    test()
