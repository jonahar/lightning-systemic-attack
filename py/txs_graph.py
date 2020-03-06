import json
import os
from typing import Any, Dict, Iterable

from networkx.algorithms.traversal.breadth_first_search import bfs_edges
from networkx.classes.digraph import DiGraph

from datatypes import BTC, Block, BlockHash, TX, TXID


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


def get_tx_incoming_value(txid: TXID, txs: Dict[TXID, TX]) -> BTC:
    return sum(
        txs[src_entry["txid"]]["vout"][src_entry["vout"]]["value"]
        for src_entry in txs[txid]["vin"] if "coinbase" not in src_entry
    )


def get_tx_outgoing_value(txid: TXID, txs: Dict[TXID, TX]) -> BTC:
    return sum(
        entry["value"]
        for entry in txs[txid]["vout"]
    )


def find_tx_fee(txid: TXID, txs: Dict[TXID, TX]) -> BTC:
    """
    return the fee paid by the given txid
    """
    our_tx = txs[txid]
    if "coinbase" in our_tx["vin"][0]:
        return 0
    
    return get_tx_incoming_value(txid, txs=txs) - get_tx_outgoing_value(txid, txs=txs)


def build_txs_graph(datadir: str) -> DiGraph:
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
    
    graph = DiGraph()
    
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


def get_downstream(graph: DiGraph, sources: Iterable[Any]) -> DiGraph:
    """
    return the downstream of sources in the given graph.
    sources must be an iterable of existing node ids in the graph
    """
    sources = list(sources)  # sources may be iterable only once (e.g. map), so we copy
    nodes_to_include = set(sources)
    
    # for each source, compute the set of its ancestors using bfs
    nodes_to_include.update(
        *({u for v, u in bfs_edges(graph, source=src)} for src in sources)
    )
    return graph.subgraph(nodes=nodes_to_include)
