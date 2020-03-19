from typing import Any, Iterable, List

from networkx.algorithms.traversal.breadth_first_search import bfs_edges
from networkx.classes.digraph import DiGraph

from datatypes import BlockHeight, TXID
from txs_graph.htlc_script import get_htlc_expiration_height, is_htlc_script
from txs_graph.txs_graph_utils import find_tx_fee, load_blocks, load_txs


class TxsGraph(DiGraph):
    
    @staticmethod
    def from_datadir(datadir: str) -> "TxsGraph":
        """
        read all block and transaction files in the given datadir and construct
        a full transaction graph.
        
        Args:
            datadir: path to a data dir, that contains block and tx json files
        
        Each node represents a transaction. the node's id is the txid and it has
        the following attributes:
            - "tx":     the full tx json, as returned by bitcoind
            - "fee":    the tx fee
            - "height": the block height in which the tx was included, or None if
                        the tx was not included in any block (e.g. mempool tx)
        
        Each edge has the following attributes:
            - "value": the value in BTC of the output represented by this edge
            - "index": the index of the spent output in the source transaction

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
            graph.add_node(
                txid,
                tx=txs[txid],
                fee=txid_to_fee[txid],
                height=txid_to_height.get(txid, None),
            )
        
        # add edges between transactions
        for dest_txid, dest_tx in txs.items():
            for entry in dest_tx["vin"]:
                if "coinbase" in entry:
                    continue  # coinbase transaction. no src
                src_txid = entry["txid"]
                index = entry["vout"]
                value = txs[src_txid]["vout"][index]["value"]
                graph.add_edge(src_txid, dest_txid, value=value, index=index)
        
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
    
    def is_htlc_claim_tx(self, txid: TXID) -> bool:
        vin = self.nodes[txid]["tx"]["vin"]
        if len(vin) != 1:
            # an htlc-claim tx should have a single input, which is the commitment
            return False
        
        script_hex = vin[0]["txinwitness"][-1]
        return is_htlc_script(script_hex)
    
    def get_minimal_htlc_expiration_height(self, commitment_txid: TXID) -> BlockHeight:
        """
        return the minimal expiration height of an htlc in the given commitment tx.
        if no htlcs were found, return 0
        """
        res = 0xffffff  # the maximal value for a 3-byte int (cltv_expiry is 3-bytes)
        for _, txid in self.out_edges(commitment_txid):
            if self.is_htlc_claim_tx(txid):
                vin = self.nodes[txid]["tx"]["vin"]
                script_hex = vin[0]["txinwitness"][-1]
                exp_time = get_htlc_expiration_height(script_hex)
                res = min(res, exp_time)
        
        if res == 0xffffff:
            res = 0
        return res
