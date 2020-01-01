import itertools
import json
import os
import re
from functools import reduce
from typing import Callable, Dict, Iterable, Set

import networkx as nx
from networkx.algorithms.traversal.breadth_first_search import bfs_edges
from networkx.classes.digraph import DiGraph

from datatypes import BTC, Block, BlockHash, TX, TXID
from utils import btc_to_satoshi


class TransactionDB:
    
    def __init__(self, datadir: str) -> None:
        self.datadir = datadir
        self.blocks: Dict[BlockHash, Block] = self.__load_blocks()
        self.txs: Dict[TXID, TX] = self.__load_txs()
        self.__add_fee_to_tx_data()
        self.__add_height_to_tx_data()
        self.__txs_graph: DiGraph = self.__build_txs_graph()
    
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
    
    def __get_tx_fee(self, txid: TXID) -> BTC:
        return self.get_tx_incoming_value(txid) - self.get_tx_outgoing_value(txid)
    
    def __add_fee_to_tx_data(self) -> None:
        """add a 'fee' attribute for each tx"""
        for txid, tx in self.txs.items():
            if "coinbase" in tx["vin"][0]:
                continue  # don't include fee for coinbase transaction
            tx["fee"] = self.__get_tx_fee(txid)
    
    def __add_height_to_tx_data(self) -> None:
        """add a 'height' attribute for each tx"""
        for block in self.blocks.values():
            for txid in block["tx"]:
                self.txs[txid]["height"] = block["height"]
    
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


def export_tx_graph_to_dot(
    g: DiGraph,
    dotfile: str,
    txid_to_label: Callable[[TXID], str],
) -> None:
    # https://www.graphviz.org/Documentation/TSE93.pdf
    with open(dotfile, mode="w") as f:
        f.write("digraph shells {\n")
        f.write("node [fontsize=20, shape = box];\n")
        
        txid_to_height = lambda txid: g.nodes[txid]["tx"]["height"]
        height_to_txids = {
            k: set(v)
            for k, v in itertools.groupby(
                sorted(g.nodes, key=txid_to_height), key=txid_to_height
            )
        }
        
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


def extract_funding_txids(simulation_outfile: str) -> Set[TXID]:
    p = re.compile("""{\\s+"tx".*?"txid".*?"channel_id".*?}""", flags=re.DOTALL)
    
    with open(simulation_outfile) as f:
        simulation_output = f.read()
    
    m = p.search(string=simulation_output)
    funding_txids = set()
    while m:
        funding_tx_json_str = m.group(0)
        funding_txid = json.loads(funding_tx_json_str)["txid"]
        funding_txids.add(funding_txid)
        m = p.search(string=simulation_output, pos=m.end())
    
    return funding_txids


def print_commitments_sizes(db: TransactionDB, funding_txids: Set[TXID]) -> None:
    for funding in funding_txids:
        successors = list(db.full_txs_graph.successors(funding))
        assert len(successors) == 1
        commitment_tx = db.full_txs_graph.nodes[successors[0]]["tx"]
        print(
            f"commitment {commitment_tx['txid'][-4:]}"
            f"\tsize={commitment_tx['size']}"
            f"\tvsize={commitment_tx['vsize']}"
            f"\tweight={commitment_tx['weight']}"
        )


ln = os.path.expandvars("$LN")
datadir = os.path.join(ln, "simulations/datadir")
outfile = os.path.join(ln, "simulations/simulation.out")

db = TransactionDB(datadir=datadir)
funding_txids = extract_funding_txids(outfile)

txs_graph = db.transactions_sub_graph(sources=funding_txids)

dotfile = os.path.join(ln, "txs_graph.dot")
txid_to_label_and_fee = (
    lambda txid: f"id={txid[-4:]}; fee={btc_to_satoshi(txs_graph.nodes[txid]['tx']['fee'])}"
)
txid_to_label = lambda txid: txid[-4:]
export_tx_graph_to_dot(
    g=txs_graph,
    dotfile=dotfile,
    txid_to_label=txid_to_label,
)
