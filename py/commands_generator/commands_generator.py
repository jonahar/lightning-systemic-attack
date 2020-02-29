import argparse
import json
import sys
from typing import Any, Dict, TextIO

from commands_generator.clightning import ClightningCommandsGenerator
from commands_generator.eclair import EclairCommandsGenerator
from commands_generator.lightning import LightningCommandsGenerator
from commands_generator.lnd import LndCommandsGenerator
from commands_generator.resources_allocator import ResourcesAllocator
from datatypes import NodeIndex
from paths import BITCOIN_CLI_BINARY, BITCOIN_CONF_PATH

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
        
        # each LightningCommandsGenerator should generate lightning node commands
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
                v["peers"] = [int(p) for p in v["peers"]]
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
        return EclairCommandsGenerator(
            index=node_idx,
            file=self.file,
            lightning_dir=self.resources_allocator.get_lightning_node_datadir(node_idx),
            listen_port=self.resources_allocator.get_lightning_node_listen_port(node_idx),
            rpc_port=self.resources_allocator.get_lightning_node_rpc_port(node_idx),
            bitcoin_rpc_port=self.resources_allocator.get_bitcoin_node_rpc_port(node_idx),
            zmqpubrawblock_port=self.resources_allocator.get_bitcoin_node_zmqpubrawblock_port(node_idx),
            zmqpubrawtx_port=self.resources_allocator.get_bitcoin_node_zmqpubrawtx_port(node_idx),
            alias=alias,
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
                raise TypeError(f"unsupported client: {client}")
        
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
    
    def start_bitcoin_miner(self):
        self.__maybe_info("starting bitcoin miner node")
        self.__start_bitcoin_node(idx=BITCOIN_MINER_IDX)
    
    def stop_bitcoin_miner(self):
        self.__maybe_info("stopping bitcoin miner node")
        self.__write_line(f"{self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} stop")
    
    def start_bitcoin_nodes(self):
        self.__maybe_info("starting all bitcoin nodes")
        for idx in self.topology.keys():
            self.__start_bitcoin_node(idx=idx)
    
    def stop_bitcoin_nodes(self):
        self.__maybe_info("stopping all bitcoin nodes")
        for idx in self.topology.keys():
            self.__write_line(f"{self.__bitcoin_cli_cmd_prefix(idx)} stop")
    
    # TODO move this method, as well as all other bitcoin-cli commands to a new module `BitcoinCommandsGenerator`
    def __bitcoin_cli_cmd_prefix(self, node_idx: NodeIndex) -> str:
        return (
            f"{BITCOIN_CLI_BINARY} "
            f" -conf={BITCOIN_CONF_PATH} "
            f" -rpcport={self.resources_allocator.get_bitcoin_node_rpc_port(node_idx)} "
        )
    
    def wait_until_miner_is_ready(self):
        self.__maybe_info("waiting until miner node is ready")
        self.__write_line(f"""
    while [[ $({self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} echo "sanity" 2>/dev/null | jq -r ".[0]") != "sanity" ]]; do
        sleep 1;
    done
    """)
    
    def wait_until_bitcoin_nodes_synced(self, height: int):
        """
        generate code that waits until all bitcoin nodes have reached the given height
        """
        self.__maybe_info(f"waiting until all bitcoin nodes have reached height {height}")
        for node_idx in self.topology:
            self.__write_line(f"""
            while [[ $({self.__bitcoin_cli_cmd_prefix(node_idx)} -getinfo | jq ".blocks") -lt "{height}" ]]; do
                sleep 1
            done
            """)
    
    def connect_bitcoin_nodes_to_miner(self):
        self.__maybe_info("connecting all bitcoin nodes to the miner node")
        # connect all nodes to the miner
        miner_listen_port = self.resources_allocator.get_bitcoin_node_listen_port(BITCOIN_MINER_IDX)
        for node_idx in self.topology.keys():
            node_listen_port = self.resources_allocator.get_bitcoin_node_listen_port(node_idx)
            # miner adds node
            self.__write_line(
                f"{self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} addnode 127.0.0.1:{node_listen_port} add"
            )
            # node adds miner
            self.__write_line(
                f"{self.__bitcoin_cli_cmd_prefix(node_idx)} addnode 127.0.0.1:{miner_listen_port} add"
            )
    
    def connect_bitcoin_nodes_in_circle(self):
        self.__maybe_info("connecting all bitcoin nodes in circle")
        all_nodes = sorted(self.topology.keys())
        num_nodes = len(all_nodes)
        for i in range(num_nodes):
            peer_1_idx = int(all_nodes[i % num_nodes])
            peer_2_idx = int(all_nodes[(i + 1) % num_nodes])
            peer_2_listen_port = self.resources_allocator.get_bitcoin_node_listen_port(peer_2_idx)
            self.__write_line(
                f"{self.__bitcoin_cli_cmd_prefix(peer_1_idx)} addnode 127.0.0.1:{peer_2_listen_port} add"
            )
    
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
        self.mine(num_blocks=100 + num_blocks)  # at least 100 to unlock coinbase txs
        num_outputs = 10
        # usually for these kind of transactions this is the ratio between the block's weight and size
        block_weight_size_ratio = 2.7
        full_block_expected_size = self.bitcoin_block_max_weight / block_weight_size_ratio
        
        for i in range(num_outputs):
            self.__write_line(f"""MINER_ADDR_{i}=$({self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} getnewaddress)""")
        
        sendmany_arg = "{" + ",".join(f"""\\"$MINER_ADDR_{i}\\":0.1""" for i in range(num_outputs)) + "}"
        
        # we want to launch multiple sendmany requests at the same time, but we can't
        # do too too many either (bitcoind will fail). we use 10 at a time and wait
        # until all of them are finished. we run them in a sub-shell so they don't
        # put too much junk in our console
        
        self.__write_line(f"""
        for _ in $(seq 1 {num_blocks}); do
            while [[ $({self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} getmempoolinfo | jq -r ".bytes") -lt {int(2 * full_block_expected_size)} ]]; do
                (
                    for _ in $(seq 1 10); do
                        {self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} sendmany "" "{sendmany_arg}" >/dev/null &
                    done
                    wait
                )
            done
            {self.__get_mine_command(1)}
        done
        """)
    
    def fund_nodes(self) -> None:
        """generate code to fund nodes"""
        self.__maybe_info("funding lightning nodes")
        # mine enough blocks to fund the nodes and to unlock coinbase coins
        self.mine(num_blocks=100 + len(self.topology))
        
        for idx in self.topology:
            self.lightning_clients[idx].set_address(bash_var=f"ADDR_{idx}")
            
            # We give more funds to nodes that need to open many channels.
            # we fund these nodes with many small transactions instead of one big transaction,
            # so they have enough outputs to funds the different channels
            for _ in range(len(self.topology[idx]["peers"])):
                self.__write_line(f"{self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} sendtoaddress $ADDR_{idx} 1")
        
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
        self.__write_line(f"""
    while [[ $({self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} getmempoolinfo | jq -r ".size") != "{num_channels}" ]]; do
        sleep 1;
    done
    """)
    
    def wait_to_route(self, sender_idx: NodeIndex, receiver_idx: NodeIndex, amount_msat: int):
        self.__maybe_info(f"waiting until there is a known route from {sender_idx} to {receiver_idx}")
        self.lightning_clients[sender_idx].wait_to_route(
            receiver=self.lightning_clients[receiver_idx],
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
    
    def __set_blockchain_height(self):
        """set a bash variable BLOCKCHAIN_HEIGHT with the current height"""
        self.__write_line(
            f"""BLOCKCHAIN_HEIGHT=$({self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} -getinfo | jq ".blocks")""")
    
    def advance_blockchain(self, num_blocks: int, block_time_sec: int):
        """
        generate code to advance the blockchain by 'num_blocks' blocks.
        blocks are mined at a rate corresponding to block_time_sec until the
        blockchain reaches height CURRENT_HEIGHT+num_blocks.
        Note, this may be different than mining 'num_blocks' blocks, in case
        someone else is also mining
        """
        self.__maybe_info(
            f"mining: advancing blockchain by {num_blocks} blocks "
            f"with block_time={block_time_sec}sec"
        )
        self.__set_blockchain_height()
        self.__write_line(f"DEST_HEIGHT=$((BLOCKCHAIN_HEIGHT + {num_blocks}))")
        
        self.__write_line(f"""
    while [[ $({self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} -getinfo | jq ".blocks") -lt $DEST_HEIGHT ]]; do
        sleep {block_time_sec}
        {self.__get_mine_command(num_blocks=1)}
    done
        """)
    
    def dump_simulation_data(self, dir: str):
        """
        dump the following data to files in the given directory:
            - all blocks in the blockchain
            - all transactions in the blockchain
            - total balance of each node, that is not locked in a channel
        
        """
        self.__maybe_info(f"dumping simulation data")
        self.__write_line(f"mkdir -p '{dir}'")
        self.__write_line(f"cd '{dir}'")
        
        self.__set_blockchain_height()
        # dump blocks + transactions
        self.__write_line(f"""
    for i in $(seq 1 $BLOCKCHAIN_HEIGHT); do
        BLOCK_HASH=$({self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} getblockhash $i)
        {self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} getblock $BLOCK_HASH > block_$i.json
        TXS_IN_BLOCK=$(jq -r ".tx[]" < block_$i.json)
        for TX in $TXS_IN_BLOCK; do
            {self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} getrawtransaction $TX true > tx_$TX.json
        done
    done
        """)
        
        # dump nodes balances
        for idx in self.topology.keys():
            self.lightning_clients[idx].dump_balance(filepath="nodes_balance")
        
        self.__write_line(f"cd - > /dev/null")  # go back to where we were
    
    def __get_mine_command(self, num_blocks) -> str:
        """
        an helper method for mine(). this could be used by other methods if they want
        to inject a mine command in a more complex bash code (e.g. mine inside a bash for-loop)
        """
        return (
            f"{self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} generatetoaddress "
            f" {num_blocks} $({self.__bitcoin_cli_cmd_prefix(BITCOIN_MINER_IDX)} getnewaddress) >/dev/null"
        )
    
    def mine(self, num_blocks):
        """generate code to mine num_blocks blocks. blocks are mined by the miner node"""
        self.__write_line(self.__get_mine_command(num_blocks))
    
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
        help="set bitcoin's block maximum weight",
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
    cg.start_bitcoin_miner()
    cg.wait_until_miner_is_ready()
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
        # mine 10 blocks so the channels reach NORMAL_STATE
        cg.mine(num_blocks=10)
    
    if args.make_payments:
        sender_idx, receiver_idx, num_payments, amount_msat = args.make_payments
        cg.wait_to_route(sender_idx, receiver_idx, amount_msat)
        cg.make_payments(*args.make_payments)
        cg.print_node_htlcs(node_idx=receiver_idx)
    
    if args.steal_attack:
        sender_idx, receiver_idx, num_blocks = args.steal_attack
        cg.stop_lightning_node(sender_idx)
        cg.start_lightning_node_silent(sender_idx)
        cg.reveal_preimages(node_idx=receiver_idx)
        cg.close_all_node_channels(receiver_idx)
        cg.advance_blockchain(num_blocks=num_blocks, block_time_sec=args.block_time)
    
    if args.dump_data:
        # before dumping we advance the blockchain by 100 blocks in case some
        # channels are still waiting to forget a peer
        cg.advance_blockchain(num_blocks=100, block_time_sec=5)
        cg.dump_simulation_data(dir=args.dump_data)
    
    cg.stop_all_lightning_nodes()
    cg.stop_bitcoin_nodes()
    cg.stop_bitcoin_miner()
    
    cg.info("Done")
    
    # NOTE: we close outfile which may be stdout
    outfile.close()


if __name__ == "__main__":
    main()
