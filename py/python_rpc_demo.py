import os
import time

from lightning import LightningRpc, Millisatoshi  # pip3 install pylightning

from bitcoin_cli import find_interesting_txids_in_last_t_blocks, mine, show_num_tx_in_last_t_blocks
from lightning_cli import make_many_payments, wait_to_route

ln = os.path.expandvars("$LN")
n1 = LightningRpc(os.path.join(ln, "lightning-dirs/1/regtest/lightning-rpc"))
n2 = LightningRpc(os.path.join(ln, "lightning-dirs/2/regtest/lightning-rpc"))
n3 = LightningRpc(os.path.join(ln, "lightning-dirs/3/regtest/lightning-rpc"))

# we assume the channels are already set-up

amount = Millisatoshi("0.0001btc")

wait_to_route(src=n1, dest=n3, msatoshi=amount.millisatoshis)

# send many payments to Charlie, which would result in unresolved HTLCs (assuming charlie is evil)
make_many_payments(
    sender=n1,
    receiver=n3,
    num_payments=480,
    msatoshi_per_payment=amount.millisatoshis,
)

# see the number of HTLCs that node 3 have with each peer
for i, peer in enumerate(n3.listpeers()["peers"]):
    print(f"htlcs with peers {i}: {len(peer['channels'][0]['htlcs'])}")

# Alice is not responsive. Bob can't remove HTLCs gracefully
n1.stop()

# node 3 closes all channels gracefully
for peer in n3.listpeers()["peers"]:
    n3.close(peer_id=peer["id"])

mine(1)

# Bob now has to publish the commitment tx of him and Alice
# slowly mine blocks
for _ in range(20):
    mine(1)
    time.sleep(5)

show_num_tx_in_last_t_blocks(t=30)
txs = find_interesting_txids_in_last_t_blocks(t=30)
