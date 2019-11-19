import os
import time

from lightning import LightningRpc  # pip3 install pylightning

from bitcoin_cli import fund_addresses, mine
from lightning_cli import connect_nodes, fund_channel

os.chdir(os.path.expandvars("$LAB/ln/lightning-dirs"))

n1 = LightningRpc("1/lightning-rpc")
n2 = LightningRpc("2/lightning-rpc")
n3 = LightningRpc("3/lightning-rpc")

mine(400)  # mine 400 to activate segwit
initial_balance_txid = fund_addresses([addr1, addr2, addr3])

# wait a few seconds until the lightning nodes get the blocks and are fully synced
time.sleep(5)
# check that the node is synced if it is aware of its funding
n2.listfunds()

connect_nodes(n1, n2)
connect_nodes(n2, n3)
alice_bob_funding_txid = fund_channel(funder=n1, fundee=n2, num_satoshi=10_000_000)
bob_charlie_funding_txid = fund_channel(funder=n2, fundee=n3, num_satoshi=10_000_000)

print(len(n2.listchannels()['channels']))

invoice = n3.invoice(msatoshi=1_000_000, label=f"label_{time.time()}", description="")
n1.pay(bolt11=invoice['bolt11'])

# close channel
charlie_bob_closing_txid = l3.close(peer_id=id2, force=True)['txid']
mine(1)
