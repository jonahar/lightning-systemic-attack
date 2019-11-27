#!/usr/bin/env python3

import os

from lightning import LightningRpc  # pip3 install pylightning

from bitcoin_cli import (
    fund_addresses,
    mine,
)
from lightning_cli import (
    connect_nodes,
    fund_channel,
    get_addr,
)
from utils import (
    wait_to_funds,
    wait_to_route,
)


def init(n1: LightningRpc, n2: LightningRpc, n3: LightningRpc, channel_balance_satoshi: int) -> None:
    """
    - fund all nodes with BTC
    - construct and fund channels n1 <--> n2 <--> n3
    """
    print("Funding the nodes (onchain)")
    mine(400)  # mine 400 to activate segwit
    initial_balance_txid = fund_addresses([get_addr(n1), get_addr(n2), get_addr(n3)])
    
    # wait until nodes 1,2 have funds so we can fund the channels
    print("Waiting for nodes to receive funds")
    wait_to_funds(n1)
    wait_to_funds(n2)
    
    connect_nodes(n1, n2)
    connect_nodes(n2, n3)
    channel_1_funding_txid = fund_channel(funder=n1, fundee=n2, num_satoshi=channel_balance_satoshi)
    channel_2_funding_txid = fund_channel(funder=n2, fundee=n3, num_satoshi=channel_balance_satoshi)
    # wait until n1 knows a path to n3 so we can make a payment
    print("Waiting for node A to know payment path to node C")
    wait_to_route(n1, n3, msatoshi=channel_balance_satoshi * 1000 // 10)


if __name__ == "__main__":
    lnpath = os.path.expandvars("$LNPATH")
    n1 = LightningRpc(os.path.join(lnpath, "lightning-dirs/1/regtest/lightning-rpc"))
    n2 = LightningRpc(os.path.join(lnpath, "lightning-dirs/2/regtest/lightning-rpc"))
    n3 = LightningRpc(os.path.join(lnpath, "lightning-dirs/3/regtest/lightning-rpc"))
    
    init(
        n1, n2, n3,
        channel_balance_satoshi=10_000_000,  # 0.1 BTC
    )
