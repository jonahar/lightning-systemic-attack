import os
import re

import matplotlib.pyplot as plt

ln = os.path.expandvars("$LN")
samples_dir = os.path.join(ln, "estimatesmartfee-samples")

samples_file_regex = re.compile("estimates-blocks=(\\d+),mode=(\\w+)")

for entry in os.listdir(samples_dir):
    match = samples_file_regex.match(entry)
    if not match:
        print(f"Ignoring file in unrecognized format: {entry}")
        continue
    blocks: str = match.group(1)
    mode: str = match.group(2)
    with open(os.path.join(samples_dir, entry)) as f:
        lines = f.read().splitlines()
    timestamps = list(map(lambda line: line.split(":")[0], lines))
    feerates = list(map(lambda line: line.split(":")[1], lines))
    plt.plot(
        timestamps, feerates,
        label=f"estimatesmartfee(block={blocks},mode={mode})",
    )

# graph config
plt.legend(loc='best')
plt.xlabel('timestamp')
plt.ylabel('feerate')
plt.title('estimated vs actual required feerate')
plt.show()
