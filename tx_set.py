from collections import defaultdict
from typing import Dict, List, Set, Tuple

from bitcoin_cli import get_transaction, get_tx_height
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
    
    def export_to_gexf(self, filepath: str) -> None:
        graph = open(filepath, mode="w")
        graph.write(
            """
            <?xml version="1.0" encoding="UTF-8"?>
            <gexf xmlns="http://www.gexf.net/1.2draft" xmlns:viz="http://www.gexf.net/1.1draft/viz" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.gexf.net/1.2draft http://www.gexf.net/1.2draft/gexf.xsd" version="1.2">
            <graph mode="static" defaultedgetype="directed">
            """
        )
        graph.write('<nodes>\n')
        
        for txid in self.graph:
            # label are of the form: 4f3..af9(415)
            label = txid[:3] + ".." + txid[-3:] + f"({get_tx_height(txid)})"
            graph.write(f"""<node id="{txid}" label="{label}">\n""")
            graph.write('</node>\n')
        
        graph.write('</nodes>\n')
        graph.write('<edges>\n')
        for u in self.graph:
            for v, value in self.graph[u]:
                graph.write(f"""<edge source="{u}" target="{v}" label="{value}"/>\n""")
        
        graph.write('</edges>\n')
        graph.write('</graph>\n')
        graph.write('</gexf>\n')
        graph.close()
