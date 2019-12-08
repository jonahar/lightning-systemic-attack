import argparse
import json
import os
import sys

LABPATH = os.path.expandvars("$LAB")
LNPATH = os.path.expandvars("$LNPATH")
LIGHTNING_DIR_BASE = os.path.join(LNPATH, "lightning-dirs")
LIGHTNING_CONF_PATH = os.path.join(LNPATH, "conf/lightning.conf")
BITCOIN_CONF_PATH = os.path.join(LNPATH, "conf/bitcoin.conf")
PORT_BASE = 10000
INITIAL_CHANNEL_BALANCE = 10000000  # 0.1 BTC

LIGHTNING_BINARY = os.path.join(LABPATH, "lightning/lightningd/lightningd")
LIGHTNING_BINARY_EVIL = os.path.join(LABPATH, "lightning-evil/lightningd/lightningd")


class CommandsGenerator:
    
    def __init__(self, file, topology: dict):
        """
        :param file: file-like object
        :param topology: topology dictionary
        """
        self.file = file
        self.topology = topology
    
    def __write_line(self, line: str) -> None:
        self.file.write(line)
        self.file.write("\n")
    
    def shebang(self) -> None:
        self.__write_line("#!/usr/bin/env bash")
    
    def start_nodes(self) -> None:
        """generate code to start lightning nodes"""
        for id, info in self.topology.items():
            alias = info["alias"] if "alias" in info else id
            evil_flag = ""
            binary = LIGHTNING_BINARY
            if "evil" in info and info["evil"]:
                evil_flag = "--evil"
                binary = LIGHTNING_BINARY_EVIL
            
            lightning_dir = os.path.join(LIGHTNING_DIR_BASE, id)
            port = PORT_BASE + int(id)
            
            self.__write_line(f"mkdir -p {lightning_dir}")
            self.__write_line(
                f"{binary} "
                f"  --conf={LIGHTNING_CONF_PATH}"
                f"  --lightning-dir={lightning_dir}"
                f"  --addr=localhost:{port}"
                f"  --alias={alias}"
                f"  --log-file=log"  # relative to lightning-dir
                f"  {evil_flag}"
                f"  --daemon"
            )
    
    def fund_nodes(self) -> None:
        """generate code to fund nodes"""
        # mine enough blocks to funds the nodes and to unlock coinbase coins
        self.__write_line(f"mine {100 + len(self.topology)}")
        
        for id in self.topology:
            self.__write_line(f"ADDR_{id}=$(lcli {id} newaddr | jq -r '.address')")
            
            # We give more funds to nodes that need to open many channels.
            # we fund these nodes with many small transactions instead of one big transaction,
            # so they have enough outputs to funds the different channels
            for _ in range(len(self.topology[id]["peers"])):
                self.__write_line(f"bitcoin-cli sendtoaddress $ADDR_{id} 1")
        
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
                peer_port = PORT_BASE + int(peer_id)
                self.__write_line(f"lcli {id} connect $ID_{peer_id} localhost:{peer_port}")
                self.__write_line(f"lcli {id} fundchannel $ID_{peer_id} {INITIAL_CHANNEL_BALANCE}")
        
        # mine 6 blocks so the channels reach NORMAL_STATE
        self.__write_line("mine 6")


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
    
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.topology) as f:
        topology = json.load(f)
    
    outfile = open(args.outfile, mode="w") if args.outfile else sys.stdout
    
    cg = CommandsGenerator(file=outfile, topology=topology)
    cg.shebang()
    cg.start_nodes()
    
    if args.establish_channels:
        cg.fund_nodes()
        cg.wait_for_funds()
        cg.establish_channels()
    
    # NOTE: we close outfile which may be stdout
    outfile.close()


if __name__ == "__main__":
    main()
