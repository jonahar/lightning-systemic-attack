import os

from feerates.bitcoind_oracle import BitcoindTXFeeOracle
from feerates.sql_oracle import SQLTXFeeOracle
from feerates.tx_fee_oracle import TXFeeOracle
from utils import setup_logging

logger = setup_logging(logger_name="feerates_db_logger", filename="feerates_db.log")

ln = os.path.expandvars("$LN")
DB_FOLDER = "/cs/labs/avivz/jonahar/bitcoin-datadir/feerates"
DB_FILEPATH = os.path.join(DB_FOLDER, "feerates.sqlite")

# may be used by BlockchainParserTXFeeOracle
blocks_dir = "/cs/labs/avivz/jonahar/bitcoin-datadir/blocks"
index_dir = "/cs/labs/avivz/jonahar/bitcoin-datadir/blocks/index"


def get_multi_layer_oracle() -> TXFeeOracle:
    layer_1 = BitcoindTXFeeOracle(next_oracle=None)
    
    layer_0 = SQLTXFeeOracle(
        db_filepath=DB_FILEPATH,
        next_oracle=layer_1,
    )
    return layer_0
