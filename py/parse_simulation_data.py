import itertools
import os
import re
import sys
from collections import defaultdict
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, List, Set

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator

from datatypes import BTC, TXID, btc_to_sat
from paths import SIMULATIONS_DIR
from txs_graph.txs_graph import TxsGraph
from utils import setup_logging

GRAPH_FILE = "num-victims-vs-stolen-htlcs.png"
log = setup_logging()


def get_txid_to_short_txid_and_fee(txs_graph: TxsGraph) -> Callable[[TXID], str]:
    def txid_to_short_txid_and_fee(txid: TXID) -> str:
        fee = btc_to_sat(txs_graph.nodes[txid]['tx']['fee'])
        return f"{txid[-4:]}; fee={fee}"
    
    return txid_to_short_txid_and_fee


def txid_to_short_txid(txid: TXID) -> str:
    return txid[-4:]


def export_txs_graph_to_dot(
    graph: TxsGraph,
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


def get_htlc_claims(
    txs_graph: TxsGraph,
    commitment_txid: TXID,
    include_unconfirmed: bool = False,
) -> List[TXID]:
    """
    return a list of txids that spend an HTLC output from the given
    commitment transaction.
    if include_unconfirmed is True, the result includes transactions that were published
    but not included in a block
    """
    return [
        child_tx
        for _, child_tx in txs_graph.out_edges(commitment_txid)
        if (
            # we want to include it
            (txs_graph.nodes[child_tx]["height"] is not None or include_unconfirmed)
            and
            # it really spends an HTLC output
            txs_graph.is_htlc_claim_tx(child_tx)
        )
    ]


def get_timeout_htlc_claims(
    txs_graph: TxsGraph,
    commitment_txid: TXID,
    include_unconfirmed: bool = False,
) -> List[TXID]:
    """
    return a list of txids that spend an HTLC output from the given
    commitment transaction, using the timeout-path of the HTLC script
    
    include_unconfirmed has the same effect as defined in get_htlc_claims
    """
    # from the bolt:
    # " HTLC-Timeout and HTLC-Success Transactions... are almost identical,
    #   except the HTLC-timeout transaction is timelocked
    #   ...
    #   locktime: 0 for HTLC-success, cltv_expiry for HTLC-timeout
    #   "
    #
    # i.e. if the child_tx has a non-zero locktime, it is an HTLC-timeout
    
    return list(
        filter(
            lambda txid: txs_graph.nodes[txid]["tx"]["locktime"] > 0,
            get_htlc_claims(txs_graph, commitment_txid, include_unconfirmed),
        )
    )


def get_success_htlc_claims(
    txs_graph: TxsGraph,
    commitment_txid: TXID,
    include_unconfirmed: bool = False,
) -> List[TXID]:
    """
    return a list of txids that spend an HTLC output from the given
    commitment transaction, using the success-path of the HTLC script.
    
    include_unconfirmed has the same effect as defined in get_htlc_claims
    """
    return list(
        filter(
            lambda txid: txs_graph.nodes[txid]["tx"]["locktime"] == 0,
            get_htlc_claims(txs_graph, commitment_txid, include_unconfirmed),
        )
    )


def get_stolen_htlc_num(txs_graph: TxsGraph, commitments: List[TXID]) -> [int, int]:
    """
    return the total number of htlcs in the given commitments, and the number
    of htlcs that were claimed after timeout
    
    return: (total_htlcs, stolen_htlcs)
    """
    
    stolen_htlcs = sum(
        map(lambda commitment: len(get_timeout_htlc_claims(txs_graph, commitment)), commitments)
    )
    
    total_htlcs = sum(
        map(lambda commitment: len(get_htlc_claims(txs_graph, commitment)), commitments)
    )
    
    # this is just a sanity check
    success_htlcs = sum(
        map(lambda commitment: len(get_success_htlc_claims(txs_graph, commitment)), commitments)
    )
    if stolen_htlcs + success_htlcs != total_htlcs:
        print(
            "Warning: success+timeout transactions don't add up to the total number "
            "of htlc claims. probably a partial graph was given, or there is a bug",
            file=sys.stderr,
        )
    
    return total_htlcs, stolen_htlcs


def find_double_spends(txs_graph: TxsGraph) -> Dict[TXID, Dict[int, List[TXID]]]:
    """
    find double spends in the given TxsGraph. return a dictionary, mapping txid
    that contains a double-spent output, to a dictionary, mapping output index to
    txids that spent this output:
    
    {
        TXID: {
            0: [list of txids that spent TXID:0]
            2: [list of txids that spent TXID:2]
        },
        ...
    }
    """
    res = {}
    for txid in txs_graph.nodes:
        res[txid] = defaultdict(list)
        for src, dest, data in txs_graph.out_edges(txid, data=True):
            idx = data["index"]
            res[txid][idx].append(dest)
        
        # only keep the lists that have more than one element - these are double-spends
        res[txid] = {
            idx: txid_list
            for idx, txid_list in res[txid].items()
            if len(txid_list) > 1
        }
    
    # keep only txids that have at least one double-spent output
    res = {
        txid: double_spend_dict
        for txid, double_spend_dict in res.items()
        if len(double_spend_dict) > 0
    }
    
    return res


def print_double_spends(txs_graph: TxsGraph) -> None:
    double_spends = find_double_spends(txs_graph)
    for parent_txid, output_to_txid_list in double_spends.items():
        for output, txid_list in output_to_txid_list.items():
            short_parent_txid = txid_to_short_txid(parent_txid)
            print(f"txids that spend {short_parent_txid}:{output}:")
            for child_txid in txid_list:
                short_child_txid = txid_to_short_txid(child_txid)
                fee_sat = btc_to_sat(txs_graph.nodes[child_txid]["fee"])
                feerate = fee_sat / txs_graph.nodes[child_txid]["tx"]["size"]
                included_in_block = txs_graph.nodes[child_txid]["height"] is not None
                
                print(
                    f"    {short_child_txid} "
                    f"fee_satoshi={fee_sat}, "
                    f"feerate= {feerate}, "
                    f"included_in_blocks: {included_in_block}"
                )
            print()


def print_commitments_info(commitment_txids: List[TXID], txs_graph: TxsGraph) -> None:
    txid_label_len = 6
    txid_col_len = txid_label_len + 7
    height_col_len = 8
    min_exp_height_col_len = 16
    num_outputs_col_len = 13
    htlcs_stolen_col_len = 11
    
    print(
        "commit_txid".ljust(txid_col_len) +
        "height".ljust(height_col_len) +
        "min_exp_height".ljust(min_exp_height_col_len) +
        "num_outputs".ljust(num_outputs_col_len) +
        "htlcs_stolen".ljust(htlcs_stolen_col_len)
    )
    for commitment_txid in commitment_txids:
        short_txid = commitment_txid[-txid_label_len:]
        height = txs_graph.nodes[commitment_txid]["height"]
        min_exp_height = txs_graph.get_minimal_htlc_expiration_height(commitment_txid)
        num_outputs = len(txs_graph.nodes[commitment_txid]["tx"]["vout"])
        htlcs_stolen = len(get_timeout_htlc_claims(txs_graph=txs_graph, commitment_txid=commitment_txid))
        print(
            f"{short_txid:<{txid_col_len}}"
            f"{height:<{height_col_len}}"
            f"{min_exp_height:<{min_exp_height_col_len}}"
            f"{num_outputs:<{num_outputs_col_len}}"
            f"{htlcs_stolen:<{htlcs_stolen_col_len}}"
        )


def print_simulation_stats(simulation_name: str) -> None:
    txs_graph = get_simulation_graph(simulation_name)
    commitments = get_simulation_commitments(simulation_name)
    # only keep commitments who are not graceful closing transactions
    commitments = filter(
        lambda commitment_txid: txs_graph.get_minimal_nsequence(commitment_txid) < 0xffffffff,
        commitments,
    )
    
    sorted_commitments = sorted(commitments, key=lambda txid: txs_graph.nodes[txid]["height"])
    print_commitments_info(
        commitment_txids=sorted_commitments,
        txs_graph=txs_graph,
    )
    total_htlcs, stolen_htlcs = get_stolen_htlc_num(
        txs_graph=txs_graph,
        commitments=sorted_commitments,
    )
    print(
        f"Total HTLCs stolen: {stolen_htlcs}/{total_htlcs} "
        f"({round(stolen_htlcs * 100 / total_htlcs)}%)"
    )


simulation_name_regex = re.compile("steal-attack-(\\d+)-lnd-victims-blockmaxweight=(\\d+)")


def get_num_victims_vs_stolen_htlcs_data(simulation_names: List[str]) -> Dict[int, np.ndarray]:
    """
    return a mapping from blockmaxweight to a numpy matrix with 3 rows:
    first row with num_victims values
    second row with stolen_htlcs values
    third row with stolen_htlcs values in percentages
    """
    # mapping from blockmaxweight to array with shape 2xN
    data = defaultdict(lambda: ([], [], []))
    
    # initialize graphs_data
    for simulation_name in simulation_names:
        m = simulation_name_regex.fullmatch(simulation_name)
        if m is None:
            raise ValueError(f"Unrecognized simulation_name format: {simulation_name}")
        num_victims = int(m.group(1))
        blockmaxweight = int(m.group(2))
        total_htlcs, stolen_htlcs = get_stolen_htlc_num(
            txs_graph=get_simulation_graph(simulation_name),
            commitments=get_simulation_commitments(simulation_name),
        )
        stolen_htlcs_percent = (stolen_htlcs * 100 / total_htlcs)
        data[blockmaxweight][0].append(num_victims)
        data[blockmaxweight][1].append(stolen_htlcs)
        data[blockmaxweight][2].append(stolen_htlcs_percent)
    
    res = {}
    for blockmaxweight in data:
        graph_data = np.array(data[blockmaxweight])
        # sort by number of victims
        indices = np.argsort(graph_data[0])
        res[blockmaxweight] = graph_data[:, indices]
        assert res[blockmaxweight].shape[0] == 3
    
    return res


def plot_num_victims_vs_stolen_htlcs_graph(simulation_names: List[str]) -> None:
    """
    plot the graphs of number-of-victims vs stolen-HTLCs
    Different graph for each blockmaxweight, all on the same figure
    """
    data = get_num_victims_vs_stolen_htlcs_data(simulation_names)
    
    fig = plt.figure(figsize=[9.6, 7.2])
    for blockmaxweight, graph_data in data.items():
        num_victims_values = graph_data[0]
        stolen_htlcs_values = graph_data[1]
        stolen_htlcs_percent = graph_data[2]
        plt.plot(num_victims_values, stolen_htlcs_values, marker="o", label=f"blockmaxweight={blockmaxweight}")
    
    # force integer ticks for the num-victims axis
    fig.gca().xaxis.set_major_locator(MaxNLocator(integer=True))
    
    plt.xlabel("Number of victims")
    plt.ylabel("Number of HTLCs stolen")
    plt.legend(loc="best")
    plt.grid()
    plt.savefig(GRAPH_FILE)
    plt.show()


def get_simulation_datadir(simulation_name: str) -> str:
    return os.path.join(SIMULATIONS_DIR, simulation_name)


def get_simulation_outfile(simulation_name: str) -> str:
    return os.path.join(SIMULATIONS_DIR, f"{simulation_name}.out")


@lru_cache(maxsize=64)
def get_simulation_graph(simulation_name: str) -> TxsGraph:
    return TxsGraph.from_datadir(
        datadir=get_simulation_datadir(simulation_name)
    )


def get_simulation_commitments(simulation_name: str) -> List[TXID]:
    return find_commitments(
        simulation_outfile=get_simulation_outfile(simulation_name),
        graph=get_simulation_graph(simulation_name),
    )


def main(simulation_names: List[str]) -> None:
    for simulation_name in simulation_names:
        print(simulation_name)
        print_simulation_stats(simulation_name)
        print("\n=======\n")
    
    plot_num_victims_vs_stolen_htlcs_graph(simulation_names)


if __name__ == "__main__":
    simulation_names = sorted(filter(
        lambda name: os.path.isdir(get_simulation_datadir(name)) and name.startswith("steal-attack"),
        os.listdir(SIMULATIONS_DIR)
    ))
    main(simulation_names)
