import os
import re

import matplotlib.pyplot as plt

ln = os.path.expandvars("$LN")
simulations = os.path.join(ln, "simulations")
os.chdir(simulations)

stolen_amounts = {}
for entry in os.listdir(simulations):
    datadir_full = os.path.join(simulations, entry)
    balance_file = os.path.join(datadir_full, "nodes_balance")
    if os.path.isdir(datadir_full) and os.path.isfile(balance_file):
        with open(balance_file) as f:
            line1 = f.readline()
            line2 = f.readline()
            if not line1.startswith("node 1 balance:") or not line2.startswith("node 3 balance:"):
                continue
            node_1_balance = int(line1.split()[-1])
            node_3_balance = int(line2.split()[-1])
            # print(f"node_1_balance={node_1_balance}")
            # print(f"node_3_balance={node_3_balance}")
            total_satoshi = node_1_balance + node_3_balance
            # print(f"total satoshi combined: {total_satoshi}")
            total_btc = total_satoshi * (10 ** -8)
            btc_stolen = round(total_btc - 10, 8)
            
            blockmaxweight = int(re.search("blockmaxweight=(\d+)", entry).group(1))
            stolen_amounts[blockmaxweight] = btc_stolen
            # print(f"total btc combined: {total_btc}")
            # print(f"amount stolen: {btc_stolen}")
            print(f"{blockmaxweight}: {btc_stolen}")
            print("====================================")

for blockmaxweight in sorted(stolen_amounts.keys()):
    print(f"{blockmaxweight}\t\t{stolen_amounts[blockmaxweight]}")

x = sorted(stolen_amounts.keys())
y = list(map(lambda blockmaxweight: stolen_amounts[blockmaxweight], x))
plt.plot(x, y)
plt.xlabel('blockmaxweight')
plt.ylabel('BTC stolen')
plt.title('10 victims attack')
plt.show()
