import os

from feerates.blockchain_parser_oracle import BlockchainParserTXFeeOracle
from feerates.sql_oracle import SQLTXFeeOracle
from feerates.tx_fee_oracle import TXFeeOracle
from utils import setup_logging

logger = setup_logging(logger_name="feerates_db_logger", filename="feerates_db.log")

ln = os.path.expandvars("$LN")
DB_FOLDER = "/cs/labs/avivz/jonahar/bitcoin-datadir/feerates"
DB_FILEPATH = os.path.join(ln, "feerates.sqlite")

blocks_dir = "/cs/labs/avivz/jonahar/bitcoin-datadir/blocks"
index_dir = "/cs/labs/avivz/jonahar/bitcoin-datadir/blocks/index"

blockchain_parser_first_block = 613903
blockchain_parser_last_block = 614903


def get_multi_layer_oracle() -> TXFeeOracle:
    layer_1 = BlockchainParserTXFeeOracle(
        blocks_dir=blocks_dir,
        index_dir=index_dir,
        first_block=blockchain_parser_first_block,
        last_block=blockchain_parser_last_block,
        next_oracle=None,
    )
    
    layer_0 = SQLTXFeeOracle(
        db_filepath=DB_FILEPATH,
        next_oracle=layer_1,
    )
    return layer_0
