import os

from lightning import LightningRpc, Millisatoshi  # pip3 install pylightning

from bitcoin_cli import get_mempool_txids, get_transaction, mine
from lightning_cli import (
    get_id,
    make_many_payments,
)

lnpath = os.path.expandvars("$LNPATH")
n1 = LightningRpc(os.path.join(lnpath, "lightning-dirs/1/regtest/lightning-rpc"))
n2 = LightningRpc(os.path.join(lnpath, "lightning-dirs/2/regtest/lightning-rpc"))
n3 = LightningRpc(os.path.join(lnpath, "lightning-dirs/3/regtest/lightning-rpc"))

# we assume the channels are already set-up. see setup_nodes.py

ab_funding_txid = n1.listpeers(peerid=get_id(n2))["peers"][0]["channels"][0]["funding_txid"]
bc_funding_txid = n2.listpeers(peerid=get_id(n3))["peers"][0]["channels"][0]["funding_txid"]

amount = Millisatoshi("0.0001btc")

# send many payments to Charlie, which would result in unresolved HTLCs (assuming charlie is evil)
make_many_payments(
    sender=n1,
    receiver=n3,
    num_payments=480,
    msatoshi_per_payment=amount.millisatoshis,
)

# force close so we can see the commitment transaction
bc_commitment = n3.close(peer_id=get_id(n2), force=True, timeout=0)["txid"]
mine(1)

# the mempool, after bob sees the commitment tx onchain
mempool = get_mempool_txids()
total_size = sum(map(lambda txid: get_transaction(txid)["size"], mempool))
total_vsize = sum(map(lambda txid: get_transaction(txid)["vsize"], mempool))
