import json
import os

from lightning import Millisatoshi  # pip3 install pylightning

from commands_generator.commands_generator import CommandsGenerator

# This script generates simulation commands to examine different transactions/scripts
# structure. We create a channel and make payments s.t. the commitment transaction
# will contain all output types: local, remote, htlc-in, htlc-out


ln = os.path.expandvars("$LN")

outfile = open(os.path.join(ln, "simulations/structure-simulation.sh"), mode="w")
topology_file = os.path.join(ln, "topologies/topology-1-a-b-1.json")  # 3<->1<->2<->4
dumpdir = os.path.join(ln, "simulations/structure-simulation")

with open(topology_file)as f:
    topology = json.load(f)

cg = CommandsGenerator(
    file=outfile,
    topology=topology,
    bitcoin_block_max_weight=4000000,
    verbose=True,
)

cg.shebang()
cg.generated_code_comment()
cg.start_bitcoin_nodes()
cg.start_bitcoin_miner()
cg.wait_until_miner_is_ready()
cg.connect_bitcoin_nodes_to_miner()
cg.connect_bitcoin_nodes_in_circle()
cg.mine(10)
cg.wait_until_bitcoin_nodes_synced(height=10)
cg.start_lightning_nodes()
cg.fund_nodes()
cg.wait_for_funds()
cg.establish_channels()
cg.wait_for_funding_transactions()
cg.mine(num_blocks=10)
cg.wait_to_route(1, 4, 10000000)
cg.wait_to_route(2, 3, 10000000)
# create output for node 2
cg.make_payments(sender_idx=1, receiver_idx=2, num_payments=1, amount_msat=Millisatoshi("0.042btc").millisatoshis)
# create HTLC-in
cg.make_payments(sender_idx=1, receiver_idx=4, num_payments=2, amount_msat=Millisatoshi("0.001btc").millisatoshis)
# create HTLC-out
cg.make_payments(sender_idx=2, receiver_idx=3, num_payments=2, amount_msat=Millisatoshi("0.002btc").millisatoshis)
cg.wait(seconds=2)
cg.stop_lightning_node(1)
cg.close_all_node_channels(4)
cg.advance_blockchain(num_blocks=40, block_time_sec=60)
cg.advance_blockchain(num_blocks=100, block_time_sec=0)
cg.advance_blockchain(num_blocks=2, block_time_sec=30)
# we shouldn't call __write_line directly, but....
cg._CommandsGenerator__write_line(
    """
    ADDR_2=$(lcli 2 newaddr | jq -r ".address")
    lcli 2 withdraw $ADDR_2 all
    """
)
cg.mine(1)
cg.dump_simulation_data(dir=dumpdir)
cg.info("Done")

outfile.close()
