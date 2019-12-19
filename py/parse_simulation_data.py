import json
import os
from functools import reduce
from typing import Callable, Dict, Iterable, List, Mapping

import networkx as nx
from networkx.algorithms.traversal.breadth_first_search import bfs_edges
from networkx.classes.digraph import DiGraph

from datatypes import Block, BlockHash, BlockHeight, TX, TXID


def load_blocks(datadir: str) -> Dict[BlockHash, Block]:
    blocks = {}
    for filename in os.listdir(datadir):
        if filename.startswith("block_"):
            with open(os.path.join(datadir, filename)) as f:
                d = json.load(f)
                blocks[d["hash"]] = d
    
    return blocks


def load_txs(datadir: str) -> Dict[TXID, TX]:
    txs = {}
    for filename in os.listdir(datadir):
        if filename.startswith("tx_"):
            with open(os.path.join(datadir, filename)) as f:
                d = json.load(f)
                txs[d["txid"]] = d
    
    return txs


def build_txs_graph(txs: Dict[TXID, TX]) -> DiGraph:
    """
    return a directed graph with all transactions as nodes, and an edge between
    tx X to tx Y if Y spends an output from X. each edge has a 'value' attribute
    which is the value of the spent output
    """
    txs_graph = nx.DiGraph()
    
    # add all transactions
    for txid in txs.keys():
        txs_graph.add_node(txid, tx=txs[txid])
    
    # add edges between transactions
    for dest_txid, dest_tx in txs.items():
        for entry in dest_tx["vin"]:
            if "coinbase" in entry:
                continue  # coinbase transaction. no src
            src_txid = entry["txid"]
            index = entry["vout"]
            value = txs[src_txid]["vout"][index]["value"]
            txs_graph.add_edge(src_txid, dest_txid, value=value)
    
    return txs_graph


def get_all_children(g: DiGraph, root) -> set:
    """
    return a set with all nodes that are children of the given root, i.e. nodes
    that are reachable from root
    """
    children = {
        dest
        for src, dest in bfs_edges(g, source=root)
    }
    return children.union({root})


def build_height_to_txids_map(blocks: Mapping[BlockHash, Block]) -> Mapping[BlockHeight, List[TXID]]:
    """
    return a mapping from block height to the transactions in this block.
    the returned mapping includes only blocks with more than 1
    transactions (i.e. at least one non-coinbase transaction)
    """
    return {
        block["height"]: block["tx"]
        for block in blocks.values()
        if len(block["tx"]) > 1
    }


def find_tx_height(blocks: Mapping[BlockHash, Block], txid: TXID) -> BlockHeight:
    for block in blocks.values():
        if txid in block["tx"]:
            return block["height"]
    return -1


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
            value = data["value"]
            f.write(
                f""" "{txid_to_label(u)}" -> "{txid_to_label(v)}" [ label = "{value}" ];\n"""
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

blocks = load_blocks(datadir)
txs = load_txs(datadir)

txs_full_graph = build_txs_graph(txs)

# get the children of all funding txs. those are the interesting txs
children = reduce(
    lambda s1, s2: s1.union(s2),
    (get_all_children(txs_full_graph, funding_txid) for funding_txid in funding_txids)
)

txs_graph = txs_full_graph.subgraph(nodes=children)
height_to_txids = build_height_to_txids_map(blocks)

dotfile = os.path.join(ln, "txs_graph.dot")
export_tx_graph_to_dot(
    g=txs_graph,
    dotfile=dotfile,
    height_to_txids=height_to_txids,
    txid_to_label=lambda txid: txid[-4:],
)
