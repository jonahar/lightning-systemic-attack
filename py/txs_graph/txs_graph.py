from typing import Any, Iterable, List

from networkx.algorithms.traversal.breadth_first_search import bfs_edges
from networkx.classes.digraph import DiGraph

from datatypes import TXID
from txs_graph.txs_graph_utils import find_tx_fee, load_blocks, load_txs


class TxsGraph(DiGraph):
    
    @staticmethod
    def from_datadir(datadir: str) -> "TxsGraph":
        """
        read all block and transaction files in the given datadir and construct
        a full transaction graph.
        
        Each node represents a transaction. the node's id is the txid and it has
        the following attributes:
            - "tx" - the full tx json, as returned by bitcoind
            - "fee" - the tx fee
            - "height" - the block height in which the tx was included
        
        Each edge has the following attributes:
            - "value" the value in BTC of the output represented by this edge
            
        """
        blocks = load_blocks(datadir)
        txs = load_txs(datadir)
        
        txid_to_fee = {txid: find_tx_fee(txid, txs) for txid in txs.keys()}
        txid_to_height = {
            txid: block["height"]
            for block in blocks.values()
            for txid in block["tx"]
        }
        
        graph = TxsGraph()
        
        # add all transactions
        for txid in txs.keys():
            graph.add_node(txid, tx=txs[txid], fee=txid_to_fee[txid], height=txid_to_height[txid])
        
        # add edges between transactions
        for dest_txid, dest_tx in txs.items():
            for entry in dest_tx["vin"]:
                if "coinbase" in entry:
                    continue  # coinbase transaction. no src
                src_txid = entry["txid"]
                index = entry["vout"]
                value = txs[src_txid]["vout"][index]["value"]
                graph.add_edge(src_txid, dest_txid, value=value)
        
        return graph
    
    def get_all_direct_children(self, txid: TXID) -> List[TXID]:
        return [txid for _, txid in self.out_edges(txid)]
    
    def get_minimal_nsequence(self, txid: TXID) -> int:
        """
        return the minimal nsequence of an input in the given txid
        """
        return min(map(
            lambda input_dict: input_dict['sequence'],
            self.nodes[txid]["tx"]["vin"]
        ))
    
    def is_replaceable_by_fee(self, txid: TXID) -> bool:
        return self.get_minimal_nsequence(txid) < (0xffffffff - 1)
    
    def get_downstream(self, sources: Iterable[Any]) -> "TxsGraph":
        """
        return the downstream of sources in the given graph.
        sources must be an iterable of existing node ids in the graph
        """
        sources = list(sources)  # sources may be iterable only once (e.g. map), so we copy
        
        downstream = TxsGraph()
        downstream.add_nodes_from(
            map(lambda src: (src, self.nodes[src]), sources)
        )
        for src in sources:
            for v, u in bfs_edges(self, source=src):
                downstream.add_node(v, **self.nodes[v])
                downstream.add_node(u, **self.nodes[u])
                downstream.add_edge(v, u, **self.edges[(v, u)])
        
        return downstream
