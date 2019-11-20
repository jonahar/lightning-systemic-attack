import json
import subprocess
from typing import List, Optional

from datatypes import Address, Block, Json, TXID


def decode_stdout(result: subprocess.CompletedProcess) -> str:
    out = result.stdout.decode("utf-8")
    # remove newline at the end if exist
    if out[-1] == '\n':
        out = out[:-1]
    return out


def get_transaction(txid: TXID) -> Json:
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


def __gen_bitcoin_address() -> Address:
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


def fund_addresses(addresses: List[Address]) -> Optional[str]:
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


def get_block_by_hash(block_hash: str) -> Block:
    result = subprocess.run(
        ["bitcoin-cli", "getblock", block_hash],
        stdout=subprocess.PIPE,
    )
    return json.loads(decode_stdout(result))


def get_block_by_height(height: int) -> Block:
    result = subprocess.run(
        ["bitcoin-cli", "getblockhash", str(height)],
        stdout=subprocess.PIPE,
    )
    block_hash = decode_stdout(result)
    return get_block_by_hash(block_hash)


def num_tx_in_block(block: Block) -> int:
    return len(block['tx'])


def get_tx_height(txid: TXID) -> int:
    """return the block height to which this tx entered"""
    result = subprocess.run(
        ["bitcoin-cli", "getrawtransaction", txid, "1"],
        stdout=subprocess.PIPE,
    )
    block_hash = json.loads(decode_stdout(result))["blockhash"]
    block = get_block_by_hash(block_hash)
    return block["height"]
