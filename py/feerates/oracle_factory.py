import os

import plyvel

from feerates.bitcoind_oracle import BitcoindTXFeeOracle
from feerates.level_db_oracle import LevelDBTXFeeOracle
from feerates.tx_fee_oracle import TXFeeOracle

ln = os.path.expandvars("$LN")
DB_FOLDER = "/cs/labs/avivz/jonahar/bitcoin-datadir/feerates"
SQLITE_DB_FILEPATH = os.path.join(DB_FOLDER, "feerates.sqlite")
FEERATES_LEVELDB_FILEPATH = os.path.join(DB_FOLDER, "feerates_leveldb")
F_VALUES_LEVELDB_FILEPATH = os.path.join(DB_FOLDER, "f_values_leveldb")

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


def get_f_values_db() -> plyvel.DB:
    return plyvel.DB(F_VALUES_LEVELDB_FILEPATH, create_if_missing=True)
