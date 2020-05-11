import json
import os

from paths import LN

num_attacker_sending_nodes = 5
num_attacker_receiving_nodes = num_attacker_sending_nodes
num_victims_values = [5, 10, 20]
blockmaxweight_values = [1_000_000, 2_000_000, 4_000_000]

min_simulation_num = 1
max_simulation_num = 5
num_payments_multiplier = 3

for num_victims in num_victims_values:
    # generate topology
    # sending-node ids start with 1
    # receiving-node ids start with 3
    # victim ids start with 4
    
    sending_node_ids = [f"1{i}" for i in range(1, num_attacker_sending_nodes + 1)]
    receiving_node_ids = [f"3{i}" for i in range(1, num_attacker_receiving_nodes + 1)]
    victim_node_ids = [f"4{i}" for i in range(1, num_victims + 1)]
    
    topology = {}
    
    for sending_node_id in sending_node_ids:
        topology[sending_node_id] = {
            "client": "c-lightning",
            "evil": True,
            "peers": victim_node_ids,
            "type": "attacker-sending"
            
        }
    
    for receiving_node_id in receiving_node_ids:
        topology[receiving_node_id] = {
            "client": "c-lightning",
            "evil": True,
            "peers": [],
            "type": "attacker-receiving",
        }
    
    for victim_node_id in victim_node_ids:
        topology[victim_node_id] = {
            "client": "lnd",
            "peers": receiving_node_ids,
            "type": "victim"
        }
    
    topology_filename = f"topology-{num_attacker_sending_nodes}-{num_victims}-{num_attacker_receiving_nodes}.json"
    topology_fullpath = os.path.join(LN, "topologies", topology_filename)
    with open(topology_fullpath, mode="w") as f:
        json.dump(topology, f, sort_keys=True, indent=4)
    
    # generate simulation script
    num_payments = int(483 * num_payments_multiplier)
    for blockmaxweight in blockmaxweight_values:
        script_name = (
            f"steal-attack-{num_attacker_sending_nodes}-{num_victims}-{num_attacker_receiving_nodes}-blockmaxweight={blockmaxweight}"
        )
        script_path = os.path.join(LN, "simulations", f"{script_name}.sh")
        simulation_num = (
            min_simulation_num + (int(num_victims / 10) % (max_simulation_num - min_simulation_num + 1))
        )
        script = f"""#!/usr/bin/env bash
SCRIPT_NAME="{script_name}"
TOPOLOGY="$LN/topologies/{topology_filename}"
DATA_DIR="$LN/simulations/$SCRIPT_NAME"
OUTPUT_FILE="$LN/simulations/$SCRIPT_NAME.out"
SIMULATION={simulation_num}
COMMANDS_FILE=$LN/generated_commands_$SIMULATION
cd $LN/py
python3 -m commands_generator.commands_generator \\
    --topology "$TOPOLOGY" \\
    --establish-channels \\
    --make-payments {num_payments} 11000000 \\
    --steal-attack \\
    --dump-data "$DATA_DIR.tmp" \\
    --block-time 240 \\
    --bitcoin-blockmaxweight {blockmaxweight} \\
    --simulation-number $SIMULATION \\
    --outfile $COMMANDS_FILE

rm -rf /tmp/lightning-simulations/$SIMULATION
rm -rf "$DATA_DIR"
bash $COMMANDS_FILE 2>&1 | tee "$OUTPUT_FILE.tmp"
mv "$OUTPUT_FILE.tmp" "$OUTPUT_FILE"
mv "$DATA_DIR.tmp" "$DATA_DIR"
"""
        with open(script_path, mode="w") as f:
            f.write(script)
