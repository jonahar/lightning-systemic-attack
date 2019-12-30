import argparse
import json
import sys
from typing import Dict, TextIO

from commands_generator.clightning import ClightningCommandsGenerator
from commands_generator.config_constants import *
from datatypes import NodeIndex, NodeIndexStr
from commands_generator.lightning import LightningCommandsGenerator


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
    
    def __init__(self, file: TextIO, topology: dict, bitcoin_block_max_weight: int):
        """
        :param file: file-like object
        :param topology: topology dictionary
        """
        if BITCOIN_MINER_IDX in topology:
            raise ValueError("Invalid id {BITCOIN_MINER_ID}: reserved for bitcoin miner node")
        self.file = file
        self.topology = topology
        self.bitcoin_block_max_weight = bitcoin_block_max_weight
        
        # each LightningCommandsGenerator should generate lightning node commands
        # according to the node's chosen implementation
        self.clients: Dict[NodeIndexStr, LightningCommandsGenerator] = self.__init_clients()
    
    def __init_clients(self) -> Dict[NodeIndexStr, LightningCommandsGenerator]:
        """
        build LightningCommandsGenerator for each node in the topology.
        the concrete implementation is determined by the node's config
        """
        clients = {}
        for idx, info in self.topology.items():
            node_idx = int(idx)
            alias = info.get("alias", idx)
            client = info.get("client", "c-lightning")
            lightning_dir = self.get_lightning_node_dir(node_idx=node_idx)
            
            if client == "c-lightning":
                evil = info.get("evil", False)
                silent = info.get("silent", False)
                clients[idx] = ClightningCommandsGenerator(
                    idx=node_idx,
                    file=self.file,
                    lightning_dir=lightning_dir,
                    listen_port=self.get_lightning_node_listen_port(node_idx),
                    bitcoin_rpc_port=self.__get_bitcoin_node_rpc_port(node_idx),
                    alias=alias,
                    evil=evil,
                    silent=silent,
                )
            else:
                raise TypeError(f"unsupported client: {client}")
        
        return clients
    
    @staticmethod
    def get_lightning_node_dir(node_idx: int) -> str:
        return os.path.join(LIGHTNING_DIR_BASE, str(node_idx))
    
    @staticmethod
    def get_lightning_node_rpc_port(node_idx: int) -> int:
        return LIGHTNING_RPC_PORT_BASE + node_idx
    
    @staticmethod
    def get_lightning_node_listen_port(node_idx: int) -> int:
        return LIGHTNING_LISTEN_PORT_BASE + node_idx
    
    def __write_line(self, line: str) -> None:
        self.file.write(line)
        self.file.write("\n")
    
    @staticmethod
    def __get_bitcoin_node_dir(node_idx: int) -> str:
        return os.path.join(BITCOIN_DIR_BASE, str(node_idx))
    
    @staticmethod
    def __get_bitcoin_node_rpc_port(node_idx: int) -> int:
        return BITCOIN_RPC_PORT_BASE + node_idx
    
    @staticmethod
    def __get_bitcoin_node_listen_port(node_idx: int) -> int:
        return BITCOIN_LISTEN_PORT_BASE + node_idx
    
    @staticmethod
    def __get_bitcoin_node_zmqpubrawblock_port(node_idx: int) -> int:
        return ZMQPUBRAWBLOCK_PORT_BASE + node_idx
    
    @staticmethod
    def __get_bitcoin_node_zmqpubrawtx_port(node_idx: int) -> int:
        return ZMQPUBRAWTX_PORT_BASE + node_idx
    
    def shebang(self) -> None:
        self.__write_line("#!/usr/bin/env bash")
    
    def generated_code_comment(self) -> None:
        self.__write_line(f"#------------------------------------------------------------")
        self.__write_line(f"#    This code was auto-generated by: {self.__class__.__name__}")
        self.__write_line(f"#    Version: A.113")
        self.__write_line(f"#------------------------------------------------------------")
    
    def wait(self, seconds: int):
        self.__write_line(f"sleep {seconds}")
    
    def __start_bitcoin_node(self, idx: int):
        datadir = self.__get_bitcoin_node_dir(idx)
        
        self.__write_line(f"mkdir -p {datadir}")
        self.__write_line(
            f"bitcoind"
            f"  -conf={BITCOIN_CONF_PATH}"
            f"  -port={self.__get_bitcoin_node_listen_port(idx)}"
            f"  -rpcport={self.__get_bitcoin_node_rpc_port(idx)}"
            f"  -datadir={datadir}"
            f"  -daemon"
            f"  -blockmaxweight={self.bitcoin_block_max_weight}"
            f"  -zmqpubrawblock=tcp://127.0.0.1:{self.__get_bitcoin_node_zmqpubrawblock_port(idx)}"
            f"  -zmqpubrawtx=tcp://127.0.0.1:{self.__get_bitcoin_node_zmqpubrawtx_port(idx)}"
        )
    
    def start_bitcoin_miner(self):
        self.__start_bitcoin_node(idx=int(BITCOIN_MINER_IDX))
    
    def start_bitcoin_nodes(self):
        for idx in self.topology.keys():
            self.__start_bitcoin_node(idx=int(idx))
    
    def wait_until_miner_is_ready(self):
        self.__write_line("""
    while [[ $(bcli 0 -getinfo 2>/dev/null | jq -r ".blocks") != "0" ]]; do
        sleep 1;
    done
    """)
    
    def wait_until_bitcoin_nodes_synced(self, height: int):
        """
        generate code that waits until all bitcoin nodes have reached the given height
        """
        node_ids = " ".join(self.topology.keys())
        
        self.__write_line(f"""
    for i in {node_ids}; do
        while [[ $(bcli $i -getinfo | jq ".blocks") -lt "{height}" ]]; do
            sleep 1
        done
    done
        """)
    
    def connect_bitcoin_nodes_to_miner(self):
        # connect all nodes to the miner
        miner_idx = int(BITCOIN_MINER_IDX)
        miner_listen_port = self.__get_bitcoin_node_listen_port(miner_idx)
        for node_idx in self.topology.keys():
            node_listen_port = self.__get_bitcoin_node_listen_port(int(node_idx))
            # miner adds node
            self.__write_line(
                f"bcli {miner_idx} addnode 127.0.0.1:{node_listen_port} add"
            )
            # node adds miner
            self.__write_line(
                f"bcli {node_idx} addnode 127.0.0.1:{miner_listen_port} add"
            )
    
    def connect_bitcoin_nodes_in_circle(self):
        all_nodes = sorted(self.topology.keys())
        num_nodes = len(all_nodes)
        for i in range(num_nodes):
            peer_1_idx = int(all_nodes[i % num_nodes])
            peer_2_idx = int(all_nodes[(i + 1) % num_nodes])
            peer_2_listen_port = self.__get_bitcoin_node_listen_port(peer_2_idx)
            self.__write_line(
                f"bcli {peer_1_idx} addnode 127.0.0.1:{peer_2_listen_port} add"
            )
    
    def start_lightning_nodes(self) -> None:
        """generate code to start all lightning nodes"""
        for idx, info in self.topology.items():
            self.clients[idx].start()
    
    def fund_nodes(self) -> None:
        """generate code to fund nodes"""
        # mine enough blocks to fund the nodes and to unlock coinbase coins
        self.__write_line(f"mine {100 + len(self.topology)}")
        
        for idx in self.topology:
            self.clients[idx].set_address(bash_var=f"ADDR_{idx}")
            
            # We give more funds to nodes that need to open many channels.
            # we fund these nodes with many small transactions instead of one big transaction,
            # so they have enough outputs to funds the different channels
            for _ in range(len(self.topology[idx]["peers"])):
                self.__write_line(f"bcli {BITCOIN_MINER_IDX} sendtoaddress $ADDR_{idx} 1")
        
        self.mine(10)
    
    def wait_for_funds(self) -> None:
        """generate code that waits until the nodes are synced and recognize their funds"""
        for idx, info in self.topology.items():
            # we need to wait only for nodes that need to fund a channel
            if len(self.topology[idx]["peers"]) != 0:
                self.clients[idx].wait_for_funds()
    
    def establish_channels(self) -> None:
        """generate code to connect peers and establish all channels"""
        for idx, info in self.topology.items():
            for peer_idx in info["peers"]:
                self.clients[idx].establish_channel(
                    peer=self.clients[peer_idx],
                    peer_listen_port=self.get_lightning_node_listen_port(int(peer_idx))
                )
    
    def wait_for_funding_transactions(self):
        """
        generate code that waits until all funding transactions have propagated
        to the miner node's mempool
        """
        num_channels = sum(map(lambda entry: len(entry["peers"]), self.topology.values()))
        self.__write_line(f"""
    while [[ $(bcli 0 getmempoolinfo | jq -r ."size") != "{num_channels}" ]]; do
        sleep 1;
    done
    """)
    
    def wait_to_route(self, sender_idx: int, receiver_idx: int, amount_msat: int):
        self.clients[str(sender_idx)].wait_to_route(
            receiver=self.clients[str(receiver_idx)],
            amount_msat=amount_msat,
        )
    
    def make_payments(self, sender_idx: int, receiver_idx: int, num_payments: int, amount_msat: int):
        self.clients[str(sender_idx)].make_payments(
            receiver=self.clients[str(receiver_idx)],
            num_payments=num_payments,
            amount_msat=amount_msat,
        )
    
    def print_node_htlcs(self, node_idx: int):
        """
        print the number of htlcs the given node has on each of its channels
        """
        self.clients[str(node_idx)].print_node_htlcs()
    
    def stop_lightning_node(self, node_idx: int):
        self.clients[str(node_idx)].stop()
    
    def start_lightning_node_silent(self, node_idx: int):
        # silent mode is only supported for the c-lightning impl
        self.clients[node_idx] = ClightningCommandsGenerator(
            idx=node_idx,
            file=self.file,
            lightning_dir=self.get_lightning_node_dir(node_idx),
            listen_port=self.get_lightning_node_listen_port(node_idx),
            bitcoin_rpc_port=self.__get_bitcoin_node_rpc_port(node_idx),
            silent=True,
        )
        self.clients[node_idx].start()
    
    def close_all_node_channels(self, node_idx: NodeIndex):
        self.clients[str(node_idx)].close_all_channels()
    
    def __set_blockchain_height(self):
        """set a bash variable BLOCKCHAIN_HEIGHT with the current height"""
        self.__write_line("""BLOCKCHAIN_HEIGHT=$(bcli 0 -getinfo | jq ".blocks")""")
    
    def advance_blockchain(self, num_blocks: int, block_time_sec: int):
        """
        generate code to advance the blockchain by 'num_blocks' blocks.
        blocks are mined at a rate corresponding to block_time_sec until the
        blockchain reaches height CURRENT_HEIGHT+num_blocks.
        Note, this may be different than mining 'num_blocks' blocks, in case
        someone else is also mining
        """
        self.__set_blockchain_height()
        self.__write_line(f"DEST_HEIGHT=$((BLOCKCHAIN_HEIGHT + {num_blocks}))")
        
        self.__write_line(f"""
    while [[ $(bcli 0 -getinfo | jq ".blocks") -lt $DEST_HEIGHT ]]; do
        sleep {block_time_sec}
        mine 1
    done
        """)
    
    def dump_simulation_data(self, dir: str):
        """
        dump the following data to files in the given directory:
            - all blocks in the blockchain
            - all transactions in the blockchain
            - total balance of each node, that is not locked in a channel
        
        """
        self.__write_line(f"mkdir -p '{dir}'")
        self.__write_line(f"cd '{dir}'")
        
        self.__set_blockchain_height()
        # dump blocks + transactions
        self.__write_line("""
    for i in $(seq 1 $BLOCKCHAIN_HEIGHT); do
        getblock $i > block_$i.json
        TXS_IN_BLOCK=$(jq -r ".tx[]" < block_$i.json)
        for TX in $TXS_IN_BLOCK; do
            gettransaction $TX > tx_$TX.json
        done
    done
        """)
        
        # dump nodes balances
        for idx in self.topology.keys():
            self.clients[idx].dump_balance(filepath="nodes_balance")
        
        self.__write_line(f"cd - > /dev/null")  # go back to where we were
    
    def mine(self, num_blocks):
        self.__write_line(f"mine {num_blocks}")
    
    def info(self, msg):
        self.__write_line(f"echo \"{msg}\"")


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
    )
    cg.shebang()
    cg.generated_code_comment()
    cg.info("starting all bitcoin nodes")
    cg.start_bitcoin_nodes()
    cg.start_bitcoin_miner()
    cg.info("waiting until miner node is ready")
    cg.wait_until_miner_is_ready()
    cg.info("connecting bitcoin nodes to the miner node")
    cg.connect_bitcoin_nodes_to_miner()
    cg.info("connecting all nodes in circle")
    cg.connect_bitcoin_nodes_in_circle()
    cg.mine(10)
    cg.info("waiting until nodes are synced with miner node")
    cg.wait_until_bitcoin_nodes_synced(height=10)
    cg.info("starting lightning nodes")
    cg.start_lightning_nodes()
    
    if args.establish_channels:
        cg.info("funding lightning nodes")
        cg.fund_nodes()
        cg.info("waiting until lightning nodes are synchronized and have received their funds")
        cg.wait_for_funds()
        cg.info("establishing lightning channels")
        cg.establish_channels()
        cg.info("waiting for funding transactions to enter miner's mempool")
        cg.wait_for_funding_transactions()
        # mine 10 blocks so the channels reach NORMAL_STATE
        cg.mine(num_blocks=10)
    
    if args.make_payments:
        sender_idx, receiver_idx, num_payments, amount_msat = args.make_payments
        cg.info("waiting until there is a known route from sender to receiver")
        cg.wait_to_route(sender_idx, receiver_idx, amount_msat)
        cg.info("making payments")
        cg.make_payments(*args.make_payments)
        cg.info(f"number of HTLCs node {receiver_idx} has on each channel:")
        cg.print_node_htlcs(node_idx=receiver_idx)
    
    if args.steal_attack:
        sender_idx, receiver_idx, num_blocks = args.steal_attack
        cg.info(f"stopping lightning node {sender_idx}")
        cg.stop_lightning_node(sender_idx)
        cg.info(f"starting lightning node {sender_idx} in silent mode")
        cg.start_lightning_node_silent(sender_idx)
        cg.info(f"closing all channels of node {receiver_idx}")
        cg.close_all_node_channels(receiver_idx)
        cg.info(f"slowly mining {num_blocks} blocks")
        cg.advance_blockchain(num_blocks=num_blocks, block_time_sec=args.block_time)
    
    if args.dump_data:
        # before dumping we advance the blockchain by 100 blocks in case some
        # channels are still waiting to forget a peer
        cg.info(f"quickly mining 100 blocks")
        cg.advance_blockchain(num_blocks=100, block_time_sec=5)
        cg.info(f"dumping simulation data")
        cg.dump_simulation_data(dir=args.dump_data)
    
    cg.info("simulation ended")
    
    # NOTE: we close outfile which may be stdout
    outfile.close()


if __name__ == "__main__":
    main()
