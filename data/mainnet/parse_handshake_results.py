import json
import os
from collections import OrderedDict

import matplotlib.pyplot as plt

DIR = "handshake-responses"

attempted_connections = 0
successful_connections = 0
failed_connections_timeout = 0
failed_connections_socket_failed = 0
failed_connections_unknown = 0

for file in filter(lambda f: f.endswith("connect.json"), os.listdir(DIR)):
    attempted_connections += 1
    with open(os.path.join(DIR, file)) as f:
        res = json.load(f)
    
    if "id" in res:
        successful_connections += 1
    elif "timeout" in res or ("message" in res and "Connection timed out" in res["message"]):
        failed_connections_timeout += 1
    elif "message" in res and "Connection refused" in res["message"]:
        failed_connections_socket_failed += 1
    else:
        failed_connections_unknown += 1

print(f"attempted_connections={attempted_connections}")
print(f"successful_connections={successful_connections}")
print(f"failed_connections_timeout={failed_connections_timeout}")
print(f"failed_connections_socket_failed={failed_connections_socket_failed}")
print(f"failed_connections_unknown={failed_connections_unknown}")

attempted_handshakes = 0
successful_handshakes = 0
failed_handshakes_unacceptable_fee = 0
failed_handshakes_sync_blockchain = 0
failed_handshakes_timeout = 0
failed_handshakes_unacceptable_balance = 0
failed_handshakes_unknown = 0

for file in filter(lambda f: f.endswith("fundchannel-start.json"), os.listdir(DIR)):
    attempted_handshakes += 1
    with open(os.path.join(DIR, file)) as f:
        res = json.load(f)
    
    if "funding_address" in res:
        successful_handshakes += 1
    elif "timeout" in res:
        failed_handshakes_timeout += 1
    elif "message" in res and "Synchronizing blockchain" in res["message"]:
        failed_handshakes_sync_blockchain += 1
    elif "message" in res and "feerates are too different" in res["message"]:
        failed_handshakes_unacceptable_fee += 1
    elif "message" in res and "is below min chan size of" in res["message"]:
        failed_handshakes_unacceptable_balance += 1
    else:
        failed_handshakes_unknown += 1

assert successful_connections == attempted_handshakes
assert (
    successful_handshakes + failed_handshakes_unacceptable_fee
    + failed_handshakes_sync_blockchain + failed_handshakes_timeout
    + failed_handshakes_unacceptable_balance + failed_handshakes_unknown
    == attempted_handshakes
)

to_percent = lambda v: round(v * 100 / attempted_handshakes, 2)

value_to_label: dict = {
    successful_handshakes: f"Successful 'accept_channel' ({to_percent(successful_handshakes)}%)",
    failed_handshakes_unacceptable_fee: f"Unacceptable fee ({to_percent(failed_handshakes_unacceptable_fee)}%)",
    failed_handshakes_sync_blockchain: f"Not ready (blockchain sync) ({to_percent(failed_handshakes_sync_blockchain)}%)",
    failed_handshakes_timeout: f"Request timeout ({to_percent(failed_handshakes_timeout)}%)",
    failed_handshakes_unacceptable_balance: f"Unacceptable balance ({to_percent(failed_handshakes_unacceptable_balance)}%)",
    failed_handshakes_unknown: f"Unspecified reason ({to_percent(failed_handshakes_unknown)}%)",
}
value_to_label: OrderedDict = OrderedDict(sorted(value_to_label.items(), reverse=True))


def aggregate(d: OrderedDict) -> OrderedDict:
    d_aggregated = d.copy()
    # only keep 3 top reasons, labeling anything else as 'other'
    other_count = 0
    for k in list(d_aggregated.keys())[3:]:
        other_count += k
        d_aggregated.pop(k)
    d_aggregated[other_count] = f"Other ({to_percent(other_count)}%)"
    return d_aggregated


value_to_label_aggregated: OrderedDict = aggregate(value_to_label)

for k, v in value_to_label_aggregated.items():
    print(k, "\t", v)

plt.figure()
# plot one without labels so we can design it ourselves
plt.pie(x=value_to_label_aggregated.keys())
plt.savefig("handshake-results-pie.svg")

plt.figure()
plt.pie(x=value_to_label_aggregated.keys(), labels=value_to_label_aggregated.values())
plt.legend(loc="best")
plt.show()
