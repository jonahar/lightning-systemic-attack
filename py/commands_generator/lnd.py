from typing import TextIO

from commands_generator.config_constants import LND_BINARY, LND_CONF_PATH
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
        self.bitcoin_rpc_port = bitcoin_rpc_port
        self.zmqpubrawblock_port = zmqpubrawblock_port
        self.zmqpubrawtx_port = zmqpubrawtx_port
        self.alias = alias
    
    def __get_lncli_command_prefix(self) -> str:
        """
        return a prefix on an lncli command. that includes the lncli executable
        """
        return (
            f"$LAB/lnd/lncli"
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
            self.__get_lncli_command_prefix() + " " + command
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
            f"script -q -c \"{self.__get_lncli_command_prefix()} create\" "
            f" <<< \"\"\"00000000\n00000000\nn\n\n\"\"\" | tail -n1"
        )
    
    def stop(self) -> None:
        raise NotImplemented
    
    def set_address(self, bash_var: str) -> None:
        raise NotImplemented
    
    def set_id(self, bash_var: str) -> None:
        raise NotImplemented
    
    def wait_for_funds(self) -> None:
        raise NotImplemented
    
    def establish_channel(
        self,
        peer: LightningCommandsGenerator,
        peer_listen_port: int,
    ) -> None:
        raise NotImplemented
    
    def wait_to_route(
        self,
        receiver: LightningCommandsGenerator,
        amount_msat: int,
    ) -> None:
        raise NotImplemented
    
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
        raise NotImplemented
