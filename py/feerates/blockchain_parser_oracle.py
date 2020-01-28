from typing import Dict, Optional

from bitcoin_cli import (
    get_transaction, get_tx_feerate, get_tx_incoming_value,
    get_tx_outgoing_value,
)
from blockchain_parser.blockchain import Blockchain
from blockchain_parser.transaction import Transaction
from datatypes import FEERATE, SATOSHI, TXID, btc_to_sat
from feerates.tx_fee_oracle import TXFeeOracle


class BlockchainParserTXFeeOracle(TXFeeOracle):
    def __init__(
        self,
        blocks_dir: str,
        index_dir: str,
        first_block: int,
        last_block: int = 0,
        next_oracle: Optional[TXFeeOracle] = None,
    ) -> None:
        super().__init__(next_oracle=next_oracle)
        blockchain = Blockchain(blocks_dir)
        blocks_gen = blockchain.get_ordered_blocks(
            index=index_dir,
            start=first_block,
            end=last_block,
        )
        
        self.TXS: Dict[TXID, Transaction] = {}
        for block in blocks_gen:
            for tx in block.transactions:
                self.TXS[tx.txid] = tx
    
    def __get_output_value(self, txid: TXID, idx: int) -> SATOSHI:
        if txid in self.TXS:
            return self.TXS[txid].outputs[idx].value
        tx = get_transaction(txid)
        return btc_to_sat(tx["vout"][idx]["value"])
    
    def __get_tx_outgoing_value(self, txid: TXID) -> SATOSHI:
        if txid in self.TXS:
            sum(
                output.value
                for output in self.TXS[txid].outputs
            )
        
        return btc_to_sat(get_tx_outgoing_value(txid))
    
    def __get_tx_incoming_value(self, txid: TXID) -> SATOSHI:
        if txid in self.TXS:
            return sum(
                self.__get_output_value(
                    txid=input.transaction_hash,
                    idx=input.transaction_index,
                )
                for input in self.TXS[txid].inputs
            )
        
        return btc_to_sat(get_tx_incoming_value(txid))
    
    def _get_tx_feerate_from_self(self, txid: TXID) -> FEERATE:
        if txid in self.TXS:
            tx = self.TXS[txid]
            if hasattr(tx, "feerate"):
                # we already computed the feerate for that tx
                return tx.feerate
            incoming_value = self.__get_tx_incoming_value(txid)
            outgoing_value = self.__get_tx_outgoing_value(txid)
            fee = incoming_value - outgoing_value
            feerate: FEERATE = fee / tx.size
            tx.feerate = feerate  # save for future calls
            return feerate
        
        return get_tx_feerate(txid)
