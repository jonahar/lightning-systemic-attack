import argparse
import json
import os
import sys

LABPATH = os.path.expandvars("$LAB")
LN = os.path.expandvars("$LN")
LIGHTNING_DIR_BASE = os.path.join(LN, "lightning-dirs")
BITCOIN_DIR_BASE = os.path.join(LN, "bitcoin-dirs")
LIGHTNING_CONF_PATH = os.path.join(LN, "conf/lightning.conf")
BITCOIN_CONF_PATH = os.path.join(LN, "conf/bitcoin.conf")
LIGHTNING_RPC_PORT_BASE = 10000
BITCOIN_RPC_PORT_BASE = 18000
BITCOIN_PORT_BASE = 8300

INITIAL_CHANNEL_BALANCE_SAT = 10000000  # 0.1 BTC

LIGHTNING_BINARY = os.path.join(LABPATH, "lightning/lightningd/lightningd")
LIGHTNING_BINARY_EVIL = os.path.join(LABPATH, "lightning-evil/lightningd/lightningd")

BITCOIN_MINER_IDX = "0"


class CommandsGenerator:
    """
    A CommandsGenerator generates bash code to execute many lightning-related actions.
    it support:
        - start bitcoin nodes
        - connect bitcoin nodes to a central "miner" node
        - start lightning nodes
        - establish channels between lightning nodes
        - make lightning payments between nodes
    
    topology structure:
    
    {
      "ID1": {
        "peers": ["ID2", "ID4"],   // mandatory. may be an empty list
        "evil": false,             // optional. defaults to false
        "silent": false,           // optional. defaults to false
        "alias": "alice"           // optional. defaults to ID
      },
      "ID2": {...},
      "ID3": {...},
      "ID4": {...}
    }

    """
    
    def __init__(self, file, topology: dict):
        """
        :param file: file-like object
        :param topology: topology dictionary
        """
        if BITCOIN_MINER_IDX in topology:
            raise ValueError("Invalid id {BITCOIN_MINER_ID}: reserved for bitcoin miner node")
        self.file = file
        self.topology = topology
    
    def __write_line(self, line: str) -> None:
        self.file.write(line)
        self.file.write("\n")
    
    def shebang(self) -> None:
        self.__write_line("#!/usr/bin/env bash")
    
    def wait(self, seconds: int):
        self.__write_line(f"sleep {seconds}")
    
    def __start_bitcoin_node(self, idx: str):
        id_int = int(idx)
        datadir = os.path.join(BITCOIN_DIR_BASE, idx)
        
        self.__write_line(f"mkdir -p {datadir}")
        self.__write_line(
            f"bitcoind"
            f"  -conf={BITCOIN_CONF_PATH}"
            f"  -port={BITCOIN_PORT_BASE + id_int}"
            f"  -rpcport={BITCOIN_RPC_PORT_BASE + id_int}"
            f"  -datadir={datadir}"
            f"  -daemon"
        )
    
    def start_bitcoin_miner(self):
        self.__start_bitcoin_node(idx=BITCOIN_MINER_IDX)
    
    def start_bitcoin_nodes(self):
        for idx in self.topology.keys():
            self.__start_bitcoin_node(idx=idx)
    
    def wait_until_miner_is_ready(self):
        self.__write_line("""
    while [[ $(bcli 0 -getinfo 2>/dev/null | jq -r ".blocks") != "0" ]]; do
        sleep 1;
    done
    """)
    
    def connect_miner_to_all_nodes(self):
        for id in self.topology.keys():
            id_int = int(id)
            self.__write_line(
                f"bcli 0 addnode 127.0.0.1:{BITCOIN_PORT_BASE + id_int} onetry"
            )
    
    @staticmethod
    def __get_node_lightning_dir(node_idx: int) -> str:
        return os.path.join(LIGHTNING_DIR_BASE, str(node_idx))
    
    @staticmethod
    def __get_node_lightning_port(node_idx: int) -> int:
        return LIGHTNING_RPC_PORT_BASE + node_idx
    
    def start_lightning_node(
        self,
        idx: int,
        lightning_dir: str,
        binary: str,
        port: int,
        alias: str = None,
        evil: bool = False,
        silent: bool = False,
        log_level: str = None,
    ):
        evil_flag = "--evil" if evil else ""
        silent_flag = "--silent" if silent else ""
        alias_flag = f"--alias={alias}" if alias else ""
        log_level_flag = f"--log-level={log_level}" if log_level else ""
        
        self.__write_line(f"mkdir -p {lightning_dir}")
        self.__write_line(
            f"{binary} "
            f"  --conf={LIGHTNING_CONF_PATH}"
            f"  --lightning-dir={lightning_dir}"
            f"  --addr=localhost:{port}"
            f"  --log-file=log"  # relative to lightning-dir
            f"  {alias_flag}"
            f"  {evil_flag}"
            f"  {silent_flag}"
            f"  {log_level_flag}"
            f"  --bitcoin-rpcconnect=localhost"
            f"  --bitcoin-rpcport={BITCOIN_RPC_PORT_BASE + int(idx)}"
            f"  --daemon"
        )
    
    def start_lightning_nodes(self) -> None:
        """generate code to start all lightning nodes"""
        for idx, info in self.topology.items():
            node_idx = int(idx)
            alias = info.get("alias", id)
            evil = info.get("evil", False)
            silent = info.get("silent", False)
            
            evil_flag = "--evil" if evil else ""
            silent_flag = "--silent" if silent else ""
            
            binary = LIGHTNING_BINARY
            log_level = None
            if evil or silent:
                binary = LIGHTNING_BINARY_EVIL
                log_level = "JONA"
            
            self.start_lightning_node(
                idx=node_idx,
                lightning_dir=self.__get_node_lightning_dir(node_idx=node_idx),
                binary=binary,
                port=self.__get_node_lightning_port(node_idx=node_idx),
                alias=alias,
                evil=evil,
                silent=silent,
                log_level=log_level,
            )
    
    def fund_nodes(self) -> None:
        """generate code to fund nodes"""
        # mine enough blocks to fund the nodes and to unlock coinbase coins
        self.__write_line(f"mine {100 + len(self.topology)}")
        
        for idx in self.topology:
            self.__write_line(f"ADDR_{idx}=$(lcli {idx} newaddr | jq -r '.address')")
            
            # We give more funds to nodes that need to open many channels.
            # we fund these nodes with many small transactions instead of one big transaction,
            # so they have enough outputs to funds the different channels
            for _ in range(len(self.topology[idx]["peers"])):
                self.__write_line(f"bcli {BITCOIN_MINER_IDX} sendtoaddress $ADDR_{idx} 1")
        
        self.__write_line("mine 10")
    
    def wait_for_funds(self) -> None:
        """generate code that waits until the nodes are synced and recognize their funds"""
        # we need to wait only for nodes that need to fund a channel
        ids_list_str = " ".join(
            filter(
                lambda id: len(self.topology[id]["peers"]) != 0,
                self.topology.keys()
            )
        )
        
        self.__write_line(f"""
    for i in {ids_list_str}; do
        while [[ $(lcli $i listfunds | jq -r ."outputs") == "[]" ]]; do
            sleep 1;
        done
    done
    """)
    
    def establish_channels(self) -> None:
        """generate code to connect peers and establish all channels"""
        # get full id for each node
        for node_idx in self.topology:
            self.__write_line(f"ID_{node_idx}=$(lcli {node_idx} getinfo | jq -r '.id')")
        
        for node_idx, info in self.topology.items():
            for peer_id in info["peers"]:
                peer_port = LIGHTNING_RPC_PORT_BASE + int(peer_id)
                self.__write_line(f"lcli {node_idx} connect $ID_{peer_id} localhost:{peer_port}")
                self.__write_line(f"lcli {node_idx} fundchannel $ID_{peer_id} {INITIAL_CHANNEL_BALANCE_SAT}")
    
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
    
    def __set_riskfactor(self):
        self.__write_line("RISKFACTOR=1")
    
    def __set_receiver_id(self, receiver_idx: int):
        self.__write_line(f'RECEIVER_ID=$(lcli {receiver_idx} getinfo | jq -r ".id")')
    
    def wait_to_route(self, sender_idx: int, receiver_idx: int, amount_msat: int):
        self.__set_riskfactor()
        self.__set_receiver_id(receiver_idx)
        self.__write_line(f"""
        while [[ "$(lcli {sender_idx} getroute $RECEIVER_ID {amount_msat} $RISKFACTOR | jq -r ".route")" == "null" ]]; do
            sleep 1;
        done
            """)
    
    def make_payments(self, sender_idx: int, receiver_idx: int, num_payments: int, amount_msat: int):
        self.__set_riskfactor()
        self.__set_receiver_id(receiver_idx)
        self.__write_line(f"""
    for i in $(seq 1 {num_payments}); do
        LABEL="invoice-label-$(date +%s.%N)"
        PAYMENT_HASH=$(lcli {receiver_idx} invoice $AMOUNT_MSAT $LABEL "" | jq -r ".payment_hash")
        ROUTE=$(lcli {sender_idx} getroute $RECEIVER_ID {amount_msat} $RISKFACTOR | jq -r ".route")
        lcli {sender_idx} sendpay "$ROUTE" "$PAYMENT_HASH"
    done
        """)
    
    def stop_lightning_node(self, node_idx: int):
        self.__write_line(f"lcli {node_idx} stop")
    
    def start_lightning_node_silent(self, node_idx: int):
        self.start_lightning_node(
            idx=node_idx,
            lightning_dir=self.__get_node_lightning_dir(node_idx),
            binary=LIGHTNING_BINARY_EVIL,
            port=self.__get_node_lightning_port(node_idx),
            silent=True,
        )
    
    def close_all_node_channels(self, node_idx):
        pass;
        self.__write_line(
            f"""PEER_IDS=$(lcli {node_idx} listpeers | jq -r ".peers[] | .id")"""
        )
        self.__write_line(f"""
    for id in $PEER_IDS; do
        lcli {node_idx} close $id
    done
        """)
    
    def mine_many(self, num_blocks: int, block_time_sec: int = 60):
        """
        generate code to mine num_blocks blocks every block_time_sec seconds
        """
        self.__write_line(f"""
    for i in $(seq 1 {num_blocks}); do
        mine 1; sleep {block_time_sec};
    done
        """)
        # we have a redundant sleep at the end. Nu shoin... I rather keep it simple than efficient
    
    def dump_simulation_data(self, dir: str):
        """
        dump the following data to files in the given directory:
            - all blocks in the blockchain
            - all transactions in the blockchain
            - total balance of each node, that is not locked in a channel
        
        """
        self.__write_line(f"mkdir -p '{dir}'")
        self.__write_line(f"cd '{dir}'")
        
        self.__write_line("""BLOCKCHAIN_HEIGHT=$(bcli 0 -getinfo | jq ".blocks")""")
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
        
        # dump nodes balances that are not locked in channels
        node_ids = " ".join(self.topology.keys())
        self.__write_line(f"""
    for i in {node_ids}; do
        printf "node ${{i}} balance: " >> nodes_balance
        lcli $i listfunds | jq '.outputs[] | .value' | jq -s add >> nodes_balance
    done
        """)
        
        self.__write_line(f"cd ..")  # go back to where we were
    
    def mine(self, num_blocks):
        self.__write_line(f"mine {num_blocks}")
    
    def info(self, msg):
        self.__write_line(f"echo \"{msg}\"")


def parse_args():
    """
    parse and return the program arguments
    """
    parser = argparse.ArgumentParser(description='Lightning commands generator',
                                     formatter_class=argparse.RawTextHelpFormatter)
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
        "--outfile", action="store", metavar="OUTFILE",
        help="output file to write commands to. default to stdout if not given",
    )
    
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.topology) as f:
        topology = json.load(f)
    
    outfile = open(args.outfile, mode="w") if args.outfile else sys.stdout
    
    cg = CommandsGenerator(file=outfile, topology=topology)
    cg.shebang()
    cg.info("starting all bitcoin nodes")
    cg.start_bitcoin_nodes()
    cg.start_bitcoin_miner()
    cg.info("waiting until miner node is ready")
    cg.wait_until_miner_is_ready()
    cg.info("connecting miner to all other bitcoin nodes")
    cg.connect_miner_to_all_nodes()
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
        # mine 6 blocks so the channels reach NORMAL_STATE
        cg.mine(num_blocks=6)
    
    if args.make_payments:
        sender_idx, receiver_idx, num_payments, amount_msat = args.make_payments
        cg.info("waiting until there is a known route from sender to receiver")
        cg.wait_to_route(sender_idx, receiver_idx, amount_msat)
        cg.info("making payments")
        cg.make_payments(*args.make_payments)
    
    if args.steal_attack:
        sender_idx, receiver_idx, num_blocks = args.steal_attack
        cg.info(f"stopping lightning node {sender_idx}")
        cg.stop_lightning_node(sender_idx)
        cg.info(f"starting lightning node {sender_idx} in silent mode")
        cg.start_lightning_node_silent(sender_idx)
        cg.info(f"closing all channels of node {receiver_idx}")
        cg.close_all_node_channels(receiver_idx)
        cg.info(f"slowly mining {num_blocks} blocks")
        cg.mine_many(num_blocks)
    
    if args.dump_data:
        cg.info(f"dumping simulation data")
        cg.dump_simulation_data(dir=args.dump_data)
    
    # NOTE: we close outfile which may be stdout
    outfile.close()


if __name__ == "__main__":
    main()
