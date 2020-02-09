from typing import Optional

import plyvel

from datatypes import FEERATE, TXID
from feerates.tx_fee_oracle import TXFeeOracle


class LevelDBTXFeeOracle(TXFeeOracle):
    """
    A TXFeeOracle that look for feerate in an existing LevelDB database
    """
    
    def __init__(self, db_filepath: str, next_oracle: Optional[TXFeeOracle]) -> None:
        super().__init__(next_oracle=next_oracle)
        self.db = plyvel.DB(db_filepath)
    
    def _get_tx_feerate_from_self(self, txid: TXID) -> Optional[FEERATE]:
        value = self.db.get(txid.encode("utf-8"))
        if value:
            return float(value)
