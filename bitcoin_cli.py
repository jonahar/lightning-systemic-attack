import json
import subprocess
from typing import Any, Dict, List, Optional

JsonDict = Dict[str, Any]


def decode_stdout(result: subprocess.CompletedProcess) -> str:
    out = result.stdout.decode("utf-8")
    # remove newline at the end if exist
    if out[-1] == '\n':
        out = out[:-1]
    return out


def get_transaction(txid: str) -> JsonDict:
    result = subprocess.run(
        ["bitcoin-cli", "getrawtransaction", txid],
        stdout=subprocess.PIPE,
    )
    raw_transaction = decode_stdout(result)
    result = subprocess.run(
        ["bitcoin-cli", "decoderawtransaction", raw_transaction],
        stdout=subprocess.PIPE,
    )
    return json.loads(decode_stdout(result))


def __gen_bitcoin_address() -> str:
    # generate a bitcoin address to which bitcoins will be mined
    result = subprocess.run(["bitcoin-cli", "getnewaddress"], stdout=subprocess.PIPE)
    assert result.returncode == 0
    return decode_stdout(result)


MAIN_ADDRESS = __gen_bitcoin_address()


def mine(num_blocks: int) -> None:
    result = subprocess.run(
        ["bitcoin-cli", "generatetoaddress", str(num_blocks), MAIN_ADDRESS],
        stdout=subprocess.PIPE,
    )
    if result.returncode != 0:
        print(decode_stdout(result))


def fund_addresses(addresses: List[str]) -> Optional[str]:
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


def get_block_by_hash(block_hash: str) -> JsonDict:
    result = subprocess.run(
        ["bitcoin-cli", "getblock", block_hash],
        stdout=subprocess.PIPE,
    )
    return json.loads(decode_stdout(result))


def get_block_by_height(height: int) -> JsonDict:
    result = subprocess.run(
        ["bitcoin-cli", "getblockhash", str(height)],
        stdout=subprocess.PIPE,
    )
    block_hash = decode_stdout(result)
    return get_block_by_hash(block_hash)
