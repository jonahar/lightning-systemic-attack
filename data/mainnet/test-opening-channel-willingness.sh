#!/usr/bin/env bash

RESPONSES_DIR="$LN/data/mainnet/handshake-responses"
NODES_INFO_DIR="$LN/data/mainnet/ln-nodes-info"
mkdir -p "$RESPONSES_DIR"

connect_and_start_handshake() {
    full_address="$1" # ID@host:port
    id=$(echo "$full_address" | awk -F'@' '{print $1}')

    timeout 90s ./lightning-cli.sh connect $full_address >"$RESPONSES_DIR/$id-connect.json"
    status=$?
    if [[ $status == 124 ]]; then # 124 is the return code in case of timeout
        echo '{"timeout": true}' >"$RESPONSES_DIR/$id-connect.json"
        return
    elif [[ $status == 0 ]]; then
        # wait a bit and try to start handshake
        sleep 5
        timeout 60s ./lightning-cli.sh fundchannel_start $id 10000000 >"$RESPONSES_DIR/$id-fundchannel-start.json" # 0.1 BTC
        if [[ $? == 124 ]]; then
            echo '{"timeout": true}' >"$RESPONSES_DIR/$id-fundchannel-start.json"
        fi
    fi
}

connect_and_start_handshake_many() {
    full_addresses="$1" # list of ID@host:port
    for full_address in $full_addresses; do
        connect_and_start_handshake "$full_address" &
        sleep 3
    done
}

# read nodes information from files
full_addresses=
for json_file in $NODES_INFO_DIR/*; do
    full_addresses="$full_addresses $(cat $json_file | jq -r '.[] | "\(.pub_key)@\(.addresses[0].addr)"')"
done

# filter onion addresses and duplicate entries
full_addresses=$(echo $full_addresses | tr ' ' '\n' | sort -u | grep -v "onion" | xargs)
echo "$(wc -w <<<"$full_addresses") unique full_addresses"
connect_and_start_handshake_many "$full_addresses"

# find all potential peers (remove nodes with unknown/onion/ipv6 ip)
potential_peers=$(./lightning-cli.sh listnodes |
    jq -r '.nodes[] | "\(.nodeid)@\(.addresses[0].address):\(.addresses[0].port)" ' |
    grep -v "null" | grep -v "onion" | grep -v ":.*:")

echo "$(wc -w <<<"$potential_peers") potential peers"
echo "$potential_peers" >"$RESPONSES_DIR/potential_peers.txt"

connect_and_start_handshake_many "$potential_peers"
