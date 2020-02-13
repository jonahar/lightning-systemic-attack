#!/usr/bin/env python3

import os

ln = os.path.expandvars("$LN")
simulations_dir = os.path.join(ln, "simulations")

# set these to customize the simulation
topology = os.path.join(ln, "topologies/topology-1-5-1.json")
num_victims = 5
payments_per_victim = 400
channel_balance = 0.1
blockmaxweight_values = [100000]
num_blocks = 200
block_time = 150

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
num_payments = int(num_payments * 1.2)

for blockmaxweight in blockmaxweight_values:
    script_name = f"steal-attack-{num_victims}-victims-blockmaxweight={blockmaxweight}"
    datadir = os.path.join(simulations_dir, f"{script_name}")
    script_file = os.path.join(simulations_dir, f"{script_name}.sh")
    output_file = os.path.join(simulations_dir, f"{script_name}.out")
    
    with open(script_file, mode="w") as f:
        simulation_script = f"""#!/usr/bin/env bash
        cd $LN/py
        python3 -m commands_generator.commands_generator \\
            --topology "{topology}" \\
            --establish-channels \\
            --make-payments 1 3 {num_payments} {amount_msat} \\
            --steal-attack 1 3 {num_blocks} \\
            --dump-data "{datadir}" \\
            --block-time {block_time} \\
            --bitcoin-blockmaxweight {blockmaxweight} \\
            --outfile $LN/generated_commands
        
        cd $LN
        source sh/cli-functions
        clean-env
        
        bash generated_commands 2>&1 | tee {output_file}
        kill-daemons # kill all daemons before we terminate
        exit 0
        """
        
        f.write(simulation_script)
