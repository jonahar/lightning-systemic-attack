import time
from functools import lru_cache
from multiprocessing import Process

from lightning import LightningRpc  # pip3 install pylightning

from bitcoin_cli import mine
from datatypes import Address, TXID


@lru_cache(maxsize=100)
def get_id(l: LightningRpc) -> str:
    return l.getinfo()['id']


def get_addr(l: LightningRpc) -> Address:
    return l.newaddr()['address']


def connect_nodes(n1: LightningRpc, n2: LightningRpc) -> None:
    n1_id = get_id(n1)
    n1_host: str = n1.getinfo()['binding'][0]['address']
    n1_port: int = n1.getinfo()['binding'][0]['port']
    n2.connect(peer_id=n1_id, host=n1_host, port=n1_port)


def fund_channel(
    funder: LightningRpc,
    fundee: LightningRpc,
    num_satoshi: int,
    blocks_to_mine=6,
) -> TXID:
    """
    fund a channel between the two nodes with initial num_satoshi satoshis, and
    mine blocks_to_mine blocks.
    blocks_to_mine should be the minimum number of blocks required for this channel
    to be considered valid.
    funder and fundee should be already connected
    
    If all went well, the funding txid is returned
    """
    funding_txid = funder.fundchannel(node_id=get_id(fundee), satoshi=num_satoshi)['txid']
    mine(blocks_to_mine)
    return funding_txid


def make_many_payments(
    sender: LightningRpc,
    receiver: LightningRpc,
    num_payments: int,
    msatoshi_per_payment: int,
    timeout: int,
) -> None:
    # in case the receiver is evil, the secret will not be returned and the call
    # to LightningRpc.pay will be stuck, waiting for the secret. therefore we need
    # to run pay with a timeout
    processes = []
    for i in range(num_payments):
        invoice = receiver.invoice(
            msatoshi=msatoshi_per_payment,
            label=f"label_{time.time()}",  # a unique label is needed
            description="",
        )
        p = Process(target=LightningRpc.pay, args=(sender, invoice["bolt11"]))
        processes.append(p)
        p.start()
    
    time.sleep(timeout)
    for p in processes:
        p.terminate()
