import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor

from bitcoin_cli import blockchain_height, get_block_by_height, get_tx_feerate, set_bitcoin_cli
from datatypes import Block, BlockHeight
from feerates import logger
from paths import DATA

MAX_WORKERS = None  # will be set by the executor according to number of CPUs

TSV_SEPARATOR = "\t"


def __dump_block_feerates_to_file(h: BlockHeight, filepath: str) -> bool:
    """
    helper for dump_block_feerates. write feerates of txs in block h to a file in the given path.
    returns true only if ALL feerates were successfully written to the file.
    """
    try:
        block: Block = get_block_by_height(h)
    except Exception:
        # TODO change this except. get_block_by_height should either declare
        #  exactly what it raises, or return None if it fails
        logger.error(f"Failed to retrieve block {h} from bitcoind")
        return False
    
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    # submit all jobs to the pool
    txid_to_future = {
        txid: executor.submit(get_tx_feerate, txid)
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
            
            f.write(f"{txid}{TSV_SEPARATOR}{feerate}\n")
    
    executor.shutdown(wait=True)
    return True


def dump_block_feerates(h: BlockHeight) -> None:
    """
    computes the feerate of all transactions in block at height h and dump them
    to a text file in the DB_FOLDER directory
    """
    logger.info(f"Dumping feerates for block {h}")
    filepath = os.path.join(DATA, "feerates_tsv_files", f"block_{h}_feerates.tsv")
    if os.path.isfile(filepath):
        return  # this block was already dumped
    
    # use tmp suffix until we finish with that block (in case we crash before we dumped all txs)
    filepath_tmp = f"{filepath}.tmp"
    success = __dump_block_feerates_to_file(h=h, filepath=filepath_tmp)
    if success:
        os.rename(filepath_tmp, filepath)
    else:
        logger.error(f"Failed to retrieve feerate for a transaction in block {h}")


def dump_blocks_feerates(first_block: int, last_block: int) -> None:
    for h in range(first_block, last_block + 1):
        dump_block_feerates(h=h)


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
    
    set_bitcoin_cli(args.bitcoin_cli)
    
    if args.last_block != 0:
        dump_blocks_feerates(first_block=args.first_block, last_block=args.last_block)
    else:
        # we dump all blocks from first_block to the current height, indefinitely
        while True:
            curr_height = blockchain_height()
            logger.info(
                f"Dumping all blocks from height {args.first_block} to current blockchain height ({curr_height})"
            )
            dump_blocks_feerates(first_block=args.first_block, last_block=curr_height)
            logger.info("sleeping for 5 minutes")
            time.sleep(60 * 5)
            # we may change first_block to curr_height, but we're leaving this
            # as it is in case some of the blocks failed in the last attempt

# ----------


"""
# After we dump all feerates, we wish to create DB with all, for quick access.

# create tsv file with all of the data
time sort --parallel=16 block_*_feerates.tsv > all_feerates_sorted.tsv


# build SQLite:
sqlite3 feerates.sqlite
> CREATE TABLE IF NOT EXISTS "feerates" (txid TEXT PRIMARY KEY, feerate TEXT);
> .mode tabs
> .import all_feerates_sorted.tsv feerates
> select count(*) from feerates; -- check table size


# build LevelDB:
# to quickly build the db we use ldbsh: https://github.com/kanosaki/ldbsh
ldbsh feerates_leveldb
> load all_feerates_sorted.tsv
"""
