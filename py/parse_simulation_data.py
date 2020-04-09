import itertools
import os
import re
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Set

from datatypes import BTC, TXID, btc_to_sat
from paths import LN
from txs_graph.txs_graph import TxsGraph


# ---------- txid-to-label functions ----------


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


def get_htlcs_claimed_by_timeout(
    txs_graph: TxsGraph,
    commitment_txid: TXID,
    include_unconfirmed: bool = False,
) -> List[TXID]:
    """
    return a list of txids that spend an HTLC output from the given
    commitment transaction, using the timeout-path of the HTLC script
    if include_unconfirmed is True, the result includes transactions that were published
    but not included in a block
    """
    # from the bolt:
    # " HTLC-Timeout and HTLC-Success Transactions... are almost identical,
    #   except the HTLC-timeout transaction is timelocked
    #   ...
    #   locktime: 0 for HTLC-success, cltv_expiry for HTLC-timeout
    #   "
    #
    # i.e. if the child_tx has a non-zero locktime, it is an HTLC-timeout
    return [
        child_tx
        for _, child_tx in txs_graph.out_edges(commitment_txid)
        if (
            # we want to include it
            (txs_graph.nodes[child_tx]["height"] is not None or include_unconfirmed)
            and
            # it really spends an HTLC output
            txs_graph.is_htlc_claim_tx(child_tx)
            and
            # is using the "timeout" path of the htlc script
            txs_graph.nodes[child_tx]["tx"]["locktime"] > 0
        )
    ]


def get_htlcs_claimed_by_success(
    txs_graph: TxsGraph,
    commitment_txid: TXID,
    include_unconfirmed: bool = False,
) -> List[TXID]:
    """
    return a list of txids that spend an HTLC output from the given
    commitment transaction, using the success-path of the HTLC script.
    
    include_unconfirmed just as in get_htlcs_claimed_by_timeout
    """
    # from the bolt:
    # " HTLC-Timeout and HTLC-Success Transactions... are almost identical,
    #   except the HTLC-timeout transaction is timelocked
    #   ...
    #   locktime: 0 for HTLC-success, cltv_expiry for HTLC-timeout
    #   "
    return [
        child_tx
        for _, child_tx in txs_graph.out_edges(commitment_txid)
        if (
            (txs_graph.nodes[child_tx]["height"] is not None or include_unconfirmed)
            and
            txs_graph.is_htlc_claim_tx(child_tx)
            and
            txs_graph.nodes[child_tx]["tx"]["locktime"] == 0
        )
    ]


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
    txid_col_len = txid_label_len + 2
    height_col_len = 8
    min_exp_height_col_len = 15
    num_outputs_col_len = 13
    replaceable_col_len = 13
    nsequence_col_len = 11
    htlcs_stolen_col_len = 11
    
    print(
        "txid".ljust(txid_col_len) +
        "height".ljust(height_col_len) +
        "min_exp_height".ljust(min_exp_height_col_len) +
        "num_outputs".ljust(num_outputs_col_len) +
        "replaceable".ljust(replaceable_col_len) +
        "nsequence".ljust(nsequence_col_len) +
        "htlcs_stolen".ljust(htlcs_stolen_col_len)
    )
    total_htlcs_stolen = 0
    for commitment_txid in commitment_txids:
        short_txid = commitment_txid[-txid_label_len:]
        height = txs_graph.nodes[commitment_txid]["height"]
        min_exp_height = txs_graph.get_minimal_htlc_expiration_height(commitment_txid)
        num_outputs = len(txs_graph.nodes[commitment_txid]["tx"]["vout"])
        replaceable = str(txs_graph.is_replaceable_by_fee(txid=commitment_txid))
        nsequence = txs_graph.get_minimal_nsequence(commitment_txid)
        htlcs_stolen = len(get_htlcs_claimed_by_timeout(txs_graph=txs_graph, commitment_txid=commitment_txid))
        total_htlcs_stolen += htlcs_stolen
        print(
            f"{short_txid:<{txid_col_len}}"
            f"{height:<{height_col_len}}"
            f"{min_exp_height:<{min_exp_height_col_len}}"
            f"{num_outputs:<{num_outputs_col_len}}"
            f"{replaceable:<{replaceable_col_len}}"
            f"{nsequence:<{nsequence_col_len}x}"
            f"{htlcs_stolen:<{htlcs_stolen_col_len}}"
        )
    
    print(f"Total HTLCs stolen: {total_htlcs_stolen}")


def export_to_jpg(graph: TxsGraph, graph_name: str) -> None:
    """
    export the graph to a jpg file, named  <graph_name>.jpg
    """
    dotfile = os.path.join(LN, f"{graph_name}.dot")
    export_txs_graph_to_dot(
        graph=graph,
        dotfile=dotfile,
        txid_to_label=txid_to_short_txid,
    )
    # convert dot to jpg
    jpgfile = os.path.join(LN, f"{graph_name}.jpg")
    os.system(f"cd {LN}; dot2jpg {dotfile} {jpgfile}")


def get_simulation_datadir(simulation_name: str) -> str:
    return os.path.join(LN, "simulations", simulation_name)


def get_simulation_outfile(simulation_name: str) -> str:
    return os.path.join(LN, "simulations", f"{simulation_name}.out")


def get_simulation_graph(simulation_name: str) -> TxsGraph:
    return TxsGraph.from_datadir(
        datadir=get_simulation_datadir(simulation_name)
    )


def get_simulation_commitments(simulation_name: str) -> List[TXID]:
    return find_commitments(
        simulation_outfile=get_simulation_outfile(simulation_name),
        graph=get_simulation_graph(simulation_name),
    )


def print_simulation_stats(simulation_name: str) -> None:
    print(simulation_name)
    commitments = get_simulation_commitments(simulation_name)
    txs_graph = get_simulation_graph(simulation_name)
    sorted_commitments = sorted(commitments, key=lambda txid: txs_graph.nodes[txid]["height"])
    print_commitments_info(
        commitment_txids=sorted_commitments,
        txs_graph=txs_graph,
    )


def main(simulation_names: List[str]) -> None:
    for simulation_name in simulation_names:
        print_simulation_stats(simulation_name)
        print("\n=======\n")


if __name__ == "__main__":
    main(["simulation_names"])
