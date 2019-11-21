from collections import defaultdict
from typing import Dict, List, Set, Tuple

from bitcoin_cli import get_transaction
from datatypes import TXID


class TXSet:
    
    def __init__(self, txids: Set[TXID]):
        self.graph: Dict[TXID, List[Tuple[TXID, float]]] = defaultdict(list)
        
        for txid in txids:
            transaction = get_transaction(txid)
            # go over all inputs of txid
            for entry in transaction["vin"]:
                in_txid = entry["txid"]
                idx = entry["vout"]  # the output index in in_txid
                in_txid_value = get_transaction(in_txid)["vout"][idx]["value"]
                self.graph[in_txid].append((txid, in_txid_value))
    
    def print(self):
        for txid in self.graph.keys():
            print(f"{txid}:")
            for out_txid, value in self.graph[txid]:
                print(f"    {out_txid}: {value}")
