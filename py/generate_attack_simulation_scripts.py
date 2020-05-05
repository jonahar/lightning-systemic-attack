import json
import os

from paths import LN

min_num_victims = 1
max_num_victims = 10
num_payments_multiplier = 3
blockmaxweight_values = [100_000, 200_000, 300_000, 400_000]

num_victims_values = list(range(min_num_victims, max_num_victims + 1))
min_simulation_num = 1
max_simulation_num = 5

for num_victims in num_victims_values:
    # generate topology file
    topology = {
        1: {
            "client": "c-lightning",
            "evil": True,
            "peers": list(map(str, range(4, 4 + num_victims)))
        },
        3: {
            "client": "c-lightning",
            "evil": True,
            "peers": []
        },
    }
    
    for i in range(4, 4 + num_victims):
        topology[i] = {
            "client": "lnd",
            "peers": [
                "3"
            ]
        }
    topology_filename = f"topology-{num_victims}-lnd-victims.json"
    topology_fullpath = os.path.join(LN, "topologies", topology_filename)
    with open(topology_fullpath, mode="w") as f:
        json.dump(topology, f, sort_keys=True, indent=4)
    
    # generate simulation script
    num_payments = int(483 * num_victims * num_payments_multiplier)
    for blockmaxweight in blockmaxweight_values:
        script_name = f"steal-attack-{num_victims}-lnd-victims-blockmaxweight={blockmaxweight}"
        script_path = os.path.join(LN, "simulations", f"{script_name}.sh")
        simulation_num = (
            min_simulation_num + (num_victims % (max_simulation_num - min_simulation_num + 1))
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
    --make-payments 1 3 {num_payments} 11000000 \\
    --steal-attack 1 3 150 \\
    --dump-data "$DATA_DIR.tmp" \\
    --block-time 180 \\
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
