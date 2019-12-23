import json
import os
from functools import reduce
from typing import Callable, Dict, Iterable, List, Mapping

import networkx as nx
from networkx.algorithms.traversal.breadth_first_search import bfs_edges
from networkx.classes.digraph import DiGraph

from datatypes import BTC, Block, BlockHash, BlockHeight, TX, TXID, btc_to_satoshi


class TransactionDB:
    
    def __init__(self, datadir: str) -> None:
        self.datadir = datadir
        self.blocks: Dict[BlockHash, Block] = self.__load_blocks()
        self.txs: Dict[TXID, TX] = self.__load_txs()
        self.__add_fee_to_tx_data()
        self.__txs_graph: DiGraph = self.__build_txs_graph()
        self.__height_to_txids: Dict[BlockHeight, List[TXID]] = self.__build_height_to_txids_map()
    
    @property
    def height_to_txids(self) -> Dict[BlockHeight, List[TXID]]:
        return self.__height_to_txids
    
    @property
    def full_txs_graph(self) -> DiGraph:
        return self.__txs_graph
    
    def __load_blocks(self) -> Dict[BlockHash, Block]:
        blocks = {}
        for filename in os.listdir(self.datadir):
            if filename.startswith("block_"):
                with open(os.path.join(self.datadir, filename)) as f:
                    d = json.load(f)
                    blocks[d["hash"]] = d
        
        return blocks
    
    def __load_txs(self) -> Dict[TXID, TX]:
        txs = {}
        for filename in os.listdir(self.datadir):
            if filename.startswith("tx_"):
                with open(os.path.join(self.datadir, filename)) as f:
                    d = json.load(f)
                    txs[d["txid"]] = d
        
        return txs
    
    def get_tx_incoming_value(self, txid: TXID) -> float:
        return sum(
            self.txs[src_entry["txid"]]["vout"][src_entry["vout"]]["value"]
            for src_entry in self.txs[txid]["vin"] if "coinbase" not in src_entry
        )
        # this is equivalent to
        # value = 0
        # for entry in self.txs[txid]["vin"]:
        #     if "coinbase" in entry:
        #         continue  # coinbase transaction. no fee
        #     src_txid = entry["txid"]
        #     index = entry["vout"]
        #     value += self.txs[src_txid]["vout"][index]["value"]
        # return value
    
    def get_tx_outgoing_value(self, txid: TXID) -> float:
        return sum(
            entry["value"]
            for entry in self.txs[txid]["vout"]
        )
    
    def get_tx_fee(self, txid: TXID) -> BTC:
        return self.get_tx_incoming_value(txid) - self.get_tx_outgoing_value(txid)
    
    def __add_fee_to_tx_data(self) -> None:
        for txid, tx in self.txs.items():
            if "coinbase" in tx["vin"][0]:
                continue  # don't include fee for coinbase transaction
            tx["fee"] = self.get_tx_fee(txid)
    
    def __build_txs_graph(self) -> DiGraph:
        """
        return a directed graph with all transactions as nodes, and an edge between
        tx X to tx Y if Y spends an output from X. each edge has a 'value' attribute
        which is the value of the spent output
        """
        txs_graph = nx.DiGraph()
        
        # add all transactions
        for txid in self.txs.keys():
            txs_graph.add_node(txid, tx=self.txs[txid])
        
        # add edges between transactions
        for dest_txid, dest_tx in self.txs.items():
            for entry in dest_tx["vin"]:
                if "coinbase" in entry:
                    continue  # coinbase transaction. no src
                src_txid = entry["txid"]
                index = entry["vout"]
                value = self.txs[src_txid]["vout"][index]["value"]
                txs_graph.add_edge(src_txid, dest_txid, value=value)
        
        return txs_graph
    
    def transactions_sub_graph(self, sources: Iterable[TXID]) -> DiGraph:
        """
        return a directed graph that contains the given transactions and
        all their children
        """
        # for each source, compute the set of its children. then reduce all by union
        children = reduce(
            lambda s1, s2: s1.union(s2),
            ({u for v, u in bfs_edges(self.__txs_graph, source=src)} for src in sources)
        )
        all_nodes = children.union(sources)
        return self.__txs_graph.subgraph(nodes=all_nodes)
    
    def __build_height_to_txids_map(self) -> Dict[BlockHeight, List[TXID]]:
        """
        return a mapping from block height to the transactions in this block.
        the returned mapping includes only blocks with more than 1
        transaction (i.e. at least one non-coinbase transaction)
        """
        return {
            block["height"]: block["tx"]
            for block in self.blocks.values()
            if len(block["tx"]) > 1
        }


def export_tx_graph_to_dot(
    g: DiGraph,
    dotfile: str,
    height_to_txids: Mapping[BlockHeight, Iterable[TXID]],
    txid_to_label: Callable[[TXID], str],
) -> None:
    # https://www.graphviz.org/Documentation/TSE93.pdf
    with open(dotfile, mode="w") as f:
        f.write("digraph shells {\n")
        f.write("node [fontsize=20, shape = box];\n")
        
        # mark nodes that should be in the same level
        txid_to_wrapped_label = lambda txid: f"\"{txid_to_label(txid)}\""
        for height, txids in height_to_txids.items():
            f.write("{ rank = same; ")
            f.write(" ".join(map(txid_to_wrapped_label, txids)))
            f.write(f" \"{height}\" ")
            f.write("; }\n")
        
        for u, v, data in g.edges(data=True):
            value: BTC = data["value"]
            f.write(
                f""" "{txid_to_label(u)}" -> "{txid_to_label(v)}" [ label = "{btc_to_satoshi(value)}" ];\n"""
            )
        
        # ’invisible’ edges between height nodes so they are aligned
        f.write("edge [style=invis];\n")
        f.write(" -> ".join(map(str, sorted(height_to_txids.keys()))))
        f.write(";\n")
        f.write("}\n")


ln = os.path.expandvars("$LN")
datadir = os.path.join(ln, "simulations/datadir")
funding_txids = {
    "",
    "",
}

db = TransactionDB(datadir=datadir)

txs_graph = db.transactions_sub_graph(sources=funding_txids)

dotfile = os.path.join(ln, "txs_graph.dot")

txid_to_label = lambda txid: f"id={txid[-4:]}; fee={btc_to_satoshi(db.get_tx_fee(txid))}"
export_tx_graph_to_dot(
    g=txs_graph,
    dotfile=dotfile,
    height_to_txids=db.height_to_txids,
    txid_to_label=txid_to_label,
)
