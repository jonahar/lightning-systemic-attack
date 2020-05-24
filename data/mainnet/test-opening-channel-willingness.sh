#!/usr/bin/env bash

RESPONSES_DIR="$LN/data/mainnet/handshake-responses"
NODES_INFO_DIR="$LN/data/mainnet/ln-nodes-info"
mkdir -p "$RESPONSES_DIR"

num_peers_i_have() {
    ./lightning-cli.sh listpeers | jq ".peers" | jq length
}

connect_and_start_handshake() {
    full_address="$1" # ID@host:port
    id=$(echo "$full_address" | awk -F'@' '{print $1}')
    touch "$RESPONSES_DIR/$id-connect.json" # to mark that we tried to connect, even if the connect command times out
    timeout 60s ./lightning-cli.sh connect $full_address >"$RESPONSES_DIR/$id-connect.json"
    status=$?
    if [[ $status == 124 ]]; then
        echo "{\"message\": \"connection attempt timed out\"}" >"$RESPONSES_DIR/$id-connect.json"
    elif [[ $status == 0 ]]; then
        sleep 5
        timeout 30s ./lightning-cli.sh fundchannel_start $id 10000000 >"$RESPONSES_DIR/$id-fundchannel-start.json" # 0.1 BTC
    fi
}

connect_and_start_handshake_many() {
    full_addresses="$1" # list of ID@host:port
    for full_address in $full_addresses; do
        connect_and_start_handshake "$full_address" &
        sleep 1
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

# find more potential peers and select 1000 of them randomly
potential_peers=$(./lightning-cli.sh listnodes |
    jq -r '.nodes[] | "\(.nodeid)@\(.addresses[0].address):\(.addresses[0].port)" ' |
    grep -v "null" | grep -v "onion" | grep -v ":.*:" | head -n1000)

echo "$(wc -w <<<"$potential_peers") potential peers"
echo "$potential_peers" >"$RESPONSES_DIR/potential_peers.txt"

connect_and_start_handshake_many "$potential_peers"
