import json
import os
import sys

LNPATH = os.path.expandvars("$LNPATH")
LIGHTNING_DIR_BASE = os.path.join(LNPATH, "lightning-dirs")
LIGHTNING_CONF_PATH = os.path.join(LNPATH, "conf/lightning.conf")
BITCOIN_CONF_PATH = os.path.join(LNPATH, "conf/bitcoin.conf")
PORT_BASE = 10000
INITIAL_CHANNEL_BALANCE = 10000000  # 0.1 BTC


def shebang() -> None:
    print("#!/usr/bin/env bash")


def start_ln_nodes_commands(topology: dict) -> None:
    # code to run nodes
    for id, info in topology.items():
        alias = info["alias"] if "alias" in info else id
        evil = info["evil"] if "evil" in info else False
        evil_flag = "--evil" if evil else ""
        lightning_dir = os.path.join(LIGHTNING_DIR_BASE, id)
        port = PORT_BASE + int(id)
        
        print(f"mkdir -p {lightning_dir}")
        print(
            f"lightningd "
            f"  --conf={LIGHTNING_CONF_PATH}"
            f"  --lightning-dir={lightning_dir}"
            f"  --addr=localhost:{port}"
            f"  --alias={alias}"
            f"  --log-file=log"  # relative to lightning-dir
            f"  {evil_flag}"
            f"  --daemon"
        )


def fund_nodes_commands(topology: dict) -> None:
    # mine enough blocks to funds the nodes and to unlock coinbase coins
    print(f"mine {100 + len(topology)}")
    
    for id in topology:
        print(f"ADDR_{id}=$(lcli {id} newaddr | jq -r '.address')")
        amount = 1
        print(f"bitcoin-cli sendtoaddress $ADDR_{id} {amount}")
    print("mine 10")


def wait_for_fund_commands(topology: dict) -> None:
    ids_list_str = " ".join(topology.keys())
    print(f"""
for i in {ids_list_str}; do
    echo "waiting for funds of node $i"
    while [[ $(lcli $i listfunds | jq -r ."outputs") == "[]" ]]; do
        sleep 1;
    done
done
""")


def establish_channel_commands(topology: dict) -> None:
    # get full id for each node
    for id in topology:
        print(f"ID_{id}=$(lcli {id} getinfo | jq -r '.id')")
    
    for id, info in topology.items():
        for peer_id in info["peers"]:
            peer_port = PORT_BASE + int(peer_id)
            print(f"lcli {id} connect $ID_{peer_id} localhost:{peer_port}")
            print(f"lcli {id} fundchannel $ID_{peer_id} {INITIAL_CHANNEL_BALANCE}")
    
    # mine 6 blocks so the channels reach NORMAL_STATE
    print("mine 6")


def usage():
    print(f"usage: {sys.argv[0]} TOPOLOGY_FILE")


def main(topology_file: str) -> None:
    with open(topology_file) as f:
        topology = json.load(f)
    
    shebang()
    start_ln_nodes_commands(topology)
    fund_nodes_commands(topology)
    wait_for_fund_commands(topology)
    establish_channel_commands(topology)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
        exit(1)
    main(topology_file=sys.argv[1])
