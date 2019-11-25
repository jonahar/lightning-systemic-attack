import os
import time

from lightning import LightningRpc  # pip3 install pylightning

from bitcoin_cli import (
    get_transaction,
    mine,
)
from lightning_cli import (
    get_id,
    get_total_balance,
    make_many_payments,
)
from tx_set import TXSet
from utils import (
    find_interesting_txids,
    print_json,
    show_num_tx_in_last_t_blocks,
    show_tx_in_block,
)

lnpath = os.path.expandvars("$LNPATH")
n1 = LightningRpc(os.path.join(lnpath, "lightning-dirs/1/lightning-rpc"))
n2 = LightningRpc(os.path.join(lnpath, "lightning-dirs/2/lightning-rpc"))
n3 = LightningRpc(os.path.join(lnpath, "lightning-dirs/3/lightning-rpc"))

# we assume the channels are already set-up. see setup_nodes.py

ab_funding_txid = n1.listpeers(peerid=get_id(n2))["peers"][0]["channels"][0]["funding_txid"]
bc_funding_txid = n2.listpeers(peerid=get_id(n3))["peers"][0]["channels"][0]["funding_txid"]

# send 0.02 to Bob
make_many_payments(
    sender=n1,
    receiver=n2,
    num_payments=1,
    msatoshi_per_payment=2_000_000_000,
)

# send 0.01 to Charlie, which would result in an unresolved HTLC (assuming charlie is evil)
make_many_payments(
    sender=n1,
    receiver=n3,
    num_payments=1,
    msatoshi_per_payment=1_000_000_000,
)

# force close so we can see the commitment transaction
ab_commitment = n1.close(peer_id=get_id(n2), force=True, timeout=0)["txid"]

# ----------------

# # shutdown node 2
# n2.stop()
#
# # force close the channel
# bob_charlie_closing_txid = n3.close(peer_id=get_id(n2), force=True, timeout=0)['txid']
# mine(1)
#
# for i in range(20):
#     mine(1)
#     time.sleep(1)
#
# current_height = n1.getinfo()['blockheight']
# txids = find_interesting_txids(block_heights=range(current_height - 30, current_height + 1))
# tx_set = TXSet(txids=txids)
#
# # see the funding transaction
# print_json(get_transaction(bc_funding_txid))
#
# # see the closing transaction
# print_json(get_transaction(bob_charlie_closing_txid))
#
# show_num_tx_in_last_t_blocks(t=3)
#
# show_tx_in_block(414)
#
# get_total_balance(n1)
# get_total_balance(n2)
# get_total_balance(n3)
