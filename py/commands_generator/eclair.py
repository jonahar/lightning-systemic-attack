from typing import TextIO

from commands_generator.config_constants import ECLAIR_CLI, ECLAIR_NODE_JAR, INITIAL_CHANNEL_BALANCE_SAT
from commands_generator.lightning import LightningCommandsGenerator
from datatypes import NodeIndex


class EclairCommandsGenerator(LightningCommandsGenerator):
    
    def __init__(
        self,
        index: NodeIndex,
        file: TextIO,
        lightning_dir: str,
        listen_port: int,
        rpc_port: int,
        bitcoin_rpc_port: int,
        zmqpubrawblock_port: int,
        zmqpubrawtx_port: int,
        alias: str = None,
    ) -> None:
        super().__init__(index, file)
        self.lightning_dir = lightning_dir
        self.listen_port = listen_port
        self.rpc_port = rpc_port
        self.bitcoin_rpc_port = bitcoin_rpc_port
        self.zmqpubrawblock_port = zmqpubrawblock_port
        self.zmqpubrawtx_port = zmqpubrawtx_port
        self.alias = alias
    
    def __get_node_pid_file(self) -> str:
        """return the filepath in which the process id of this node is/should be stored"""
        # TODO this method is not a single source of truth. the kill-daemons script
        #  also has this filename hardcoded. think how to avoid it
        return f"{self.lightning_dir}/node_pid"
    
    def start(self) -> None:
        self._write_line(f"mkdir -p {self.lightning_dir}")
        # we provide all arguments to eclair via the conf file.
        # create conf file inside datadir:
        self._write_line(f"""echo '''
        eclair.api.binding-ip=127.0.0.1
        eclair.api.enabled=true
        eclair.api.password=kek
        eclair.api.port={self.rpc_port}
        eclair.bitcoind.host=localhost
        eclair.bitcoind.rpcpassword=kek
        eclair.bitcoind.rpcport={self.bitcoin_rpc_port}
        eclair.bitcoind.rpcuser=kek
        eclair.bitcoind.zmqblock="tcp://127.0.0.1:{self.zmqpubrawblock_port}"
        eclair.bitcoind.zmqtx="tcp://127.0.0.1:{self.zmqpubrawtx_port}"
        eclair.chain=regtest
        eclair.node-alias="{self.alias}"
        eclair.server.port={self.listen_port}
        ''' > {self.lightning_dir}/eclair.conf
        """)
        
        self._write_line(
            f"""java -Declair.datadir="{self.lightning_dir}" -jar {ECLAIR_NODE_JAR} >/dev/null 2>&1 & """
        )
        self._write_line(f"echo $! >{self.__get_node_pid_file()} # $! the PID of the eclair node")
        
        # wait until node is ready
        self._write_line(f"""
        while [[ $({self.__eclair_cli_command_prefix()} getinfo 2>/dev/null | jq -r ".alias") != "{self.alias}" ]]; do
            sleep 1;
        done
        """)
    
    def __eclair_cli_command_prefix(self) -> str:
        return f"{ECLAIR_CLI} -p kek -a localhost:{self.rpc_port} "
    
    def __write_eclair_cli_command(self, args: str) -> None:
        self._write_line(
            self.__eclair_cli_command_prefix() + args
        )
    
    def stop(self) -> None:
        raise NotImplementedError()
    
    def set_address(self, bash_var: str) -> None:
        self._write_line(
            f"{bash_var}=$({self.__eclair_cli_command_prefix()} getnewaddress)"
        )
    
    def set_id(self, bash_var: str) -> None:
        self._write_line(f"""{bash_var}=$({self.__eclair_cli_command_prefix()} getinfo | jq -r ".nodeId")""")
    
    def wait_for_funds(self) -> None:
        # eclair doesn't provide such method. we have to talk to its bitcoind
        # bitcoind shows balance as float, so we use bc to compare it to 0
        self._write_line(f"""
        # bc outputs 1 if the equality holds
        while [[ $(echo "$(bcli {self.idx} -getinfo | jq -r '.balance') == 0" |bc -l) == 1 ]]; do
            sleep 1
        done
        """)
    
    def establish_channel(
        self,
        peer: LightningCommandsGenerator,
        peer_listen_port: int,
    ) -> None:
        peer_id_bash_var = f"ID_{peer.idx}"
        peer.set_id(bash_var=peer_id_bash_var)
        self.__write_eclair_cli_command(
            args=f"connect --uri=${{{peer_id_bash_var}}}@localhost:{peer_listen_port}"
        )
        self.__write_eclair_cli_command(
            args=f"open --nodeId=${peer_id_bash_var} --fundingSatoshis={INITIAL_CHANNEL_BALANCE_SAT}"
        )
    
    def wait_to_route(
        self,
        receiver: LightningCommandsGenerator,
        amount_msat: int,
    ) -> None:
        raise NotImplementedError()
    
    def create_invoice(self, payment_req_bash_var, amount_msat: int) -> None:
        raise NotImplementedError()
    
    def make_payments(
        self,
        receiver: LightningCommandsGenerator,
        num_payments: int,
        amount_msat: int,
    ) -> None:
        raise NotImplementedError()
    
    def print_node_htlcs(self) -> None:
        raise NotImplementedError()
    
    def close_all_channels(self) -> None:
        raise NotImplementedError()
    
    def dump_balance(self, filepath: str) -> None:
        raise NotImplementedError()
    
    def reveal_preimages(self, peer: LightningCommandsGenerator = None) -> None:
        raise TypeError(f"Unsupported operation for {type(self).__name__}")
    
    def sweep_funds(self) -> None:
        raise NotImplementedError()
