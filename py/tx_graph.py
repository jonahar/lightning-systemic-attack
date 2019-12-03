from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Set

from bitcoin_cli import get_transaction, get_tx_height
from datatypes import Json, TXID


@dataclass(eq=True, frozen=True)
class Output:
    idx: int  # index in vout
    dest_txid: TXID  # the transaction that spends this output
    value: float


class TXGraph:
    def __init__(self, txids: Set[TXID]) -> None:
        self.txids = txids
        self.txid_to_outputs: Dict[TXID, Set[Output]] = self.__init_txid_to_outputs()
        self.height_to_txids: Dict[int, Set[TXID]] = self.__init_height_to_txids()
    
    def __init_txid_to_outputs(self) -> Dict[TXID, Set[Output]]:
        txid_to_outputs = defaultdict(set)
        
        # 'dest' transaction spends an output produced in 'src' transaction
        for dest_txid in self.txids:
            for src_entry in self.txid_to_json(dest_txid)["vin"]:
                src_txid = src_entry["txid"]
                if src_txid not in self.txids:
                    continue  # we don't include txids that were not given explicitly
                
                idx = src_entry["vout"]
                src_tx = self.txid_to_json(src_txid)
                value = src_tx["vout"][idx]["value"]
                
                # output number 'idx' with value 'value' in src was spent by dest
                txid_to_outputs[src_txid].add(
                    Output(idx=idx, dest_txid=dest_txid, value=value)
                )
        return txid_to_outputs
    
    def __init_height_to_txids(self) -> Dict[int, Set[TXID]]:
        height_to_txids = defaultdict(set)
        for txid in self.txids:
            height = get_tx_height(txid)
            height_to_txids[height].add(txid)
        return height_to_txids
    
    tx_memo = {}
    
    @classmethod
    def txid_to_json(cls, txid: TXID) -> Json:
        # we use this method so we can later easily change the way we retrieve
        # transactions. We can either cache them all in a dict, or retrieve on demand
        if txid in TXGraph.tx_memo:
            return TXGraph.tx_memo[txid]
        TXGraph.tx_memo[txid] = get_transaction(txid)
        return TXGraph.tx_memo[txid]
    
    @classmethod
    def short_txid(cls, txid: TXID) -> str:
        return "\"" + txid[-4:] + "\""
    
    def export_to_dot(self, filepath: str) -> None:
        # https://www.graphviz.org/Documentation/TSE93.pdf
        with open(filepath, mode="w") as f:
            f.write("digraph shells {\n")
            f.write("node [fontsize=20, shape = box];\n")
            
            # mark nodes that should be in the same level
            for height, txids in self.height_to_txids.items():
                f.write("{ rank = same; ")
                f.write(" ".join(map(lambda x: TXGraph.short_txid(x), txids)))
                f.write(f" \"{height}\" ")
                f.write("; }\n")
            
            # edges
            for src_txid, dest_outputs in self.txid_to_outputs.items():
                for dest_output in dest_outputs:
                    f.write(
                        f"{TXGraph.short_txid(src_txid)}"
                        f" -> "
                        f"{TXGraph.short_txid(dest_output.dest_txid)}"
                        f" [ label = \"{dest_output.value}\" ]"
                    )
            
            # ’invisible’ edges between height nodes so they are aligned
            f.write("edge [style=invis];\n")
            f.write(" -> ".join(map(str, sorted(self.height_to_txids.keys()))))
            f.write(";\n")
            
            f.write("}\n")
