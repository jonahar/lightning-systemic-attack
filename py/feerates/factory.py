import os

from feerates.bitcoind_oracle import BitcoindTXFeeOracle
from feerates.level_db_oracle import LevelDBTXFeeOracle
from feerates.tx_fee_oracle import TXFeeOracle

"""
This module is responsible for building feerates oracles and various DBs
"""

ln = os.path.expandvars("$LN")
DB_FOLDER = "/cs/labs/avivz/jonahar/bitcoin-datadir/feerates"
SQLITE_DB_FILEPATH = os.path.join(DB_FOLDER, "feerates.sqlite")
FEERATES_LEVELDB_FILEPATH = os.path.join(DB_FOLDER, "feerates_leveldb")

# may be used by BlockchainParserTXFeeOracle
blocks_dir = "/cs/labs/avivz/jonahar/bitcoin-datadir/blocks"
index_dir = "/cs/labs/avivz/jonahar/bitcoin-datadir/blocks/index"


def get_multi_layer_oracle() -> TXFeeOracle:
    layer_1 = BitcoindTXFeeOracle(next_oracle=None)
    
    layer_0 = LevelDBTXFeeOracle(
        db_filepath=FEERATES_LEVELDB_FILEPATH,
        next_oracle=layer_1,
    )
    return layer_0
