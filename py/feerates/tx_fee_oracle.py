from abc import abstractmethod
from typing import Optional

from datatypes import FEERATE, TXID


class TXFeeOracle:
    def __init__(self, next_oracle: "TXFeeOracle"):
        self.next_oracle = next_oracle
    
    @abstractmethod
    def _get_tx_feerate_from_self(self, txid: TXID) -> Optional[FEERATE]:
        pass
    
    def get_tx_feerate(self, txid: TXID) -> Optional[FEERATE]:
        feerate = self._get_tx_feerate_from_self(txid)
        if feerate is None and self.next_oracle:
            feerate = self.next_oracle.get_tx_feerate(txid)
        return feerate
