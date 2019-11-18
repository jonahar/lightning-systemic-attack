import json
import subprocess
from typing import List


def decode_stdout(result: subprocess.CompletedProcess):
    out = result.stdout.decode("utf-8")
    # remove newline at the end if exist
    if out[-1] == '\n':
        out = out[:-1]
    return out


def get_transaction(txid: str):
    result = subprocess.run(
        ["bitcoin-cli", "getrawtransaction", txid],
        stdout=subprocess.PIPE,
    )
    raw_transaction = decode_stdout(result)
    result = subprocess.run(
        ["bitcoin-cli", "decoderawtransaction", raw_transaction],
        stdout=subprocess.PIPE,
    )
    decode_stdout(result)


def gen_bitcoin_address():
    # get a general bitcoin address to which bitcoins will be mined
    result = subprocess.run(["bitcoin-cli", "getnewaddress"], stdout=subprocess.PIPE)
    assert result.returncode == 0
    return decode_stdout(result)


MAIN_ADDRESS = gen_bitcoin_address()


def mine(num_blocks: int):
    result = subprocess.run(
        ["bitcoin-cli", "generatetoaddress", str(num_blocks), MAIN_ADDRESS],
        stdout=subprocess.PIPE,
    )
    if result.returncode != 0:
        print(decode_stdout(result))


def fund_addresses(addresses: List[str]):
    sendmany_arg = json.dumps({addr: 1 for addr in addresses})
    result = subprocess.run(
        ["bitcoin-cli", "sendmany", "", sendmany_arg],
        stdout=subprocess.PIPE,
    )
    out = decode_stdout(result)
    if result.returncode != 0:
        print(out)
        return None
    mine(1)
    initial_balance_txid = out
    return initial_balance_txid
