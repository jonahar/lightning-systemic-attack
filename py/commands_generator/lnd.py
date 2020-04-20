from typing import TextIO

from commands_generator.lightning import LightningCommandsGenerator
from datatypes import NodeIndex, msat_to_sat
from paths import (
    LND_BINARY,
    LND_CLI_BINARY,
    LND_CONF_PATH,
)


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
        lnd_cmd = (
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
            f"  --debuglevel=debug"
            f"  {alias_flag}"
            # redirecting stdout+stderr and run in the background, because stupid lnd
            # doesn't have daemon option
            f"  >{self.lightning_dir}/lnd.log 2>&1 &"
        )
        
        # below are some really nasty hacks. sorry about that (blame LND)
        
        # the `create` and `unlock` commands of lncli don't accept arguments - they must
        # run interactively. They also fail to read input directly from file, as they
        # expect a terminal input (they fail with 'inappropriate ioctl for device').
        # That's why we are using `script`
        
        # we need to create and unlock the wallet and to check whether the node is ready to accept requests.
        # there is no simple command to check whether it is created/unlocked.
        # empirically, if we don't wait enough time between starting lnd/create/unlock commands,
        # the communication with lnd is down, and nothing else works besides killing lnd and start
        # it again. that's why we are trying all commands until the node is ready, with incremented
        # time interval to wait between commands
        
        self._write_line(f"""
        wait_interval=2 # how long we wait between commands
        lncli_timeout=5 # how long we let lncli run
        while true; do
            {lnd_cmd}
            lnd_pid=$!
            sleep $wait_interval
            timeout -s SIGKILL ${{lncli_timeout}}s script -a /dev/null -q -c "{self.__lncli_cmd_prefix()} create"  <<< "00000000\n00000000\nn\n\n" >/dev/null
            sleep $wait_interval
            timeout -s SIGKILL ${{lncli_timeout}}s  script -a /dev/null -q -c "{self.__lncli_cmd_prefix()} unlock" <<< "00000000\n" >/dev/null
            sleep $wait_interval
            if [[ $({self.__lncli_cmd_prefix()} getinfo 2>/dev/null | jq -r ".alias") == {self.alias} ]]; then
                break
            fi
            kill -s SIGKILL $lnd_pid
            sleep $wait_interval
            # wait a bit longer next time, in case that wasn't enough
            wait_interval=$((wait_interval+2))
            lncli_timeout=$((lncli_timeout+2))
        done
        """)
    
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
        initial_balance_sat: int,
    ) -> None:
        peer.set_id(bash_var=f"ID_{peer.idx}")
        self.__write_lncli_command(
            f"connect ${{ID_{peer.idx}}}@localhost:{peer_listen_port}"
        )
        self.__write_lncli_command(
            f"openchannel --node_key=${{ID_{peer.idx}}} --local_amt={initial_balance_sat}"
        )
    
    def wait_to_route(
        self,
        receiver: LightningCommandsGenerator,
        amount_msat: int,
    ) -> None:
        amount_sat = msat_to_sat(msat=amount_msat)
        receiver_id_bash_var = f"ID_{receiver.idx}"
        receiver.set_id(receiver_id_bash_var)
        self._write_line(f"""
    while [[ $({self.__lncli_cmd_prefix()} queryroutes --dest ${{{receiver_id_bash_var}}} --amt {amount_sat} 2>/dev/null | jq -r ".routes") == "" ]]; do
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
        amount_sat = msat_to_sat(msat=amount_msat)
        self._write_line(
            f"""{payment_req_bash_var}=$({self.__lncli_cmd_prefix()} addinvoice --amt {amount_sat} | jq -r ".payment_request")"""
        )
    
    def make_payments(
        self,
        receiver: LightningCommandsGenerator,
        num_payments: int,
        amount_msat: int,
    ) -> None:
        self._write_line(f"for i in $(seq 1 {num_payments}); do")
        receiver.create_invoice(payment_req_bash_var="PAYMENT_REQ", amount_msat=amount_msat)
        # we use timeout since sendpayment returns only when the payment succeeds/fails.
        # this may stuck us if we are sending to an evil node
        # the () is to dismiss background process info like "[3] 17480", "[3]+  Done"
        self._write_line(
            f"(timeout 2 {self.__lncli_cmd_prefix()} sendpayment --pay_req=$PAYMENT_REQ -f >/dev/null &)"
        )
        self._write_line("done")
    
    def print_node_htlcs(self) -> None:
        raise NotImplementedError()
    
    def close_all_channels(self) -> None:
        raise NotImplementedError()
    
    def dump_balance(self, filepath: str) -> None:
        self._write_line(f"""printf "node {self.idx} balance: " >> {filepath}""")
        self._write_line(
            f"""{self.__lncli_cmd_prefix()} walletbalance | jq -r ".total_balance" >> {filepath}"""
        )
    
    def reveal_preimages(self, peer: "LightningCommandsGenerator" = None) -> None:
        raise TypeError(f"Unsupported operation for {type(self).__name__}")
    
    def sweep_funds(self) -> None:
        addr_var = f"ADDR_{self.idx}"
        self.set_address(bash_var=addr_var)
        self.__write_lncli_command(
            f"sendcoins --addr ${{{addr_var}}} --sweepall"
        )
    
    def dump_channels_info(self, filepath: str) -> None:
        self._write_line(
            f"{self.__lncli_cmd_prefix()} listpeers >> {filepath}"
        )
        self._write_line(
            f"{self.__lncli_cmd_prefix()} listchannels >> {filepath}"
        )
    
    def wait_for_known_channels(self, num_channels: int) -> None:
        raise NotImplementedError()
