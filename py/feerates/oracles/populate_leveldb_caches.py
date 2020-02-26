import argparse
import time

from bitcoin_cli import blockchain_height, get_tx_feerate, get_tx_weight, get_txs_in_block, set_bitcoin_cli
from datatypes import BlockHeight
from feerates import logger


def populate_block(h: BlockHeight) -> None:
    # all we need to do to populate the db with tx weights in the given block is to
    # query get_tx_weight for these weights
    
    logger.info(f"Dumping tx weights+feerates for block {h}")
    txids = get_txs_in_block(height=h)
    for txid in txids:
        get_tx_feerate(txid)
        get_tx_weight(txid)


def populate_blocks(first_block: BlockHeight, last_block: BlockHeight) -> None:
    for h in range(first_block, last_block + 1):
        try:
            populate_block(h)
        except Exception as e:
            logger.error(f"Exception occurred when trying to populate with txs in block {h}: {type(e)}:{str(e)}")


def parse_args():
    """
    parse and return the program arguments
    """
    parser = argparse.ArgumentParser(description='populate the leveldb caches of tx weights and feerates')
    parser.add_argument(
        "first_block", type=int, action="store",
        help="the first block to populate txs of",
    )
    parser.add_argument(
        "last_block", type=int, action="store",
        help=(
            "the last block to populate txs of. if 0 is given, populate all "
            "blocks from first_block to the current blockchain height, indefinitely"
        ),
    )
    parser.add_argument(
        "bitcoin_cli", choices=["master", "user"], metavar="bitcoin_cli",
        help="the bitcoin-cli to use. must be one of `master` or `user`",
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    set_bitcoin_cli(args.bitcoin_cli)
    
    if args.last_block != 0:
        populate_blocks(first_block=args.first_block, last_block=args.last_block)
    else:
        # we populate all blocks from first_block to the current height, indefinitely
        first_block = args.first_block
        while True:
            curr_height = blockchain_height()
            logger.info(
                f"Populating txs of all blocks from height {args.first_block} to current blockchain height ({curr_height})"
            )
            populate_blocks(first_block=first_block, last_block=curr_height)
            logger.info("sleeping for 5 minutes")
            time.sleep(60 * 5)
            first_block = curr_height + 1
