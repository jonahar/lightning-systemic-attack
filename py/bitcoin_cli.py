import json
import os
import subprocess
from functools import lru_cache
from typing import List, Optional, Set

from datatypes import (
    Address, BTC, Block, BlockHeight, FEERATE, TIMESTAMP, TX, TXID, btc_to_sat,
)

ln = os.path.expandvars("$LN")

BITCOIN_CLI_MASTER = "/cs/usr/jonahar/bitcoin-datadir/bitcoin-cli-master "
BITCOIN_CLI_USER = "/cs/usr/jonahar/bitcoin-datadir/bitcoin-cli "

BITCOIN_CLI = BITCOIN_CLI_MASTER

TRANSACTIONS_CACHE_SIZE = 2 ** 13  # 8192. probably enough to hold transactions of an entire block


def set_bitcoin_cli(target: str) -> None:
    """
    set the bitcoin-cli to use for talking to bitcoind.
    target should be one of `master` or `user`
    """
    global BITCOIN_CLI
    if target == "master":
        BITCOIN_CLI = BITCOIN_CLI_MASTER
    elif target == "user":
        BITCOIN_CLI = BITCOIN_CLI_USER
    else:
        raise ValueError(f"unrecognized bitcoin-cli target: {target}")


def decode_stdout(result: subprocess.CompletedProcess) -> str:
    out = result.stdout.decode("utf-8")
    # remove newline at the end if exist
    if out[-1] == '\n':
        out = out[:-1]
    return out


def run_cli_command(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        BITCOIN_CLI.split() + args,
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


def get_block_by_height(height: BlockHeight) -> Block:
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


def show_num_tx_in_last_t_blocks(t: int):
    """
    print the number of transactions in each of the last t blocks.
    """
    block_height = blockchain_height()
    for i in range(block_height - t + 1, block_height + 1):
        num_tx_in_block_i = num_tx_in_block(block=get_block_by_height(i))
        print(f"number of tx in block {i}: {num_tx_in_block_i}")


def show_tx_in_block(block_height):
    block: Block = get_block_by_height(block_height)
    for txid in block['tx']:
        print(txid)


def find_interesting_txids_in_last_t_blocks(t: int) -> Set[TXID]:
    """
    return a set of TXIDs from the last t blocks that are not coinbase transactions
    """
    block_height = blockchain_height()
    return {
        txid
        for height in range(block_height - t + 1, block_height + 1)
        for txid in get_block_by_height(height)["tx"]
        if "coinbase" not in get_transaction(txid)["vin"][0]
    }


@lru_cache(maxsize=4096)
def get_block_time(h: BlockHeight) -> TIMESTAMP:
    return get_block_by_height(h)["time"]


# ----- Transactions -----

@lru_cache(maxsize=TRANSACTIONS_CACHE_SIZE)
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


@lru_cache(maxsize=TRANSACTIONS_CACHE_SIZE)
def get_tx_fee(txid: TXID) -> BTC:
    return get_tx_incoming_value(txid) - get_tx_outgoing_value(txid)


def get_tx_feerate(txid: TXID) -> FEERATE:
    tx_size = get_transaction(txid)["size"]
    fee_sat = btc_to_sat(get_tx_fee(txid))
    return fee_sat / tx_size
