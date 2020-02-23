import sqlite3
from typing import Optional

from datatypes import FEERATE, TXID
from feerates.oracles.tx_fee_oracle import TXFeeOracle


class SQLTXFeeOracle(TXFeeOracle):
    """
    A TXFeeOracle that look for feerate in an existing SQLite database.
    The assumption is that the DB contains a table named `feerates` with
    columns `txid` and `feerate`
    """
    
    def __init__(self, db_filepath: str, next_oracle: Optional[TXFeeOracle]) -> None:
        super().__init__(next_oracle=next_oracle)
        self.sql_conn = sqlite3.connect(db_filepath)
        self.sql_cursor = self.sql_conn.cursor()
    
    def _get_tx_feerate_from_self(self, txid: TXID) -> Optional[FEERATE]:
        self.sql_cursor.execute("SELECT feerate FROM feerates WHERE txid=(?)", [txid])
        res = self.sql_cursor.fetchone()
        if res:
            return float(res[0])
