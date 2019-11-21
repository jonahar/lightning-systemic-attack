import os
import time

from lightning import LightningRpc  # pip3 install pylightning

from bitcoin_cli import (
    fund_addresses,
    get_transaction,
    mine,
)
from lightning_cli import (
    connect_nodes,
    fund_channel,
    get_addr,
    get_id,
    get_total_balance,
    make_many_payments,
)
from utils import (
    find_interesting_txids,
    print_json,
    show_num_tx_in_last_t_blocks,
    show_tx_in_block,
    wait_to_funds,
    wait_to_route,
)


def init(n1: LightningRpc, n2: LightningRpc, n3: LightningRpc, channel_balance_satoshi: int):
    """
    - fund all nodes with BTC
    - construct and fund channels n1 <--> n2 <--> n3
    """
    mine(400)  # mine 400 to activate segwit
    initial_balance_txid = fund_addresses([get_addr(n1), get_addr(n2), get_addr(n3)])
    
    # wait until node 1 has funds so we can fund the channels
    wait_to_funds(n1)
    
    connect_nodes(n1, n2)
    connect_nodes(n2, n3)
    channel_1_funding_txid = fund_channel(funder=n1, fundee=n2, num_satoshi=channel_balance_satoshi)
    channel_2_funding_txid = fund_channel(funder=n2, fundee=n3, num_satoshi=channel_balance_satoshi)
    # wait until n1 knows a path to n3 so we can make a payment
    wait_to_route(n1, n3, msatoshi=channel_balance_satoshi * 1000 // 10)
    return channel_1_funding_txid, channel_2_funding_txid


ln_path = os.path.expandvars("$LAB/ln")
n1 = LightningRpc(os.path.join(ln_path, "lightning-dirs/1/lightning-rpc"))
n2 = LightningRpc(os.path.join(ln_path, "lightning-dirs/2/lightning-rpc"))
n3 = LightningRpc(os.path.join(ln_path, "lightning-dirs/3/lightning-rpc"))

alice_bob_funding_txid, bob_charlie_funding_txid = init(
    n1, n2, n3,
    channel_balance_satoshi=10_000_000,  # 0.1 BTC
)

make_many_payments(
    sender=n1,
    receiver=n3,
    num_payments=5,
    msatoshi_per_payment=1_000_000_000,  # 0.01 BTC
)

# shutdown node 2
n2.stop()

for i in range(20):
    mine(1)
    time.sleep(1)

current_height = n1.getinfo()['blockheight']
txids = find_interesting_txids(block_heights=range(current_height - 30, current_height + 1))

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

get_total_balance(n1)
get_total_balance(n2)
get_total_balance(n3)
