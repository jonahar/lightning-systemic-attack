import os
import re
from collections import defaultdict
from typing import Dict

import matplotlib.pyplot as plt

ln = os.path.expandvars("$LN")
simulations = os.path.join(ln, "simulations")
os.chdir(simulations)

initial_attackers_amount_btc = 5

HTLC_COUNT = int
NUM_VICTIMS = int
DELAY = int
BLOCK_MAX_WEIGHT = int
AMOUNT_STOLEN = float
GRAPH_DATA = Dict[NUM_VICTIMS, Dict[BLOCK_MAX_WEIGHT, Dict[HTLC_COUNT, Dict[DELAY, AMOUNT_STOLEN]]]]
# num_victims -> blockmaxweight -> htlc_count -> delay -> amount_stolen
# graph_data is dictionary of dictionaries of dictionaries
graph_data: GRAPH_DATA = defaultdict(
    lambda: defaultdict(
        lambda: defaultdict(dict)
    )
)

simulation_name_regex = re.compile(
    "steal-attack-(\d+)-victims-blockmaxweight=(\d+)-htlc=(\d+)-delay=(\d+)"
)

for entry in os.listdir(simulations):
    match = simulation_name_regex.fullmatch(entry)
    if not match:
        continue
    
    num_victims = int(match.group(1))
    blockmaxweight = int(match.group(2))
    htlc_count = int(match.group(3))
    delay = int(match.group(4))
    
    datadir_full = os.path.join(simulations, entry)
    balance_file = os.path.join(datadir_full, "nodes_balance")
    
    if not os.path.isfile(balance_file):
        print(f"Warning: balance file doesn't exist for {entry}")
        continue
    
    with open(balance_file) as f:
        line1 = f.readline()
        line2 = f.readline()
        assert line1.startswith("node 1 balance:") and line2.startswith("node 3 balance:")
        
        node_1_balance = int(line1.split()[-1])
        node_3_balance = int(line2.split()[-1])
        # print(f"node_1_balance={node_1_balance}")
        # print(f"node_3_balance={node_3_balance}")
        total_satoshi = node_1_balance + node_3_balance
        # print(f"total satoshi combined: {total_satoshi}")
        total_btc = total_satoshi * (10 ** -8)
        btc_stolen = round(total_btc - initial_attackers_amount_btc, 8)
        graph_data[num_victims][blockmaxweight][htlc_count][delay] = btc_stolen

for num_victims in graph_data:
    for blockmaxweight in graph_data[num_victims]:
        # simulations with the same num_victims and blockmaxweight goes no the same figure
        plt.figure()
        for htlc_count in graph_data[num_victims][blockmaxweight]:
            # simulation with different htlc_count will be different graphs on the same figure
            delay_to_amouont_dict = graph_data[num_victims][blockmaxweight][htlc_count]
            delays = sorted(delay_to_amouont_dict.keys())
            amounts_stolen = list(map(lambda delay: delay_to_amouont_dict[delay], delays))
            plt.plot(delays, amounts_stolen, label=f"max_htlc={htlc_count}")
            plt.legend(loc="best")
            plt.title(f"{num_victims} victims, blockmaxweight={blockmaxweight}")
            plt.xlabel('delay')
            plt.ylabel('BTC stolen')

plt.show()
