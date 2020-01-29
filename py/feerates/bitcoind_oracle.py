from typing import Optional

import bitcoin_cli
from datatypes import FEERATE, TXID
from feerates.feerates_logger import logger
from feerates.tx_fee_oracle import TXFeeOracle


class BitcoindTXFeeOracle(TXFeeOracle):
    def __init__(self, next_oracle: Optional[TXFeeOracle]):
        super().__init__(next_oracle=next_oracle)
    
    def _get_tx_feerate_from_self(self, txid: TXID) -> Optional[FEERATE]:
        try:
            return bitcoin_cli.get_tx_feerate(txid)
        except Exception as e:
            logger.exception(f"{type(e)}: {str(e)}")
