import json
import time

from lightning import LightningRpc  # pip3 install pylightning
from lightning.lightning import RpcError

from bitcoin_cli import (
    get_block_by_height,
    num_tx_in_block,
)
from datatypes import Block, Json
from lightning_cli import (
    get_id,
)


def print_json(o: Json):
    print(json.dumps(o, indent=4))


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
    """wait until n has a UTXO it controls"""
    while len(n.listfunds()["outputs"]) == 0:
        time.sleep(1)


def wait_to_route(src: LightningRpc, dest: LightningRpc, msatoshi: int) -> None:
    """wait until src knows a route to dest with an amount of msatoshi"""
    found = False
    while not found:
        try:
            src.getroute(node_id=get_id(dest), msatoshi=msatoshi, riskfactor=1)
            found = True
        except RpcError as e:
            assert e.error["message"] == "Could not find a route", e
            time.sleep(2)
