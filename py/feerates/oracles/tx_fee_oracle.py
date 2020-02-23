from abc import abstractmethod
from functools import lru_cache
from typing import Optional

from datatypes import Feerate, TXID


class TXFeeOracle:
    """
    An oracle that retrieves feerates for transactions.
    Oracles can be stacked together - if an oracle is unable to retrieve the
    feerate by itself for some reason, it can consult another oracle.
    This logic is implemented in this abstract class. sub-classes should only
    implement the method that actually looks for the feerate.
    """
    
    def __init__(self, next_oracle: Optional["TXFeeOracle"]):
        self.next_oracle = next_oracle
    
    @abstractmethod
    def _get_tx_feerate_from_self(self, txid: TXID) -> Optional[Feerate]:
        pass
    
    @lru_cache(maxsize=4096)  # enough to hold transactions of an entire block
    def get_tx_feerate(self, txid: TXID) -> Optional[Feerate]:
        feerate = self._get_tx_feerate_from_self(txid)
        if feerate is None and self.next_oracle:
            feerate = self.next_oracle.get_tx_feerate(txid)
        return feerate
