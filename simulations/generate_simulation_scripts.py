topology = "/home/jona/lab/ln/topologies/topology-1-10-1.json"
num_victims = 10
num_payments = num_victims * 500
amount_msat = int((0.1 / 500) * (10 ** 8) * (10 ** 3))
num_blocks = 60
block_time = 180
blockmaxweight_values = [100000, 250000, 500000, 750000, 1000000]

for blockmaxweight in blockmaxweight_values:
    script_name = "steal-attack-{num_victims}victims-blockmaxweight={bitcoin_blockmaxweight}"
    datadir = f"/home/jona/lab/ln/simulations/data-{script_name}"
    script_file = f"/home/jona/lab/ln/simulations/{script_name}.sh"
    
    with open(script_file, mode="w") as f:
        simulation_script = f"""#!/usr/bin/env bash
        cd $LN
        source sh/cli-functions
        clean-env
        python3 py/lightning_commands_generator.py \\
            --topology "{topology}" \\
            --establish-channels \\
            --make-payments 1 3 {num_payments} {amount_msat} \\
            --steal-attack 1 3 {num_blocks} \\
            --dump-data "{datadir}" \\
            --block-time {block_time} \\
            --bitcoin-blockmaxweight {blockmaxweight} \\
            --outfile generated_commands
        
        bash generated_commands
        """
        
        f.write(simulation_script)
