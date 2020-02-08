import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor

from bitcoin_cli import blockchain_height, get_block_by_height
from datatypes import Block, BlockHeight
from feerates.bitcoind_oracle import BitcoindTXFeeOracle
from feerates.feerates_logger import logger
from feerates.oracle_factory import DB_FOLDER
from feerates.tx_fee_oracle import TXFeeOracle

MAX_WORKERS = 16


def __dump_block_feerates_to_file(h: BlockHeight, oracle: TXFeeOracle, filepath: str) -> bool:
    """
    helper for dump_block_feerates. write results to a file in the given path.
    returns true if all feerates were successfully written to the file
    """
    block: Block = get_block_by_height(h)
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    # submit all jobs to the pool
    txid_to_future = {
        txid: executor.submit(TXFeeOracle.get_tx_feerate, oracle, txid)
        for txid in block["tx"]
    }
    
    with open(filepath, mode="w") as f:
        # iterate all futures, extract the computed result and dump to the file
        for txid, future in txid_to_future.items():
            feerate = future.result()
            if feerate is None:
                # we give up on the entire block if we fail to get the feerate of at least one transaction
                # cancel all remaining jobs
                for f in txid_to_future.values():
                    f.cancel()
                executor.shutdown(wait=False)
                return False
            
            f.write(f"{txid},{feerate}\n")
    
    executor.shutdown(wait=True)
    return True


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
    success = __dump_block_feerates_to_file(h=h, oracle=oracle, filepath=filepath_tmp)
    if success:
        os.rename(filepath_tmp, filepath)
    else:
        logger.error(f"Oracle couldn't retrieve feerate for a transaction in block {h}")


def dump_blocks_feerates(first_block: int, last_block: int, oracle: TXFeeOracle) -> None:
    for h in range(first_block, last_block + 1):
        dump_block_feerates(h=h, oracle=oracle)


def parse_args():
    """
    parse and return the program arguments
    """
    parser = argparse.ArgumentParser(description='dump blocks feerates to csv files')
    parser.add_argument(
        "first_block", type=int, action="store",
        help="the first block to dump feerates for",
    )
    parser.add_argument(
        "last_block", type=int, action="store",
        help=(
            "the last block to dump feerates for. if 0 is given, dump all "
            "from first_block to the current blockchain height, indefinitely"
        ),
    )
    parser.add_argument(
        "bitcoin_cli", choices=["master", "user"], metavar="bitcoin_cli",
        help="the bitcoin-cli to use. must be one of `master` or `user`",
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    oracle = BitcoindTXFeeOracle(next_oracle=None)
    
    dump_blocks_feerates(first_block=args.first_block, last_block=args.last_block, oracle=oracle)
    
    if args.last_block != 0:
        dump_blocks_feerates(first_block=args.first_block, last_block=args.last_block, oracle=oracle)
    else:
        # we dump all blocks from first_block to the current height, indefinitely
        while True:
            curr_height = blockchain_height()
            logger.info(
                f"Dumping all blocks from height {args.first_block} to current blockchain height ({curr_height})"
            )
            dump_blocks_feerates(first_block=args.first_block, last_block=curr_height, oracle=oracle)
            logger.info("sleeping for 5 minutes")
            time.sleep(60 * 5)
            # we may change first_block to curr_height, but we're leaving this
            # as it is in case some of the blocks failed in the last attempt

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
