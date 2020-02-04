import os
import sys
from concurrent.futures import ThreadPoolExecutor

from bitcoin_cli import get_block_by_height
from datatypes import Block, BlockHeight
from feerates.bitcoind_oracle import BitcoindTXFeeOracle
from feerates.feerates_logger import logger
from feerates.oracle_factory import DB_FOLDER
from feerates.tx_fee_oracle import TXFeeOracle


def dump_block_feerates(h: BlockHeight, oracle: TXFeeOracle) -> None:
    """
    computes the feerate of all transactions in block at height h and dump them
    to a text file in the DB_FOLDER directory
    """
    logger.info(f"Dumping feerates for block {h}")
    filepath = os.path.join(DB_FOLDER, f"block_{h}_feerates")
    if os.path.isfile(filepath):
        return  # this block was already dumped
    
    # use tmp suffix until we finish with that block (in case we crash before we dumped all txs)
    filepath_tmp = f"{filepath}.tmp"
    with open(filepath_tmp, mode="w") as f:
        block: Block = get_block_by_height(h)
        # we dump all transactions, including coinbase
        for txid in block["tx"]:
            feerate = oracle.get_tx_feerate(txid)
            if feerate is None:
                logger.error(f"Oracle couldn't retrieve feerate for a transaction in block {h}")
                return
            f.write(f"{txid},{feerate}\n")
    
    os.rename(filepath_tmp, filepath)


def dump_block_feerates_serial(first_block: int, last_block: int, oracle: TXFeeOracle) -> None:
    for h in range(first_block, last_block + 1):
        dump_block_feerates(h=h, oracle=oracle)


def dump_block_feerates_parallel(first_block: int, last_block: int, oracle: TXFeeOracle) -> None:
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(fn=dump_block_feerates, h=h, oracle=oracle)
            for h in range(first_block, last_block + 1)
        ]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: create_feerates_sql_db <first_block> <last_block>")
        exit(1)
    first_block = int(sys.argv[1])
    last_block = int(sys.argv[2])
    
    oracle = BitcoindTXFeeOracle(next_oracle=None)
    
    dump_block_feerates_parallel(first_block=first_block, last_block=last_block, oracle=oracle)

"""
# After we dumped all blocks feerates, we wish to put them all in an SQLite DB:
sort --parallel=4 block_*_feerates > all_feerates_sorted.csv
# sqlite:
sqlite3 feerates.sqlite
CREATE TABLE IF NOT EXISTS "feerates" (txid TEXT PRIMARY KEY, feerate TEXT);
.mode csv
.import all_feerates_sorted.csv feerates
# check table size
select count(*) from feerates;
"""
