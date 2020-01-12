from typing import TextIO

from commands_generator.config_constants import (
    INITIAL_CHANNEL_BALANCE_SAT,
    LND_BINARY,
    LND_CLI_BINARY,
    LND_CONF_PATH,
)
from commands_generator.lightning import LightningCommandsGenerator
from datatypes import NodeIndex


class LndCommandsGenerator(LightningCommandsGenerator):
    
    def __init__(
        self,
        index: NodeIndex,
        file: TextIO,
        lightning_dir: str,
        bitcoin_dir: str,
        listen_port: int,
        rpc_port: int,
        rest_port: int,
        bitcoin_rpc_port: int,
        zmqpubrawblock_port: int,
        zmqpubrawtx_port: int,
        alias: str = None,
    ) -> None:
        super().__init__(index, file)
        self.index = index
        self.file = file
        self.lightning_dir = lightning_dir
        self.bitcoin_dir = bitcoin_dir
        self.listen_port = listen_port
        self.rpc_port = rpc_port
        self.rest_port = rest_port
        self.bitcoin_rpc_port = bitcoin_rpc_port
        self.zmqpubrawblock_port = zmqpubrawblock_port
        self.zmqpubrawtx_port = zmqpubrawtx_port
        self.alias = alias
    
    def __lncli_cmd_prefix(self) -> str:
        """
        return a prefix on an lncli command. that includes the lncli executable
        """
        return (
            f"{LND_CLI_BINARY}"
            f"  --rpcserver localhost:{self.rpc_port}"
            f"  --lnddir {self.lightning_dir}"
            f"  --no-macaroons"
        )
    
    def __write_lncli_command(self, command: str) -> None:
        """
        generate lncli command.
        The given 'command' should include only the lncli command and its
        arguments, e.g. "closechannel <funding_txid>"
        the lncli executable and its flags should not be included and will be
        added by this method
        """
        self._write_line(
            self.__lncli_cmd_prefix() + " " + command
        )
    
    def start(self) -> None:
        self._write_line(f"mkdir -p {self.lightning_dir}")
        
        alias_flag = f"--alias={self.alias}" if self.alias else ""
        self._write_line(
            f"{LND_BINARY}"
            f"  --configfile={LND_CONF_PATH}"
            f"  --datadir={self.lightning_dir}"
            f"  --logdir={self.lightning_dir}"
            f"  --tlscertpath={self.lightning_dir}/tls.cert"
            f"  --tlskeypath={self.lightning_dir}/tls.key"
            f"  --no-macaroons"
            f"  --restlisten={self.rest_port}"
            f"  --rpclisten=localhost:{self.rpc_port}"
            f"  --listen=localhost:{self.listen_port}"
            f"  --bitcoind.rpchost=localhost:{self.bitcoin_rpc_port}"
            f"  --bitcoind.dir={self.bitcoin_dir}"
            f"  --bitcoind.zmqpubrawblock=localhost:{self.zmqpubrawblock_port}"
            f"  --bitcoind.zmqpubrawtx=localhost:{self.zmqpubrawtx_port}"
            f"  {alias_flag}"
            # redirecting stdout+stderr and run in the background, because stupid lnd
            # doesn't have daemon option
            f"  >{self.lightning_dir}/lnd.log 2>&1 &"
        )
        
        # give the node a moment to be ready to accept requests
        self._write_line("sleep 1")
        
        # the `create` command of lncli doesn't accept arguments - it must run interactively.
        # It also fails to read input directly from file, as it expects a terminal input.
        # That's why we are using `script`
        self._write_line(
            f"script -q -c \"{self.__lncli_cmd_prefix()} create\" "
            f" <<< \"\"\"00000000\n00000000\nn\n\n\"\"\" | tail -n1"
        )
        
        # give the node another moment to be ready to accept wallet requests
        self._write_line("sleep 1")
    
    def stop(self) -> None:
        self.__write_lncli_command("stop")
    
    def set_address(self, bash_var: str) -> None:
        self._write_line(
            f"{bash_var}=$({self.__lncli_cmd_prefix()} newaddress p2wkh | jq -r '.address')"
        )
    
    def set_id(self, bash_var: str) -> None:
        self._write_line(
            f"{bash_var}=$({self.__lncli_cmd_prefix()} getinfo | jq -r '.identity_pubkey')"
        )
    
    def wait_for_funds(self) -> None:
        self._write_line(f"""
    while [[ $({self.__lncli_cmd_prefix()} walletbalance | jq -r ".confirmed_balance") == 0 ]]; do
        sleep 1
    done
    """)
    
    def establish_channel(
        self,
        peer: LightningCommandsGenerator,
        peer_listen_port: int,
    ) -> None:
        peer.set_id(bash_var=f"ID_{peer.idx}")
        self.__write_lncli_command(
            f"connect ${{ID_{peer.idx}}}@localhost:{peer_listen_port}"
        )
        self.__write_lncli_command(
            f"openchannel --node_key=${{ID_{peer.idx}}} --local_amt={INITIAL_CHANNEL_BALANCE_SAT}"
        )
    
    def wait_to_route(
        self,
        receiver: LightningCommandsGenerator,
        amount_msat: int,
    ) -> None:
        amount_sat = int(amount_msat * (10 ** -3))
        receiver_id_bash_var = f"ID_{receiver.idx}"
        receiver.set_id(receiver_id_bash_var)
        self._write_line(f"""
    while [[ $({self.__lncli_cmd_prefix()} queryroutes --dest ${{{receiver_id_bash_var}}} --amt {amount_sat} 2>/dev/null | jq -r ".routes") == "" ]]; do
        sleep 1
    done
    """)
    
    def create_invoice(self, payment_hash_bash_var, amount_msat: int) -> None:
        raise NotImplemented
    
    def make_payments(
        self,
        receiver: LightningCommandsGenerator,
        num_payments: int,
        amount_msat: int,
    ) -> None:
        raise NotImplemented
    
    def print_node_htlcs(self) -> None:
        raise NotImplemented
    
    def close_all_channels(self) -> None:
        raise NotImplemented
    
    def dump_balance(self, filepath: str) -> None:
        self._write_line(f"""printf "node {self.idx} balance: " >> {filepath}""")
        self._write_line(
            f"""{self.__lncli_cmd_prefix()} walletbalance | jq -r ".total_balance" >> {filepath}"""
        )
