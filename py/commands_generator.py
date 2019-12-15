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

BITCOIN_MINER_ID = "0"


class CommandsGenerator:
    
    def __init__(self, file, topology: dict):
        """
        :param file: file-like object
        :param topology: topology dictionary
        """
        if BITCOIN_MINER_ID in topology:
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
    
    def __start_bitcoin_node(self, id: str):
        id_int = int(id)
        datadir = os.path.join(BITCOIN_DIR_BASE, id)
        
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
        self.__start_bitcoin_node(id=BITCOIN_MINER_ID)
    
    def start_bitcoin_nodes(self):
        for id in self.topology.keys():
            self.__start_bitcoin_node(id=id)
    
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
    
    def start_lightning_nodes(self) -> None:
        """generate code to start lightning nodes"""
        for id, info in self.topology.items():
            alias = info.get("alias", id)
            evil = info.get("evil", False)
            silent = info.get("silent", False)
            
            evil_flag = "--evil" if evil else ""
            silent_flag = "--silent" if silent else ""
            
            binary = LIGHTNING_BINARY
            log_level_flag = ""
            if evil or silent:
                binary = LIGHTNING_BINARY_EVIL
                log_level_flag = "--log-level=JONA"
            
            lightning_dir = os.path.join(LIGHTNING_DIR_BASE, id)
            port = LIGHTNING_RPC_PORT_BASE + int(id)
            
            self.__write_line(f"mkdir -p {lightning_dir}")
            self.__write_line(
                f"{binary} "
                f"  --conf={LIGHTNING_CONF_PATH}"
                f"  --lightning-dir={lightning_dir}"
                f"  --addr=localhost:{port}"
                f"  --alias={alias}"
                f"  --log-file=log"  # relative to lightning-dir
                f"  {evil_flag}"
                f"  {silent_flag}"
                f"  {log_level_flag}"
                f"  --bitcoin-rpcconnect=localhost"
                f"  --bitcoin-rpcport={BITCOIN_RPC_PORT_BASE + int(id)}"
                f"  --daemon"
            )
    
    def fund_nodes(self) -> None:
        """generate code to fund nodes"""
        # mine enough blocks to fund the nodes and to unlock coinbase coins
        self.__write_line(f"mine {100 + len(self.topology)}")
        
        for id in self.topology:
            self.__write_line(f"ADDR_{id}=$(lcli {id} newaddr | jq -r '.address')")
            
            # We give more funds to nodes that need to open many channels.
            # we fund these nodes with many small transactions instead of one big transaction,
            # so they have enough outputs to funds the different channels
            for _ in range(len(self.topology[id]["peers"])):
                self.__write_line(f"bcli {BITCOIN_MINER_ID} sendtoaddress $ADDR_{id} 1")
        
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
        echo "waiting for funds of node $i"
        while [[ $(lcli $i listfunds | jq -r ."outputs") == "[]" ]]; do
            sleep 1;
        done
    done
    """)
    
    def establish_channels(self) -> None:
        """generate code to connect peers and establish all channels"""
        # get full id for each node
        for id in self.topology:
            self.__write_line(f"ID_{id}=$(lcli {id} getinfo | jq -r '.id')")
        
        for id, info in self.topology.items():
            for peer_id in info["peers"]:
                peer_port = LIGHTNING_RPC_PORT_BASE + int(peer_id)
                self.__write_line(f"lcli {id} connect $ID_{peer_id} localhost:{peer_port}")
                self.__write_line(f"lcli {id} fundchannel $ID_{peer_id} {INITIAL_CHANNEL_BALANCE_SAT}")
    
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
    
    def make_payments(self, sender_idx: int, receiver_idx: int, num_payments: int, amount_msat: int):
        self.__write_line(f'SENDER_ID=$(lcli {sender_idx} getinfo | jq -r ".id")')
        self.__write_line(f'RECEIVER_ID=$(lcli {receiver_idx} getinfo | jq -r ".id")')
        self.__write_line("RISKFACTOR=1")
        
        self.__write_line(f"""
    # wait until there is a known route from sender to receiver
    while [[ $(ROUTE=$(lcli {sender_idx} getroute $RECEIVER_ID {amount_msat} $RISKFACTOR | jq -r ".route")) == "null" ]]; do
        sleep 1;
    done
        """)
        
        # make payments
        self.__write_line(f"""
    for i in $(seq 1 {num_payments}); do
        LABEL="invoice-label-$(date +%s.%N)"
        PAYMENT_HASH=$(lcli {receiver_idx} invoice $AMOUNT_MSAT $LABEL "" | jq -r ".payment_hash")
        ROUTE=$(lcli {sender_idx} getroute $RECEIVER_ID $AMOUNT_MSAT $RISKFACTOR | jq -r ".route")
        lcli {sender_idx} sendpay "$ROUTE" "$PAYMENT_HASH"
    done
        """)
    
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
        "--outfile", action="store", metavar="OUTFILE",
        help="output file to write commands to. default to stdout if not given",
    )
    parser.add_argument(
        "--establish-channels", action='store_true',
        help="generate code to establish channels too",
    )
    parser.add_argument(
        "--make-payments", type=int, nargs=4, metavar=("SENDER_ID", "RECEIVER_ID", "NUM_PAYMENTS", "AMOUNT_MSAT"),
        help="generate code to make payments between two nodes",
    )
    
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.topology) as f:
        topology = json.load(f)
    
    outfile = open(args.outfile, mode="w") if args.outfile else sys.stdout
    
    cg = CommandsGenerator(file=outfile, topology=topology)
    cg.shebang()
    cg.start_bitcoin_nodes()
    cg.start_bitcoin_miner()
    cg.info("waiting for miner node to be ready")
    cg.wait_until_miner_is_ready()
    cg.connect_miner_to_all_nodes()
    cg.start_lightning_nodes()
    
    if args.establish_channels:
        cg.fund_nodes()
        cg.wait_for_funds()
        cg.establish_channels()
        cg.info("waiting for funding transactions to enter mempool")
        cg.wait_for_funding_transactions()
        # mine 6 blocks so the channels reach NORMAL_STATE
        cg.mine(num_blocks=6)
    
    if args.make_payments:
        cg.make_payments(*args.make_payments)
    
    # NOTE: we close outfile which may be stdout
    outfile.close()


if __name__ == "__main__":
    main()
