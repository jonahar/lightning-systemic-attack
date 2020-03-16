from typing import TextIO

from commands_generator.bitcoin import BitcoinCommandsGenerator
from datatypes import BTC, NodeIndex
from paths import (
    BITCOIN_CLI_BINARY, BITCOIN_CONF_PATH
)


class BitcoinCoreCommandsGenerator(BitcoinCommandsGenerator):
    
    def __init__(
        self,
        idx: NodeIndex,
        file: TextIO,
        datadir: str,
        listen_port: int,
        rpc_port: int,
        blockmaxweight: int,
        zmqpubrawblock_port: int,
        zmqpubrawtx_port: int,
    ) -> None:
        super().__init__(index=idx, file=file)
        self.datadir = datadir
        self.listen_port = listen_port
        self.rpc_port = rpc_port
        self.blockmaxweight = blockmaxweight
        self.zmqpubrawblock_port = zmqpubrawblock_port
        self.zmqpubrawtx_port = zmqpubrawtx_port
    
    def __bitcoin_cli_cmd_prefix(self) -> str:
        return (
            f"{BITCOIN_CLI_BINARY} "
            f" -conf={BITCOIN_CONF_PATH} "
            f" -rpcport={self.rpc_port} "
        )
    
    def start(self) -> None:
        self._write_line(f"mkdir -p {self.datadir}")
        self._write_line(
            f"bitcoind"
            f"  -conf={BITCOIN_CONF_PATH}"
            f"  -port={self.listen_port}"
            f"  -rpcport={self.rpc_port}"
            f"  -datadir={self.datadir}"
            f"  -daemon"
            f"  -blockmaxweight={self.blockmaxweight}"
            f"  -zmqpubrawblock=tcp://127.0.0.1:{self.zmqpubrawblock_port}"
            f"  -zmqpubrawtx=tcp://127.0.0.1:{self.zmqpubrawtx_port}"
        )
    
    def stop(self) -> None:
        self._write_line(f"{self.__bitcoin_cli_cmd_prefix()} stop")
    
    def wait_until_synced(self, height: int) -> None:
        self._write_line(f"""
        while [[ $({self.__bitcoin_cli_cmd_prefix()} -getinfo | jq ".blocks") -lt "{height}" ]]; do
            sleep 1
        done
        """)
    
    def wait_until_ready(self) -> None:
        self._write_line(f"""
        while [[ $({self.__bitcoin_cli_cmd_prefix()} echo "sanity" 2>/dev/null | jq -r ".[0]") != "sanity" ]]; do
            sleep 1;
        done
        """)
    
    def add_peer(self, host: str, port: int) -> None:
        self._write_line(f"{self.__bitcoin_cli_cmd_prefix()} addnode {host}:{port} add")
    
    def __get_mine_command(self, num_blocks) -> str:
        """
        an helper method for mine(). this could be used by other methods if they want
        to inject a mine command in a more complex bash code (e.g. mine inside a bash for-loop)
        """
        return (
            f"{self.__bitcoin_cli_cmd_prefix()} generatetoaddress "
            f" {num_blocks} $({self.__bitcoin_cli_cmd_prefix()} getnewaddress) >/dev/null"
        )
    
    def mine(self, num_blocks):
        self._write_line(self.__get_mine_command(num_blocks))
    
    def fund(self, amount: BTC, addr_bash_var: str) -> None:
        self._write_line(f"{self.__bitcoin_cli_cmd_prefix()} sendtoaddress ${addr_bash_var} {amount}")
    
    def wait_for_txs_in_mempool(self, num_txs: int) -> None:
        """
        generate code that waits until the mempool contains at least 'num_txs' transactions
        """
        self._write_line(f"""
        while [[ $({self.__bitcoin_cli_cmd_prefix()} getmempoolinfo | jq -r ".size") != "{num_txs}" ]]; do
            sleep 1;
        done
        """)
    
    def __set_blockchain_height(self):
        """
        set the current blockchain height in a variable named BLOCKCHAIN_HEIGHT
        """
        self._write_line(
            f"""BLOCKCHAIN_HEIGHT=$({self.__bitcoin_cli_cmd_prefix()} -getinfo | jq ".blocks")"""
        )

    def __dump_mempool(self, mempool_dump_dir: str) -> None:
        self.__set_blockchain_height()
        self._write_line(f"""txids=$({self.__bitcoin_cli_cmd_prefix()} getrawmempool | jq -r ".[]") """)
        self._write_line(f"""
        for txid in $txids; do
            {self.__bitcoin_cli_cmd_prefix()} getrawtransaction $txid true \\
                    > {mempool_dump_dir}/height_${{BLOCKCHAIN_HEIGHT}}_${{txid}}.json
        done
        """)

    def advance_blockchain(self, num_blocks: int, block_time_sec: int, mempool_dump_dir: str = None) -> None:
        self.__set_blockchain_height()
        self._write_line(f"DEST_HEIGHT=$((BLOCKCHAIN_HEIGHT + {num_blocks}))")
    
        self._write_line(
            f"""while [[ $({self.__bitcoin_cli_cmd_prefix()} -getinfo | jq ".blocks") -lt $DEST_HEIGHT ]]; do""")
        self._write_line(f"sleep {block_time_sec}")
        if mempool_dump_dir:
            self.__dump_mempool(mempool_dump_dir)
        self.mine(1)
        self._write_line("done")

    def dump_blockchain(self, dir_path: str) -> None:
        self.__set_blockchain_height()
        # dump blocks + transactions
        self._write_line(f"""
        for i in $(seq 1 $BLOCKCHAIN_HEIGHT); do
            BLOCK_HASH=$({self.__bitcoin_cli_cmd_prefix()} getblockhash $i)
            {self.__bitcoin_cli_cmd_prefix()} getblock $BLOCK_HASH > {dir_path}/block_$i.json
            TXS_IN_BLOCK=$(jq -r ".tx[]" < {dir_path}/block_$i.json)
            for TX in $TXS_IN_BLOCK; do
                {self.__bitcoin_cli_cmd_prefix()} getrawtransaction $TX true > {dir_path}/tx_$TX.json
            done
        done
        """)

    def set_node_balance(self, bash_var: str) -> None:
        self._write_line(
            f"""AMOUNT_SAT_FLOAT=$(bc <<< "$({self.__bitcoin_cli_cmd_prefix()} getbalance) * 100000000")"""
        )
        self._write_line(
            f"""printf -v {bash_var} %.0f "$AMOUNT_SAT_FLOAT" """
        )

    def sweep_funds(self) -> None:
        self._write_line(f"BALANCE=$({self.__bitcoin_cli_cmd_prefix()} getbalance)")
        self._write_line(
            f'{self.__bitcoin_cli_cmd_prefix()} sendtoaddress '
            f'  $({self.__bitcoin_cli_cmd_prefix()} getnewaddress) '
            f'  $BALANCE '
            f'  "" '
            f'  "" '
            f'  true '
        )

    def fill_blockchain(self, num_blocks) -> None:
        self.mine(num_blocks=100 + num_blocks)  # at least 100 to unlock coinbase txs

        # we try to keep the mempool at the size of 2 full blocks.
        # full blocks are measured in weight units (blockmaxweight), but bitcoind
        # reports mempool size in bytes, so we need to estimate the size of a full block

        num_outputs = 10
        # usually for the kind of transaction we are building, this is the ratio between
        # the block's weight and size
        block_weight_size_ratio = 2.7
        full_block_expected_size = self.blockmaxweight / block_weight_size_ratio
        
        for i in range(num_outputs):
            self._write_line(f"""ADDR_{self.idx}_{i}=$({self.__bitcoin_cli_cmd_prefix()} getnewaddress)""")
        
        sendmany_arg = "{" + ",".join(f"""\\"$ADDR_{self.idx}_{i}\\":0.1""" for i in range(num_outputs)) + "}"
        
        # we want to launch multiple sendmany requests at the same time, but we can't
        # do too many either (bitcoind will fail). we use 10 at a time and wait
        # until all of them are finished. we run them in a sub-shell so they don't
        # put too much junk in our console
        
        self._write_line(f"""
        for _ in $(seq 1 {num_blocks}); do
            while [[ $({self.__bitcoin_cli_cmd_prefix()} getmempoolinfo | jq -r ".bytes") -lt {int(2 * full_block_expected_size)} ]]; do
                (
                    for _ in $(seq 1 10); do
                        {self.__bitcoin_cli_cmd_prefix()} sendmany "" "{sendmany_arg}" >/dev/null &
                    done
                    wait
                )
            done
            {self.__get_mine_command(1)}
        done
        """)
