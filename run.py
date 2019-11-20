import os
import time

from lightning import LightningRpc  # pip3 install pylightning
from lightning.lightning import RpcError

from bitcoin_cli import (
    fund_addresses, get_block_by_height, get_transaction, mine, num_tx_in_block
)
from datatypes import Block
from lightning_cli import connect_nodes, fund_channel, get_addr, get_id, make_many_payments
from utils import print_json


def show_num_tx_in_last_t_blocks(n: LightningRpc, t: int):
    block_height = n.getinfo()['blockheight']
    for i in range(block_height - t + 1, block_height + 1):
        num_tx_in_block_i = num_tx_in_block(block=get_block_by_height(i))
        print(f"number of tx in block {i}: {num_tx_in_block_i}")


def show_tx_in_block(block_height):
    block: Block = get_block_by_height(block_height)
    for txid in block['tx']:
        print(txid)


def wait_to_funds(n: LightningRpc) -> None:
    while len(n.listfunds()["outputs"]) == 0:
        time.sleep(1)


def wait_to_route(src: LightningRpc, dest: LightningRpc, msatoshi: int) -> None:
    found = False
    while not found:
        try:
            src.getroute(node_id=get_id(dest), msatoshi=msatoshi, riskfactor=1)
            found = True
        except RpcError as e:
            assert e.error["message"] == "Could not find a route", e
            time.sleep(1)


def init(n1: LightningRpc, n2: LightningRpc, n3: LightningRpc):
    """
    - fund all channels
    -
    :return:
    """
    mine(400)  # mine 400 to activate segwit
    initial_balance_txid = fund_addresses([get_addr(n1), get_addr(n2), get_addr(n3)])
    
    # wait until node 1 has funds so we can fund the channels
    wait_to_funds(n1)
    
    connect_nodes(n1, n2)
    connect_nodes(n2, n3)
    channel_1_funding_txid = fund_channel(funder=n1, fundee=n2, num_satoshi=10_000_000)
    channel_2_funding_txid = fund_channel(funder=n2, fundee=n3, num_satoshi=10_000_000)
    # wait until n1 knows a path to n3 so we can make a payment
    wait_to_route(n1, n3, msatoshi=100_000_000)
    return channel_1_funding_txid, channel_2_funding_txid


ln_path = os.path.expandvars("$LAB/ln")
n1 = LightningRpc(os.path.join(ln_path, "lightning-dirs/1/lightning-rpc"))
n2 = LightningRpc(os.path.join(ln_path, "lightning-dirs/2/lightning-rpc"))
n3 = LightningRpc(os.path.join(ln_path, "lightning-dirs/3/lightning-rpc"))

alice_bob_funding_txid, bob_charlie_funding_txid = init(n1, n2, n3)

make_many_payments(
    sender=n1,
    receiver=n3,
    num_payments=1,
    msatoshi_per_payment=100_000_000,  # 0.01 BTC
    timeout=3,
)

# shutdown node 2
n2.stop()

# see the funding transaction
print_json(get_transaction(bob_charlie_funding_txid))
# current height
print(n3.getinfo()['blockheight'])

# force close the channel
bob_charlie_closing_txid = n3.close(peer_id=get_id(n2), force=True)['txid']
mine(1)

# see the closing transaction
print_json(get_transaction(bob_charlie_closing_txid))

show_num_tx_in_last_t_blocks(n=n1, t=3)

show_tx_in_block(414)
