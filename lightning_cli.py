import os
import time

from lightning import LightningRpc  # pip3 install pylightning

from bitcoin_cli import mine, fund_addresses

os.chdir(os.path.expandvars("$LAB/ln/lightning-dirs"))

l1 = LightningRpc("1/lightning-rpc")
l2 = LightningRpc("2/lightning-rpc")
l3 = LightningRpc("3/lightning-rpc")


def get_id(l: LightningRpc):
    return l.getinfo()['id']


def get_addr(l: LightningRpc):
    return l.newaddr()['address']


# get ids
id1 = get_id(l1)
id2 = get_id(l2)
id3 = get_id(l3)

# get addresses for initial funding
addr1 = get_addr(l1)
addr2 = get_addr(l2)
addr3 = get_addr(l3)

mine(400)  # mine 400 to activate segwit
initial_balance_txid = fund_addresses([addr1, addr2, addr3])

# wait a few seconds until the lightning nodes get the blocks and are fully synced
time.sleep(5)
# check that the node is synced if it is aware of its funding
l2.listfunds()

# connect nodes
l1.connect(id2, host="localhost", port=10002)
l3.connect(id2, host="localhost", port=10002)

# fund channels
alice_bob_funding_txid = l1.fundchannel(node_id=id2, satoshi=10_000_000)['txid']
mine(6)  # mine 6 blocks so the channel is considered valid
bob_charlie_funding_txid = l2.fundchannel(node_id=id3, satoshi=10_000_000)['txid']
mine(6)

print(len(l2.listchannels()['channels']))

# make payments
invoice = l3.invoice(msatoshi=1_000_000, label=f"label_{time.time()}", description="")
l1.pay(bolt11=invoice['bolt11'])

# close channel
charlie_bob_closing_txid = l3.close(peer_id=id2, force=True)['txid']
mine(1)
