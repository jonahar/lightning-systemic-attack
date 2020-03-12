import itertools
import os
import re
from typing import Any, Callable, Iterable, List, Set

from networkx.classes.digraph import DiGraph

from datatypes import BTC, TXID, btc_to_sat
from paths import LN
from txs_graph.txs_graph import TxsGraph


# ---------- txid-to-label functions ----------


def get_txid_to_short_txid_and_fee(txs_graph: DiGraph) -> Callable[[TXID], str]:
    def txid_to_short_txid_and_fee(txid: TXID) -> str:
        fee = btc_to_sat(txs_graph.nodes[txid]['tx']['fee'])
        return f"{txid[-4:]}; fee={fee}"
    
    return txid_to_short_txid_and_fee


def txid_to_short_txid(txid: TXID) -> str:
    return txid[-4:]


def export_txs_graph_to_dot(
    graph: DiGraph,
    dotfile: str,
    txid_to_label: Callable[[TXID], str],
) -> None:
    # https://www.graphviz.org/Documentation/TSE93.pdf
    with open(dotfile, mode="w") as f:
        f.write("digraph shells {\n")
        f.write("node [fontsize=20, shape = box];\n")
        
        txid_to_height = lambda txid: graph.nodes[txid]["height"]
        height_to_txids = {
            k: set(v)
            for k, v in itertools.groupby(
                sorted(graph.nodes, key=txid_to_height), key=txid_to_height
            )
        }
        
        # mark nodes that should be in the same level
        txid_to_wrapped_label = lambda txid: f"\"{txid_to_label(txid)}\""
        for height, txids in height_to_txids.items():
            f.write("{ rank = same; ")
            f.write(" ".join(map(txid_to_wrapped_label, txids)))
            f.write(f" \"{height}\" ")
            f.write("; }\n")
        
        for u, v, data in graph.edges(data=True):
            value: BTC = data["value"]
            f.write(
                f""" "{txid_to_label(u)}" -> "{txid_to_label(v)}" [ label = "{btc_to_sat(value)}" ];\n"""
            )
        
        # ’invisible’ edges between height nodes so they are aligned
        f.write("edge [style=invis];\n")
        f.write(" -> ".join(map(str, sorted(height_to_txids.keys()))))
        f.write(";\n")
        f.write("}\n")


def extract_bitcoin_funding_txids(simulation_outfile: str) -> Set[TXID]:
    """
    return the set of txs that funded the different nodes.
    These are the txs in which the miner node sent the initial balance for each
    lightning node
    """
    FUNDING_INFO_LINE = "funding lightning nodes"
    txid_regex = re.compile("[0-9A-Fa-f]{64}")
    
    txids = set()
    with open(simulation_outfile) as f:
        line = f.readline().strip()
        while line is not None and line != FUNDING_INFO_LINE:
            line = f.readline().strip()
        
        if line is None:
            raise ValueError("Couldn't find funding rows in the given file. is file in bad format?")

        line = f.readline().strip()
        while txid_regex.fullmatch(line):
            txids.add(line)
            line = f.readline().strip()
    
    return txids


def flatten(s: Iterable[Iterable[Any]]) -> List[Any]:
    return list(itertools.chain.from_iterable(s))


def find_commitments(simulation_outfile: str, graph: TxsGraph) -> List[TXID]:
    bitcoin_fundings = extract_bitcoin_funding_txids(simulation_outfile=simulation_outfile)
    
    ln_channel_fundings = flatten(
        graph.get_all_direct_children(txid)
        for txid in bitcoin_fundings
    )
    
    LN_CHANNEL_BALANCE = 0.1
    
    commitments = flatten(
        list(filter(
            # only keep those with the expected balance
            lambda child_txid: graph.edges[(channel_funding_txid, child_txid)]["value"] == LN_CHANNEL_BALANCE,
            graph.get_all_direct_children(txid=channel_funding_txid)
        ))
        for channel_funding_txid in ln_channel_fundings
    )
    
    # verifications
    if len(ln_channel_fundings) != len(commitments):
        raise ValueError(
            "Failed to find commitments."
            "number of commitment txs found doesn't correspond to number of funding txs found"
        )
    
    for commitment_txid in commitments:
        num_inputs = len(graph.nodes[commitment_txid]["tx"]["vin"])
        if len(graph.nodes[commitment_txid]["tx"]["vin"]) != 1:
            raise ValueError(
                f"Failed to find commitments. "
                f"txid {commitment_txid[-4:]} expected to have exactly 1 input, but has {num_inputs}"
            )
    
    return commitments


def get_htlcs_claimed_by_timeout(graph: TxsGraph, commitment_txid: TXID) -> List[TXID]:
    """
    return a list of txids that claimed an HTLC output from the given
    commitment transaction, using timeout-claim (as opposed to success-claim)
    """
    
    # from the bolt:
    # " HTLC-Timeout and HTLC-Success Transactions... are almost identical,
    #   except the HTLC-timeout transaction is timelocked "
    #
    # i.e. if the child_tx has a non-zero locktime, it is an HTLC-timeout
    # TODO: what about claiming of local/remote outputs? are they locked? check it
    
    return [
        child_tx
        for _, child_tx in graph.out_edges(commitment_txid)
        if graph.nodes[child_tx]["tx"]["locktime"] > 0
    ]


def main(simulation_name):
    print(f"analyzing {simulation_name}")
    datadir = os.path.join(LN, "simulations", simulation_name)
    outfile = os.path.join(LN, "simulations", f"{simulation_name}.out")
    dotfile = os.path.join(LN, f"{simulation_name}.dot")
    jpgfile = os.path.join(LN, f"{simulation_name}.jpg")

    txs_graph = TxsGraph.from_datadir(datadir)
    
    commitments = find_commitments(simulation_outfile=outfile, graph=txs_graph)
    
    for commitment_txid in commitments:
        short_txid = txid_to_short_txid(commitment_txid)
        num_outputs = len(txs_graph.nodes[commitment_txid]["tx"]["vout"])
        replaceable = txs_graph.is_replaceable_by_fee(txid=commitment_txid)
        nsequence = txs_graph.get_minimal_nsequence(commitment_txid)
        num_htlcs_stolen = len(get_htlcs_claimed_by_timeout(graph=txs_graph, commitment_txid=commitment_txid))
        print(
            f"commitment: {short_txid:<5} "
            f"num-outputs: {num_outputs:<4} "
            f"replaceable: {str(replaceable):<5} "
            f"nsequence: {nsequence:x}  "
            f"htlcs-stolen: {num_htlcs_stolen}"
        )
    
    # this graph includes only interesting txs (no coinbase and other junk)
    restricted_txs_graph = txs_graph.get_downstream(
        sources=extract_bitcoin_funding_txids(simulation_outfile=outfile),
    )
    
    export_txs_graph_to_dot(
        graph=restricted_txs_graph,
        dotfile=dotfile,
        txid_to_label=txid_to_short_txid,
    )
    # convert dot to jpg
    os.system(f"cd {LN}; dot2jpg {dotfile} {jpgfile}")


if __name__ == "__main__":
    main(simulation_name="simulation-name")
