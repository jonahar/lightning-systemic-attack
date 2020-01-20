import json
import os
import subprocess
from functools import lru_cache
from typing import List, Optional

from datatypes import Address, BTC, Block, FEERATE, TX, TXID, btc_to_sat

ln = os.path.expandvars("$LN")
BITCOIN_CLI_WITH_CONF = (
    "/usr/bin/bitcoin-cli "
    " -datadir=/cs/labs/avivz/projects/bitcoin"
    " -conf=/cs/labs/avivz/projects/bitcoin/bitcoin.conf"
)


def decode_stdout(result: subprocess.CompletedProcess) -> str:
    out = result.stdout.decode("utf-8")
    # remove newline at the end if exist
    if out[-1] == '\n':
        out = out[:-1]
    return out


def run_cli_command(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        BITCOIN_CLI_WITH_CONF.split() + args,
        stdout=subprocess.PIPE,
    )


def __gen_bitcoin_address() -> Address:
    # generate a bitcoin address to which bitcoins will be mined
    result = run_cli_command(["getnewaddress"])
    assert result.returncode == 0
    return decode_stdout(result)


MAIN_ADDRESS = None


def mine(num_blocks: int) -> None:
    global MAIN_ADDRESS
    if MAIN_ADDRESS is None:
        MAIN_ADDRESS = __gen_bitcoin_address()
    result = run_cli_command(["generatetoaddress", str(num_blocks), MAIN_ADDRESS])
    if result.returncode != 0:
        print(decode_stdout(result))


def fund_addresses(addresses: List[Address]) -> Optional[str]:
    sendmany_arg = json.dumps({addr: 1 for addr in addresses})
    result = run_cli_command(["sendmany", "", sendmany_arg])
    out = decode_stdout(result)
    if result.returncode != 0:
        print(out)
        return None
    mine(1)
    initial_balance_txid = out
    return initial_balance_txid


def get_block_by_hash(block_hash: str) -> Block:
    result = run_cli_command(["getblock", block_hash])
    return json.loads(decode_stdout(result))


def get_block_by_height(height: int) -> Block:
    result = run_cli_command(["getblockhash", str(height)])
    block_hash = decode_stdout(result)
    return get_block_by_hash(block_hash)


def num_tx_in_block(block: Block) -> int:
    return len(block['tx'])


def blockchain_height() -> int:
    result = run_cli_command(["-getinfo"])
    return json.loads(decode_stdout(result))["blocks"]


def get_mempool_txids() -> List[TXID]:
    result = run_cli_command(["getrawmempool"])
    return json.loads(decode_stdout(result))


# ----- Transactions -----

@lru_cache(maxsize=8192)
def get_transaction(txid: TXID) -> TX:
    result = run_cli_command(["getrawtransaction", txid, "1"])
    return json.loads(decode_stdout(result))


def get_tx_height(txid: TXID) -> int:
    """
    return the block height to which this tx entered
    -1 if the transaction has no height (not yet mined)
    """
    transaction = get_transaction(txid)
    block_hash = transaction["blockhash"]
    block = get_block_by_hash(block_hash)
    return block["height"] if "height" in block else -1


def get_tx_incoming_value(txid: TXID) -> BTC:
    tx = get_transaction(txid)
    return sum(
        get_transaction(src_entry["txid"])["vout"][src_entry["vout"]]["value"]
        for src_entry in tx["vin"] if "coinbase" not in src_entry
    )


def get_tx_outgoing_value(txid: TXID) -> BTC:
    tx = get_transaction(txid)
    return sum(entry["value"] for entry in tx["vout"])


def get_tx_fee(txid: TXID) -> BTC:
    return get_tx_incoming_value(txid) - get_tx_outgoing_value(txid)


def get_tx_feerate(txid: TXID) -> FEERATE:
    tx_size = get_transaction(txid)["size"]
    fee_sat = btc_to_sat(get_tx_fee(txid))
    return fee_sat / tx_size
