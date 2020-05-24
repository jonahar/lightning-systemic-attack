import json

import os

DIR = "."

attempted_connections = 0
successful_connections = 0
for file in os.listdir(DIR):
    if file.endswith("connect.json"):
        attempted_connections += 1
        with open(file) as f:
            if "id" in json.load(f):
                successful_connections += 1

successful_handshakes = 0
for file in os.listdir(DIR):
    if file.endswith("fundchannel-start.json"):
        with open(file) as f:
            try:
                res = json.load(f)
                if "funding_address" in res:
                    successful_handshakes += 1
            except json.decoder.JSONDecodeError:
                # invalid json file means the fundchannel request was timed out
                pass

print(f"attempted_connections={attempted_connections}")
print(f"successful_connections={successful_connections}")
print(f"successful_handshakes={successful_handshakes}")
