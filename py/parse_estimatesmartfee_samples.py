import os
import re
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np

TIMESTAMPS = List[float]
FEERATES = List[float]
LABEL = str

ln = os.path.expandvars("$LN")
samples_dir = os.path.join(ln, "estimatesmartfee-samples")
estimations_files = os.listdir(samples_dir)

samples_file_regex = re.compile("fee-estimations_blocks=(\\d+)_mode=(\\w+)")

data: List[Tuple[TIMESTAMPS, FEERATES, LABEL]] = []
for entry in estimations_files:
    match = samples_file_regex.match(entry)
    if not match:
        print(f"Ignoring file in unrecognized format: {entry}")
        continue
    blocks: str = match.group(1)
    mode: str = match.group(2)
    with open(os.path.join(samples_dir, entry)) as f:
        lines = f.read().splitlines()
    timestamps = list(map(lambda line: int(line.split(":")[0]), lines))
    feerates = list(map(lambda line: float(line.split(":")[1]), lines))
    data.append(
        (timestamps, feerates, f"estimatesmartfee(block={blocks},mode={mode})")
    )

for timestamps, feerates, label in data:
    plt.plot(timestamps, feerates, label=label)

min_timestamp = min(min(t) for t, f, l in data)
max_timestamp = max(max(t) for t, f, l in data)
min_feerate = min(min(f) for t, f, l in data)
max_feerate = max(max(f) for t, f, l in data)

# graph config
plt.legend(loc='best')
plt.title('estimated feerate')

plt.xlabel('timestamp')
plt.xticks(np.linspace(start=min_timestamp, stop=max_timestamp, num=10))

plt.ylabel('feerate')
plt.yticks(np.linspace(start=min_feerate, stop=max_feerate, num=10))
plt.show()
