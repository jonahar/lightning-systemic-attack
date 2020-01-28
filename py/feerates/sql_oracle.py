import sqlite3
from typing import Optional

from datatypes import FEERATE, TXID
from feerates.tx_fee_oracle import TXFeeOracle


class SQLTXFeeOracle(TXFeeOracle):
    def __init__(self, db_filepath: str, next_oracle: TXFeeOracle) -> None:
        super().__init__(next_oracle=next_oracle)
        self.sql_conn = sqlite3.connect(db_filepath)
        self.sql_cursor = self.sql_conn.cursor()
    
    def _get_tx_feerate_from_self(self, txid: TXID) -> Optional[FEERATE]:
        self.sql_cursor.execute("SELECT feerate FROM feerates WHERE txid=(?)", [txid])
        res = self.sql_cursor.fetchone()
        if res:
            return float(res[0])
