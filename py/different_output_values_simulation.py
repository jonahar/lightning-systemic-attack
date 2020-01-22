import os
import time

from lightning import LightningRpc, Millisatoshi  # pip3 install pylightning

from bitcoin_cli import mine
from lightning_cli import get_id, wait_to_route

ln = os.path.expandvars("$LN")
n1 = LightningRpc(os.path.join(ln, "lightning-dirs/1/regtest/lightning-rpc"))
n2 = LightningRpc(os.path.join(ln, "lightning-dirs/2/regtest/lightning-rpc"))
n3 = LightningRpc(os.path.join(ln, "lightning-dirs/3/regtest/lightning-rpc"))

# we assume the channels are already set-up

amount = Millisatoshi("0.0001btc")

wait_to_route(src=n1, dest=n3, msatoshi=amount.millisatoshis)

sender = n1
receiver = n3
different_amounts = [
    Millisatoshi("0.04btc"),
    Millisatoshi("0.01btc"),
    Millisatoshi("0.01btc"),
    Millisatoshi("0.001btc"),
    Millisatoshi("0.001btc"),
    Millisatoshi("0.0001btc"),
    Millisatoshi("0.0001btc"),
    Millisatoshi("0.00001btc"),
    Millisatoshi("0.00001btc"),
    Millisatoshi("0.000001btc"),
]

assert sum(different_amounts, Millisatoshi(0)).to_btc() < 0.09

for amount in different_amounts:
    invoice = receiver.invoice(
        msatoshi=amount,
        label=f"label_{time.time()}",  # a unique label is needed
        description="",
    )
    route = sender.getroute(
        node_id=get_id(receiver),
        msatoshi=amount,
        riskfactor=1,
    )["route"]
    sender.sendpay(route=route, payment_hash=invoice["payment_hash"])

# Alice is not responsive. Bob can't remove HTLCs gracefully
n1.stop()

# node 3 closes all channels gracefully
for peer in n3.listpeers()["peers"]:
    n3.close(peer_id=peer["id"])

mine(1)
