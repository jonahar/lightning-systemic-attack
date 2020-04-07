import argparse
import json
import os
import sys
from typing import Any, Dict, TextIO

from commands_generator.bitcoin_core import BitcoinCommandsGenerator, BitcoinCoreCommandsGenerator
from commands_generator.clightning import ClightningCommandsGenerator
from commands_generator.eclair import EclairCommandsGenerator
from commands_generator.lightning import LightningCommandsGenerator
from commands_generator.lnd import LndCommandsGenerator
from commands_generator.resources_allocator import ResourcesAllocator
from datatypes import NodeIndex
from paths import BITCOIN_CONF_PATH

INITIAL_CHANNEL_BALANCE_SAT = 10000000  # 0.1 BTC
BITCOIN_MINER_IDX = 0


class CommandsGenerator:
    """
    A CommandsGenerator generates bash code to execute many lightning-related actions.
    it support:
        - start bitcoin nodes
        - connect bitcoin nodes to a central "miner" node
        - start lightning nodes
        - establish channels between lightning nodes
        - make lightning payments between nodes
    
    The CommandsGenerator works according to a given topology, which is a dictionary
    in the following structure:
    
    {
      "ID1": {
        "peers": ["ID2", "ID4"],   // mandatory. may be an empty list
        "evil": false,             // optional. defaults to false
        "silent": false,           // optional. defaults to false
        "alias": "alice"           // optional. defaults to ID
        "client": "c-lightning"    // optional. defaults to c-lightning
      },
      "ID2": {...},
      "ID3": {...},
      "ID4": {...}
    }

    """
    
    VERSION: str = "A.113"
    
    DEFAULT_SIMULATION = 1
    
    def __init__(
        self,
        file: TextIO,
        topology: Dict[str, Any],
        bitcoin_block_max_weight: int,
        verbose: bool = True,
        simulation_number: int = DEFAULT_SIMULATION,
    ) -> None:
        """
        Initialize a new commands generator
        
        Args:
            file: file-like object to write the commands to
            topology: a topology dictionary, as described above
            bitcoin_block_max_weight: the maximum bitcoin block weight
            verbose: If True, generate echo commands with information
            simulation_number: an int between 1 and 6. simulations with different
                               numbers are able to run in parallel (they will be
                               allocated different ports/directories)
        """
        self.file = file
        self.topology = self.__sanitize_topology_keys(topology)
        if BITCOIN_MINER_IDX in topology:
            raise ValueError(f"Invalid id {BITCOIN_MINER_IDX}: reserved for bitcoin miner node")
        self.bitcoin_block_max_weight = bitcoin_block_max_weight
        self.verbose = verbose
        self.resources_allocator = ResourcesAllocator(simulation=simulation_number)
        
        self.bitcoin_clients: Dict[NodeIndex, BitcoinCommandsGenerator] = self.__init_bitcoin_clients()
        # each LightningCommandsGenerator generates lightning commands
        # according to the node's chosen implementation
        self.lightning_clients: Dict[NodeIndex, LightningCommandsGenerator] = self.__init_lightning_clients()
    
    @staticmethod
    def __sanitize_topology_keys(topology: dict) -> Dict[NodeIndex, Any]:
        """
        verify each topology key represents an index (int) and return a topology
        in which all keys are ints
        """
        try:
            sanitized_topology = {}
            for k, v in topology.items():
                sanitized_topology[int(k)] = v
                v["peers"] = list(map(int, v["peers"]))
            return sanitized_topology
        
        except ValueError:
            raise ValueError("Failed to sanitize topology. Is there a non-integer key?")
    
    def __init_clightning_client(self, node_idx: NodeIndex) -> ClightningCommandsGenerator:
        info = self.topology[node_idx]
        alias = info.get("alias", str(node_idx))
        lightning_dir = self.resources_allocator.get_lightning_node_datadir(node_idx=node_idx)
        evil = info.get("evil", False)
        silent = info.get("silent", False)
        return ClightningCommandsGenerator(
            idx=node_idx,
            file=self.file,
            datadir=lightning_dir,
            listen_port=self.resources_allocator.get_lightning_node_listen_port(node_idx),
            bitcoin_rpc_port=self.resources_allocator.get_bitcoin_node_rpc_port(node_idx),
            alias=alias,
            evil=evil,
            silent=silent,
        )
    
    def __init_lnd_client(self, node_idx: NodeIndex) -> LndCommandsGenerator:
        info = self.topology[node_idx]
        alias = info.get("alias", str(node_idx))
        return LndCommandsGenerator(
            index=node_idx,
            file=self.file,
            lightning_dir=self.resources_allocator.get_lightning_node_datadir(node_idx),
            bitcoin_dir=self.resources_allocator.get_bitcoin_node_datadir(node_idx),
            listen_port=self.resources_allocator.get_lightning_node_listen_port(node_idx),
            rpc_port=self.resources_allocator.get_lightning_node_rpc_port(node_idx),
            rest_port=self.resources_allocator.get_lightning_node_rest_port(node_idx),
            bitcoin_rpc_port=self.resources_allocator.get_bitcoin_node_rpc_port(node_idx),
            zmqpubrawblock_port=self.resources_allocator.get_bitcoin_node_zmqpubrawblock_port(node_idx),
            zmqpubrawtx_port=self.resources_allocator.get_bitcoin_node_zmqpubrawtx_port(node_idx),
            alias=alias,
        )
    
    def __init_eclair_client(self, node_idx: NodeIndex) -> EclairCommandsGenerator:
        info = self.topology[node_idx]
        alias = info.get("alias", str(node_idx))
        max_accepted_htlcs = info.get("max_accepted_htlcs", 483)
        return EclairCommandsGenerator(
            index=node_idx,
            file=self.file,
            lightning_dir=self.resources_allocator.get_lightning_node_datadir(node_idx),
            listen_port=self.resources_allocator.get_lightning_node_listen_port(node_idx),
            rpc_port=self.resources_allocator.get_lightning_node_rpc_port(node_idx),
            bitcoin_rpc_port=self.resources_allocator.get_bitcoin_node_rpc_port(node_idx),
            zmqpubrawblock_port=self.resources_allocator.get_bitcoin_node_zmqpubrawblock_port(node_idx),
            zmqpubrawtx_port=self.resources_allocator.get_bitcoin_node_zmqpubrawtx_port(node_idx),
            bitcoin_commands_generator=self.bitcoin_clients[node_idx],
            alias=alias,
            max_accepted_htlcs=max_accepted_htlcs,
        )
    
    def __init_lightning_clients(self) -> Dict[NodeIndex, LightningCommandsGenerator]:
        """
        build LightningCommandsGenerator for each node in the topology.
        the concrete implementation is determined by the node's config
        """
        clients = {}
        for idx in self.topology.keys():
            client = self.topology[idx].get("client", "c-lightning")
            if client == "c-lightning":
                clients[idx] = self.__init_clightning_client(idx)
            elif client == "lnd":
                clients[idx] = self.__init_lnd_client(idx)
            elif client == "eclair":
                clients[idx] = self.__init_eclair_client(idx)
            else:
                raise TypeError(f"unsupported lightning client: {client}")
        
        return clients
    
    def __init_bitcoin_core_client(self, node_idx: NodeIndex) -> BitcoinCoreCommandsGenerator:
        return BitcoinCoreCommandsGenerator(
            idx=node_idx,
            file=self.file,
            datadir=self.resources_allocator.get_bitcoin_node_datadir(node_idx),
            listen_port=self.resources_allocator.get_bitcoin_node_listen_port(node_idx),
            rpc_port=self.resources_allocator.get_bitcoin_node_rpc_port(node_idx),
            blockmaxweight=self.bitcoin_block_max_weight,
            zmqpubrawblock_port=self.resources_allocator.get_bitcoin_node_zmqpubrawblock_port(node_idx),
            zmqpubrawtx_port=self.resources_allocator.get_bitcoin_node_zmqpubrawtx_port(node_idx),
        )
    
    def __init_bitcoin_clients(self) -> Dict[NodeIndex, BitcoinCommandsGenerator]:
        """
        build BitcoinCommandsGenerator for each node in the topology.
        the concrete implementation is determined by the node's config
        """
        # create the clients dictionary, and start with the miner node, which by
        # default uses bitcoin-core
        clients = {
            BITCOIN_MINER_IDX: self.__init_bitcoin_core_client(BITCOIN_MINER_IDX)
        }
        
        for idx in self.topology.keys():
            client = self.topology[idx].get("bitcoin-client", "bitcoin-core")
            if client == "bitcoin-core":
                clients[idx] = self.__init_bitcoin_core_client(idx)
            else:
                raise TypeError(f"unsupported bitcoin client: {client}")
        
        return clients
    
    def __write_line(self, line: str) -> None:
        self.file.write(line)
        self.file.write("\n")
    
    def shebang(self) -> None:
        self.__write_line("#!/usr/bin/env bash")
    
    def generated_code_comment(self) -> None:
        self.__write_line(f"#------------------------------------------------------------")
        self.__write_line(f"#    This code was auto-generated by: {self.__class__.__name__}")
        self.__write_line(f"#    Version: " + self.VERSION)
        self.__write_line(f"#------------------------------------------------------------")
    
    def wait(self, seconds: int):
        self.__write_line(f"sleep {seconds}")
    
    def __start_bitcoin_node(self, idx: NodeIndex):
        datadir = self.resources_allocator.get_bitcoin_node_datadir(idx)
        
        self.__write_line(f"mkdir -p {datadir}")
        self.__write_line(
            f"bitcoind"
            f"  -conf={BITCOIN_CONF_PATH}"
            f"  -port={self.resources_allocator.get_bitcoin_node_listen_port(idx)}"
            f"  -rpcport={self.resources_allocator.get_bitcoin_node_rpc_port(idx)}"
            f"  -datadir={datadir}"
            f"  -daemon"
            f"  -blockmaxweight={self.bitcoin_block_max_weight}"
            f"  -zmqpubrawblock=tcp://127.0.0.1:{self.resources_allocator.get_bitcoin_node_zmqpubrawblock_port(idx)}"
            f"  -zmqpubrawtx=tcp://127.0.0.1:{self.resources_allocator.get_bitcoin_node_zmqpubrawtx_port(idx)}"
        )
    
    def start_bitcoin_nodes(self):
        """
        generate code to start all bitcoin nodes (including miner)
        """
        self.__maybe_info("starting all bitcoin nodes")
        for client in self.bitcoin_clients.values():
            client.start()
    
    def stop_bitcoin_nodes(self):
        """
        generate code to stop all bitcoin nodes (including miner)
        """
        self.__maybe_info("stopping all bitcoin nodes")
        for client in self.bitcoin_clients.values():
            client.stop()
    
    def wait_until_bitcoin_nodes_ready(self):
        """generate code that waits until all bitcoin nodes are ready to get requests"""
        for idx, client in self.bitcoin_clients.items():
            self.__maybe_info(f"waiting until bitcoin node {idx} is ready")
            client.wait_until_ready()
    
    def wait_until_bitcoin_nodes_synced(self, height: int):
        """
        generate code that waits until all bitcoin nodes have reached the given height
        """
        self.__maybe_info(f"waiting until all bitcoin nodes have reached height {height}")
        for node_idx in self.topology:
            self.bitcoin_clients[node_idx].wait_until_synced(height)
    
    def connect_bitcoin_nodes_to_miner(self):
        self.__maybe_info("connecting all bitcoin nodes to the miner node")
        # connect all nodes to the miner
        miner_listen_port = self.resources_allocator.get_bitcoin_node_listen_port(BITCOIN_MINER_IDX)
        for node_idx in self.topology.keys():
            node_listen_port = self.resources_allocator.get_bitcoin_node_listen_port(node_idx)
            # miner adds node
            self.bitcoin_clients[BITCOIN_MINER_IDX].add_peer(host="localhost", port=node_listen_port)
            self.bitcoin_clients[node_idx].add_peer(host="localhost", port=miner_listen_port)
    
    def connect_bitcoin_nodes_in_circle(self):
        self.__maybe_info("connecting all bitcoin nodes in circle")
        all_nodes = sorted(self.topology.keys())
        num_nodes = len(all_nodes)
        for i in range(num_nodes):
            peer_1_idx = int(all_nodes[i % num_nodes])
            peer_2_idx = int(all_nodes[(i + 1) % num_nodes])
            peer_2_listen_port = self.resources_allocator.get_bitcoin_node_listen_port(peer_2_idx)
            self.bitcoin_clients[peer_1_idx].add_peer(host="localhost", port=peer_2_listen_port)
    
    def start_lightning_nodes(self) -> None:
        """generate code to start all lightning nodes"""
        self.__maybe_info("starting all lightning nodes")
        for idx, info in self.topology.items():
            self.lightning_clients[idx].start()
            self.__maybe_info(f"lightning node {idx} started")
    
    def stop_lightning_nodes(self) -> None:
        """generate code to stop all lightning nodes"""
        self.__maybe_info("stopping all lightning nodes")
        for idx, info in self.topology.items():
            self.lightning_clients[idx].stop()
            self.__maybe_info(f"lightning node {idx} stopped")
    
    def fill_blockchain(self, num_blocks) -> None:
        """
        generate code that fills the mempool and mine full blocks.
        the memool size is kept at around 2 times the block max weight
        """
        self.__maybe_info(f"Filling the blockchain ({num_blocks} blocks)")
        self.bitcoin_clients[BITCOIN_MINER_IDX].fill_blockchain(num_blocks)
    
    def fund_nodes(self) -> None:
        """generate code to fund nodes"""
        self.__maybe_info("funding lightning nodes")
        # mine enough blocks to fund the nodes and to unlock coinbase coins
        self.mine(num_blocks=100 + len(self.topology))
        
        for idx in self.topology:
            addr_bash_var = f"ADDR_{idx}"
            self.lightning_clients[idx].set_address(bash_var=addr_bash_var)
            # We give more funds to nodes that need to open many channels.
            # we fund these nodes with many small transactions instead of one big transaction,
            # so they have enough outputs to funds the different channels
            for _ in range(len(self.topology[idx]["peers"])):
                self.bitcoin_clients[BITCOIN_MINER_IDX].fund(amount=1, addr_bash_var=addr_bash_var)
        
        self.mine(10)
    
    def wait_for_funds(self) -> None:
        """generate code that waits until the nodes are synced and recognize their funds"""
        self.__maybe_info("waiting until lightning nodes are synchronized and have received their funds")
        for idx, info in self.topology.items():
            # we need to wait only for nodes that need to fund a channel
            if len(self.topology[idx]["peers"]) != 0:
                self.lightning_clients[idx].wait_for_funds()
    
    def establish_channels(self) -> None:
        """generate code to connect peers and establish all channels"""
        for node_idx, info in self.topology.items():
            for peer_idx in info["peers"]:
                self.__maybe_info(f"establishing channel from {node_idx} to {peer_idx}")
                self.lightning_clients[node_idx].establish_channel(
                    peer=self.lightning_clients[peer_idx],
                    peer_listen_port=self.resources_allocator.get_lightning_node_listen_port(peer_idx),
                    initial_balance_sat=INITIAL_CHANNEL_BALANCE_SAT,
                )
    
    def wait_for_funding_transactions(self):
        """
        generate code that waits until all funding transactions have propagated
        to the miner node's mempool
        """
        self.__maybe_info("waiting for funding transactions to enter miner's mempool")
        num_channels = sum(map(lambda entry: len(entry["peers"]), self.topology.values()))
        self.bitcoin_clients[BITCOIN_MINER_IDX].wait_for_txs_in_mempool(num_txs=num_channels)
    
    def wait_to_all_routes(self, sender_idx: NodeIndex, receiver_idx: NodeIndex, amount_msat: int):
        """
        wait until there is a known route from sender to receiver through each
        of the sender's peers
        """
        for peer_idx in self.topology[sender_idx]["peers"]:
            self.__maybe_info(
                f"waiting until there is a known route from {sender_idx} to {receiver_idx} via {peer_idx}"
            )
            self.lightning_clients[sender_idx].wait_to_route_via(
                src=self.lightning_clients[peer_idx],
                dest=self.lightning_clients[receiver_idx],
                amount_msat=amount_msat,
            )
    
    def make_payments(self, sender_idx: NodeIndex, receiver_idx: NodeIndex, num_payments: int, amount_msat: int):
        self.__maybe_info(
            f"making {num_payments} payments "
            f"between {sender_idx} (sender) and {receiver_idx} (receiver) with amount {amount_msat}msat"
        )
        self.lightning_clients[sender_idx].make_payments(
            receiver=self.lightning_clients[receiver_idx],
            num_payments=num_payments,
            amount_msat=amount_msat,
        )
    
    def reveal_preimages(self, node_idx: NodeIndex, peer_idx: NodeIndex = None):
        """
        make node with index 'node_idx' reveal any preimages it may hold.
        if 'peer_idx' is given, reveal only preimages held up from that peer
        """
        self.__maybe_info(
            f"Revealing preimages by node {node_idx}"
            +
            (f" to node {peer_idx}" if peer_idx else "")
        )
        self.lightning_clients[node_idx].reveal_preimages(
            peer=self.lightning_clients[peer_idx] if peer_idx else None
        )
    
    def print_node_htlcs(self, node_idx: NodeIndex):
        """
        print the number of htlcs the given node has on each of its channels
        """
        self.__maybe_info(f"number of HTLCs node {node_idx} has on each channel:")
        self.lightning_clients[node_idx].print_node_htlcs()
    
    def dump_channels_info(self, dir_path: str):
        """
        dump channels information of all lightning nodes into files in the given
        directory. file name format is 'node_<NODE_IDX>_channels'
        """
        self.__maybe_info("dumping channels information of all lightning nodes")
        self.__write_line(f"mkdir -p '{dir_path}'")
        for node_idx, client in self.lightning_clients.items():
            client.dump_channels_info(filepath=os.path.join(dir_path, f"node_{node_idx}_channels"))
    
    def stop_lightning_node(self, node_idx: NodeIndex):
        self.__maybe_info(f"stopping lightning node {node_idx}")
        self.lightning_clients[node_idx].stop()
    
    def stop_all_lightning_nodes(self) -> None:
        self.__maybe_info("stopping all lightning nodes")
        for client in self.lightning_clients.values():
            client.stop()
    
    def start_lightning_node_silent(self, node_idx: NodeIndex):
        self.__maybe_info(f"starting lightning node {node_idx} in silent mode")
        # silent mode is only supported for the c-lightning impl
        self.lightning_clients[node_idx] = ClightningCommandsGenerator(
            idx=node_idx,
            file=self.file,
            datadir=self.resources_allocator.get_lightning_node_datadir(node_idx),
            listen_port=self.resources_allocator.get_lightning_node_listen_port(node_idx),
            bitcoin_rpc_port=self.resources_allocator.get_bitcoin_node_rpc_port(node_idx),
            silent=True,
        )
        self.lightning_clients[node_idx].start()
    
    def close_all_node_channels(self, node_idx: NodeIndex):
        self.__maybe_info(f"closing all channels of node {node_idx}")
        self.lightning_clients[node_idx].close_all_channels()
    
    def sweep_funds(self, node_idx: NodeIndex):
        self.__maybe_info(f"sweeping funds of node {node_idx}")
        self.lightning_clients[node_idx].sweep_funds()
    
    def sweep_funds_all_lightning_nodes(self):
        """
        sweep funds for every lightning node.
        This could be useful to see exactly what outputs belong to the same
        entity, when analyzing a simulation's blockchain
        """
        self.__maybe_info("sweeping funds for every lightning node")
        for node_idx in self.lightning_clients.keys():
            self.sweep_funds(node_idx=node_idx)
    
    def advance_blockchain(self, num_blocks: int, block_time_sec: int, dir_path: str = None):
        """
        generate code to advance the blockchain by 'num_blocks' blocks.
        blocks are mined at a rate corresponding to block_time_sec until the
        blockchain reaches height CURRENT_HEIGHT+num_blocks.
        Note, this may be different than mining 'num_blocks' blocks, in case
        someone else is also mining.
        
        if dir_path is given, dump mempool txs to that dir
        """
        self.__maybe_info(
            f"mining: advancing blockchain by {num_blocks} blocks "
            f"with block_time={block_time_sec}sec"
        )
        if dir_path:
            self.__write_line(f"mkdir -p '{dir_path}'")
        self.bitcoin_clients[BITCOIN_MINER_IDX].advance_blockchain(
            num_blocks=num_blocks,
            block_time_sec=block_time_sec,
            dir_path=dir_path,
        )
    
    def dump_simulation_data(self, dir_path: str):
        """
        dump the following data to files in the given directory:
            - all blocks in the blockchain
            - all transactions in the blockchain
            - total balance of each node, that is not locked in a channel
        
        """
        self.__maybe_info(f"dumping simulation data")
        self.__write_line(f"mkdir -p '{dir_path}'")
        
        self.bitcoin_clients[BITCOIN_MINER_IDX].dump_blockchain(dir_path=dir_path)
        
        # dump nodes balances
        for idx in self.topology.keys():
            self.lightning_clients[idx].dump_balance(filepath=f"{dir_path}/nodes_balance")
    
    def mine(self, num_blocks):
        """generate code to mine num_blocks blocks. blocks are mined by the miner node"""
        self.bitcoin_clients[BITCOIN_MINER_IDX].mine(num_blocks)
    
    def info(self, msg: str) -> None:
        """generate command to echo the given message"""
        self.__write_line(f"echo \"{msg}\"")
    
    def __maybe_info(self, msg: str) -> None:
        """same as self.info but only generate command if verbose is True"""
        if self.verbose:
            self.info(msg)


def parse_args():
    """
    parse and return the program arguments
    """
    parser = argparse.ArgumentParser(description='Lightning commands generator')
    parser.add_argument(
        "--topology", action="store", metavar="TOPOLOGY_FILE", required=True,
        help="topology json file",
    )
    parser.add_argument(
        "--establish-channels", action='store_true',
        help="generate code to establish channels",
    )
    parser.add_argument(
        "--make-payments", type=int, nargs=4, metavar=("SENDER_ID", "RECEIVER_ID", "NUM_PAYMENTS", "AMOUNT_MSAT"),
        help="generate code to make payments between two nodes",
    )
    parser.add_argument(
        "--steal-attack", type=int, nargs=3, metavar=("SENDER_ID", "RECEIVER_ID", "NUM_BLOCKS"),
        help="generate code to execute the steal attack. NUM_BLOCKS are mined",
    )
    parser.add_argument(
        "--dump-data", type=str, metavar="DIRECTORY",
        help="generate code that dumps the simulation data to files in the given directory",
    )
    parser.add_argument(
        "--block-time", type=int, metavar="BLK_TIME_SEC", default=60,
        help="set the block time in seconds (the time until a new block is mined)."
             " applies to the attack code generation",
    )
    parser.add_argument(
        "--bitcoin-blockmaxweight", type=int, default=3996000,
        help="set bitcoin's block maximum weight",
    )
    parser.add_argument(
        "--simulation-number", type=int, default=CommandsGenerator.DEFAULT_SIMULATION,
        help="simulation number (int between 1 and 6). the simulation number affects the resources "
             "allocated to the different nodes. commands that were generated with different simulation "
             "numbers are able to run in parallel",
    )
    parser.add_argument(
        "--outfile", action="store", metavar="OUTFILE",
        help="output file to write commands to. default to stdout if not given",
    )
    
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.topology) as f:
        topology = json.load(f)
    
    outfile = open(args.outfile, mode="w") if args.outfile else sys.stdout
    
    cg = CommandsGenerator(
        file=outfile,
        topology=topology,
        bitcoin_block_max_weight=args.bitcoin_blockmaxweight,
        verbose=True,
        simulation_number=args.simulation_number,
    )
    cg.shebang()
    cg.generated_code_comment()
    cg.start_bitcoin_nodes()
    cg.wait_until_bitcoin_nodes_ready()
    cg.connect_bitcoin_nodes_to_miner()
    cg.connect_bitcoin_nodes_in_circle()
    cg.mine(10)
    cg.wait_until_bitcoin_nodes_synced(height=10)
    cg.start_lightning_nodes()
    
    if args.establish_channels:
        cg.fill_blockchain(40)  # 40 seems to be enough for the estimatesmartfee method to start working
        cg.fund_nodes()
        cg.wait_for_funds()
        cg.establish_channels()
        cg.wait_for_funding_transactions()
        # mine enough blocks so the channels reach NORMAL_STATE
        cg.advance_blockchain(num_blocks=30, block_time_sec=5)
        
        # to force channels announcements we stop all lightning nodes and start them over
        cg.stop_all_lightning_nodes()
        cg.start_lightning_nodes()
        cg.advance_blockchain(num_blocks=30, block_time_sec=5)
    
    if args.make_payments:
        sender_idx, receiver_idx, num_payments, amount_msat = args.make_payments
        cg.wait_to_all_routes(sender_idx, receiver_idx, amount_msat)
        cg.make_payments(*args.make_payments)
        cg.print_node_htlcs(node_idx=receiver_idx)
        if args.dump_data:
            cg.dump_channels_info(args.dump_data)
    
    if args.steal_attack:
        sender_idx, receiver_idx, num_blocks = args.steal_attack
        cg.stop_lightning_node(sender_idx)
        cg.start_lightning_node_silent(sender_idx)
        cg.reveal_preimages(node_idx=receiver_idx)
        cg.close_all_node_channels(receiver_idx)
        cg.advance_blockchain(
            num_blocks=num_blocks,
            block_time_sec=args.block_time,
            dir_path=args.dump_data if args.dump_data else None,
        )
    
    if args.dump_data:
        # before dumping we advance the blockchain by 100 blocks in case some
        # channels are still waiting to forget a peer
        cg.advance_blockchain(num_blocks=100, block_time_sec=5)
        cg.dump_simulation_data(dir_path=args.dump_data)
    
    cg.stop_all_lightning_nodes()
    cg.stop_bitcoin_nodes()
    
    cg.info("Done")
    
    # NOTE: we close outfile which may be stdout
    outfile.close()


if __name__ == "__main__":
    main()
