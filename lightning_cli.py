from lightning import LightningRpc  # pip3 install pylightning

from bitcoin_cli import mine


def get_id(l: LightningRpc) -> str:
    return l.getinfo()['id']


def get_addr(l: LightningRpc) -> str:
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
    blocks_to_mine=6
) -> str:
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
