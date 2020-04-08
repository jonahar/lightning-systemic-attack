from typing import TextIO

from commands_generator.bitcoin import BitcoinCommandsGenerator
from commands_generator.lightning import LightningCommandsGenerator
from datatypes import NodeIndex
from paths import ECLAIR_CLI, ECLAIR_NODE_JAR


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
        bitcoin_commands_generator: BitcoinCommandsGenerator,
        alias: str = None,
        max_accepted_htlcs: int = 483,
    ) -> None:
        super().__init__(index, file)
        self.lightning_dir = lightning_dir
        self.listen_port = listen_port
        self.rpc_port = rpc_port
        self.bitcoin_rpc_port = bitcoin_rpc_port
        self.zmqpubrawblock_port = zmqpubrawblock_port
        self.zmqpubrawtx_port = zmqpubrawtx_port
        self.bitcoin_commands_generator = bitcoin_commands_generator
        self.alias = alias
        self.max_accepted_htlcs = max_accepted_htlcs
    
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
        eclair.max-accepted-htlcs={self.max_accepted_htlcs}
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
        # we use the process id we stored when we started this node
        pid_filepath = self.__get_node_pid_file()
        self._write_line(
            f"pkill --pidfile {pid_filepath}"
        )
    
    def set_address(self, bash_var: str) -> None:
        self._write_line(
            f"{bash_var}=$({self.__eclair_cli_command_prefix()} getnewaddress)"
        )
    
    def set_id(self, bash_var: str) -> None:
        self._write_line(f"""{bash_var}=$({self.__eclair_cli_command_prefix()} getinfo | jq -r ".nodeId")""")
    
    def wait_for_funds(self) -> None:
        # eclair doesn't provide a method to get our balance. we have to use the
        # the bitcoin daemon
        balance_bash_var = f"NODE_{self.idx}_BALANCE"
        self.bitcoin_commands_generator.set_node_balance(bash_var=balance_bash_var)
        
        # bc outputs 1 if the equality holds
        # bitcoind shows balance as float, so we use bc to compare it to 0
        self._write_line(f"""while [[ $(echo "${balance_bash_var} == 0" |bc -l) == 1 ]]; do""")
        self._write_line("sleep 1")
        self.bitcoin_commands_generator.set_node_balance(bash_var=balance_bash_var)
        self._write_line("done")
    
    def establish_channel(
        self,
        peer: LightningCommandsGenerator,
        peer_listen_port: int,
        initial_balance_sat: int,
    ) -> None:
        peer_id_bash_var = f"ID_{peer.idx}"
        peer.set_id(bash_var=peer_id_bash_var)
        self.__write_eclair_cli_command(
            args=f"connect --uri=${{{peer_id_bash_var}}}@localhost:{peer_listen_port}"
        )
        self.__write_eclair_cli_command(
            args=f"open --nodeId=${peer_id_bash_var} --fundingSatoshis={initial_balance_sat}"
        )
    
    def wait_to_route(
        self,
        receiver: LightningCommandsGenerator,
        amount_msat: int,
    ) -> None:
        receiver_id_bash_var = f"ID_{receiver.idx}"
        receiver.set_id(bash_var=receiver_id_bash_var)
        find_route_command = (
            self.__eclair_cli_command_prefix() +
            f"findroutetonode --nodeId=${{{receiver_id_bash_var}}} --amountMsat={amount_msat}"
        )
        self._write_line(f"""
        while [[ $({find_route_command}) == "route not found" ]]; do
            sleep 1
        done
        """)
    
    def wait_to_route_via(
        self,
        src: LightningCommandsGenerator,
        dest: LightningCommandsGenerator,
        amount_msat: int,
    ) -> None:
        raise NotImplementedError()
    
    def create_invoice(self, payment_req_bash_var, amount_msat: int) -> None:
        self.__write_eclair_cli_command(
            f"""{payment_req_bash_var}=$(createinvoice --description="" --amountMsat={amount_msat} | jq -r ".serialized")"""
        )
    
    def make_payments(
        self,
        receiver: LightningCommandsGenerator,
        num_payments: int,
        amount_msat: int,
    ) -> None:
        self._write_line(f"for i in $(seq 1 {num_payments}); do")
        receiver.create_invoice(payment_req_bash_var="PAYMENT_REQ", amount_msat=amount_msat)
        self.__write_eclair_cli_command("payinvoice --invoice=${PAYMENT_REQ}")
        self._write_line("done")
    
    def print_node_htlcs(self) -> None:
        raise NotImplementedError()
    
    def close_all_channels(self) -> None:
        raise NotImplementedError()
    
    def dump_balance(self, filepath: str) -> None:
        balance_bash_var = f"NODE_{self.idx}_BALANCE"
        self.bitcoin_commands_generator.set_node_balance(bash_var=balance_bash_var)
        self._write_line(f"""echo "node {self.idx} balance: ${balance_bash_var}" >> {filepath}""")
    
    def reveal_preimages(self, peer: LightningCommandsGenerator = None) -> None:
        raise TypeError(f"Unsupported operation for {type(self).__name__}")
    
    def sweep_funds(self) -> None:
        self.bitcoin_commands_generator.sweep_funds()
    
    def dump_channels_info(self, filepath: str) -> None:
        self._write_line(
            f"{self.__eclair_cli_command_prefix()} channels >> {filepath}"
        )
        self._write_line(
            f"{self.__eclair_cli_command_prefix()} peers >> {filepath}"
        )
    
    def wait_for_known_channels(self, num_channels: int) -> None:
        raise NotImplementedError()
