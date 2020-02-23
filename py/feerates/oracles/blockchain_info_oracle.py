import http.client
from typing import Optional

from bitcoin_cli import (
    get_transaction, )
from datatypes import FEERATE, TXID
from feerates import logger
from feerates.oracles.tx_fee_oracle import TXFeeOracle


class BlockchainInfoTXFeeOracle(TXFeeOracle):
    def __init__(self, next_oracle: Optional[TXFeeOracle]):
        super().__init__(next_oracle=next_oracle)
    
    def _get_tx_feerate_from_self(self, txid: TXID) -> Optional[FEERATE]:
        try:
            conn = http.client.HTTPSConnection("blockchain.info")
            conn.request("GET", f"/q/txfee/{txid}")
            r = conn.getresponse()
            if r.status == 200:
                fee_satoshi = int(r.read().decode("utf-8"))
                tx_size = get_transaction(txid)["size"]
                return fee_satoshi / tx_size
        except ValueError as e:
            logger.exception(f"Failed to retrieve tx fee from blockchain.info: {e}")
            return None

# There is also this option:
# feerate_regex = re.compile("(\d+(\.\d+)?)\s+sat/B")
# conn = http.client.HTTPSConnection("www.blockchain.com")
# conn.request("GET", f"/btc/tx/{txid}")
# r = conn.getresponse()
# if r.status == 200:
#     data = r.read().decode("utf-8")
#     m = self.feerate_regex.search(data)
#     feerate = float(m.group(1))
#     return feerate
