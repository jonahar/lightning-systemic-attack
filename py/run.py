import os
import pickle
import time

from lightning import LightningRpc, Millisatoshi  # pip3 install pylightning

from bitcoin_cli import mine
from lightning_cli import (
    get_id,
    make_many_payments,
)
from tx_graph import TXGraph
from utils import find_interesting_txids_in_last_t_blocks, show_num_tx_in_last_t_blocks, wait_to_route

lnpath = os.path.expandvars("$LNPATH")
n1 = LightningRpc(os.path.join(lnpath, "lightning-dirs/1/regtest/lightning-rpc"))
n2 = LightningRpc(os.path.join(lnpath, "lightning-dirs/2/regtest/lightning-rpc"))
n3 = LightningRpc(os.path.join(lnpath, "lightning-dirs/3/regtest/lightning-rpc"))

# we assume the channels are already set-up. see setup_nodes.py

ab_funding_txid = n1.listpeers(peerid=get_id(n2))["peers"][0]["channels"][0]["funding_txid"]
bc_funding_txid = n2.listpeers(peerid=get_id(n3))["peers"][0]["channels"][0]["funding_txid"]

amount = Millisatoshi("0.0001btc")

wait_to_route(src=n1, dest=n3, msatoshi=amount.millisatoshis)

# send many payments to Charlie, which would result in unresolved HTLCs (assuming charlie is evil)
make_many_payments(
    sender=n1,
    receiver=n3,
    num_payments=480,
    msatoshi_per_payment=amount.millisatoshis,
)

# Alice is not responsive. Bob can't remove HTLCs gracefully
n1.stop()

# Charlie asks to close the channel
bc_spending = n3.close(peer_id=get_id(n2))["txid"]
mine(1)

# Bob now has to publish the commitment tx of him and Alice
# slowly mine blocks
for _ in range(20):
    mine(1)
    time.sleep(5)

show_num_tx_in_last_t_blocks(t=50)
txs = find_interesting_txids_in_last_t_blocks(t=50)

graph_dot = os.path.join(lnpath, "graphs", "tx_graph.dot")
graph_pickle = os.path.join(lnpath, "graphs", "tx_graph.pickle")

g = TXGraph(txs)
g.export_to_dot(filepath=graph_dot)
with open(graph_pickle, mode="wb") as f:
    pickle.dump(g, f)
