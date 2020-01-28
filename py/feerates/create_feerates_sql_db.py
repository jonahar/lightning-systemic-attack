import os
import sys

from bitcoin_cli import get_block_by_height
from datatypes import Block, BlockHeight
from feerates.blockchain_parser_oracle import BlockchainParserTXFeeOracle
from feerates.feerates_logger import logger
from feerates.oracle_factory import DB_FOLDER, blocks_dir, index_dir
from feerates.tx_fee_oracle import TXFeeOracle


def dump_block_feerates(h: BlockHeight, oracle: TXFeeOracle) -> None:
    filepath = os.path.join(DB_FOLDER, f"block_{h}_feerates")
    if os.path.isfile(filepath):
        return  # this block was already dumped
    
    # use tmp suffix until we finish with that block (in case this crashes before we dumped all txs)
    filepath_tmp = f"{filepath}.tmp"
    with open(filepath_tmp, mode="w") as f:
        block: Block = get_block_by_height(h)
        # we dump all transactions, including coinbase
        for txid in block["tx"]:
            f.write(f"{txid},{oracle.get_tx_feerate(txid)}\n")
    
    os.rename(filepath_tmp, filepath)


def dump_block_feerates_serial(first_block: int, last_block: int, oracle: TXFeeOracle) -> None:
    for h in range(first_block, last_block + 1):
        try:
            logger.info(f"Dumping feerates for block {h}")
            dump_block_feerates(h=h, oracle=oracle)
        except Exception as e:
            logger.exception(f"Failed to dump feerates for block {h}: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: create_feerates_sql_db <first_block> <last_block>")
        exit(1)
    first_block = int(sys.argv[1])
    last_block = int(sys.argv[2])
    
    oracle = BlockchainParserTXFeeOracle(
        blocks_dir=blocks_dir,
        index_dir=index_dir,
        first_block=first_block - 1000,  # we load 1000 more blocks before the first block, to save time
        last_block=last_block
    )
    
    dump_block_feerates_serial(first_block=first_block, last_block=last_block, oracle=oracle)

"""
# After we dumped all blocks feerates, we wish to put them all in an SQLite DB:
sort block_*_feerates > all_feerates_sorted.csv
# sqlite:
sqlite3 feerates.sqlite
CREATE TABLE IF NOT EXISTS "feerates" (txid TEXT PRIMARY KEY, feerate TEXT);
.mode csv
.import all_feerates_sorted.csv feerates
# check table size
select count(*) from feerates;
"""
