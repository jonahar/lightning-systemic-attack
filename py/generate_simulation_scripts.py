#!/usr/bin/env python3
import os
from itertools import product

ln = os.path.expandvars("$LN")
simulations_dir = os.path.join(ln, "simulations")

# set these to customize the simulation
topology = os.path.join(ln, "topologies/topology-1-5-1.json")
num_victims = 5
payments_per_victim_list = [483]
channel_balance = 0.1
num_blocks = 120
block_time = 120
blockmaxweight_values = [100_000, 200_000, 300_000, 400_000]

for blockmaxweight, payments_per_victim in product(blockmaxweight_values, payments_per_victim_list):
    # the following are derived from the previous variables. probably shouldn't be modified
    amount_msat = int(
        0.9  # leave 10% of the channel balance for fees
        * (channel_balance / payments_per_victim)  # divide channel balance equally between HTLCs
        * (10 ** 8)  # convert to satoshi
        * (10 ** 3)  # convert to millisatoshi
    )
    # this is the exact number of HTLCs we want
    num_payments = num_victims * payments_per_victim
    # some of the payments fail with no special reason. increase a bit the number of
    # payments we try. Anyway, each channel is limited by max_accepted_htlc
    num_payments = int(num_payments * 2)
    
    script_name = f"steal-attack-{num_victims}-victims-blockmaxweight={blockmaxweight}-htlc={payments_per_victim}"
    script_file = os.path.join(simulations_dir, f"{script_name}.sh")
    
    with open(script_file, mode="w") as f:
        simulation_script = f"""#!/usr/bin/env bash
        SCRIPT_NAME={script_name}
        DATA_DIR={simulations_dir}/$SCRIPT_NAME
        OUTPUT_FILE={simulations_dir}/$SCRIPT_NAME.out
        cd $LN/py
        SIMULATION=1
        COMMANDS_FILE=$LN/generated_commands_$SIMULATION
        python3 -m commands_generator.commands_generator \\
            --topology "{topology}" \\
            --establish-channels \\
            --make-payments 1 3 {num_payments} {amount_msat} \\
            --steal-attack 1 3 {num_blocks} \\
            --dump-data "$DATA_DIR" \\
            --block-time {block_time} \\
            --bitcoin-blockmaxweight {blockmaxweight} \\
            --simulation-number $SIMULATION \\
            --outfile $COMMANDS_FILE
        
        rm -rf /tmp/lightning-simulations/$SIMULATION
        bash $COMMANDS_FILE 2>&1 | tee "$OUTPUT_FILE"
        exit 0
        """
        
        f.write(simulation_script)
