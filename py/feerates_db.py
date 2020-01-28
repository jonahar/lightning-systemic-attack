import os
import sqlite3
import sys

from bitcoin_cli import get_block_by_height, get_tx_feerate
from datatypes import Block, BlockHeight, FEERATE, TXID
from utils import setup_logging

ln = os.path.expandvars("$LN")

DB_FOLDER = "/cs/labs/avivz/jonahar/bitcoin-datadir/feerates"
DB_FILEPATH = os.path.join(ln, "feerates.sqlite")

logger = setup_logging(logger_name="feerates_db_logger", filename="feerates_db.log")


class TXFeeOracle:
    """
    an object for retrieving tx feerate. It reads feerates from the feerates DB,
    if exist, or talks to bitcoind if not
    """
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILEPATH)
        self.c = self.conn.cursor()
    
    def get_tx_feerate(self, txid: TXID) -> FEERATE:
        self.c.execute("SELECT feerate FROM feerates WHERE txid=(?)", [txid])
        res = self.c.fetchone()
        if res:
            return float(res[0])
        return get_tx_feerate(txid)


def dump_block_feerates(h: BlockHeight) -> None:
    filepath = os.path.join(DB_FOLDER, f"block_{h}_feerates")
    # use tmp suffix until we finish with that block (in case this crashes before we dumped all txs)
    filepath_tmp = f"{DB_FOLDER}.tmp"
    with open(filepath_tmp, mode="w") as f:
        block: Block = get_block_by_height(h)
        # we dump all transactions, including coinbase
        for txid in block["tx"]:
            f.write(f"{txid},{get_tx_feerate(txid)}\n")
    
    os.rename(filepath_tmp, filepath)


def dump_block_feerates_serial(first_block: int, last_block: int) -> None:
    for h in range(first_block, last_block + 1):
        try:
            logger.info(f"Dumping feerates for block {h}")
            dump_block_feerates(h)
        except Exception as e:
            logger.exception(f"Failed to dump feerates for block {h}: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: feerates_db <first_block> <last_block>")
        exit(1)
    first_block, last_block = sys.argv[1:]
    dump_block_feerates_serial(first_block=first_block, last_block=last_block)

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
