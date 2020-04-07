from typing import TextIO

from commands_generator.lightning import LightningCommandsGenerator
from datatypes import NodeIndex
from paths import (
    CLIGHTNING_CONF_PATH, LIGHTNINGD_BINARY, LIGHTNINGD_BINARY_EVIL, LIGHTNING_CLI_BINARY,
)

CLOSE_CHANNEL_TIMEOUT_SEC = 60


class ClightningCommandsGenerator(LightningCommandsGenerator):
    
    def __init__(
        self,
        idx: NodeIndex,
        file: TextIO,
        datadir: str,
        listen_port: int,
        bitcoin_rpc_port: int,
        alias: str = None,
        evil: bool = False,
        silent: bool = False,
    ) -> None:
        super().__init__(index=idx, file=file)
        self.datadir = datadir
        self.alias = alias
        self.evil = evil
        self.silent = silent
        self.listen_port = listen_port
        self.bitcoin_rpc_port = bitcoin_rpc_port
    
    def start(self) -> None:
        self._write_line(f"mkdir -p {self.datadir}")
        
        binary = LIGHTNINGD_BINARY_EVIL if self.evil or self.silent else LIGHTNINGD_BINARY
        
        alias_flag = f"--alias={self.alias}" if self.alias else ""
        evil_flag = "--evil" if self.evil else ""
        silent_flag = "--silent" if self.silent else ""
        log_level_flag = f"--log-level=DEBUG"
        
        self._write_line(
            f"{binary} "
            f"  --conf={CLIGHTNING_CONF_PATH}"
            f"  --lightning-dir={self.datadir}"
            f"  --addr=localhost:{self.listen_port}"
            f"  --log-file=log"  # relative to lightning-dir
            f"  {alias_flag}"
            f"  {evil_flag}"
            f"  {silent_flag}"
            f"  {log_level_flag}"
            f"  --bitcoin-rpcconnect=localhost"
            f"  --bitcoin-rpcport={self.bitcoin_rpc_port}"
            f"  --daemon"
        )
    
    def __lightning_cli_command_prefix(self) -> str:
        return (
            f"""{LIGHTNING_CLI_BINARY} --conf="{CLIGHTNING_CONF_PATH}" --lightning-dir="{self.datadir}" """
        )
    
    def stop(self) -> None:
        self._write_line(f"{self.__lightning_cli_command_prefix()} stop")
    
    def set_address(self, bash_var: str) -> None:
        self._write_line(f"{bash_var}=$({self.__lightning_cli_command_prefix()} newaddr | jq -r '.address')")
    
    def set_id(self, bash_var: str) -> None:
        self._write_line(f"{bash_var}=$({self.__lightning_cli_command_prefix()} getinfo | jq -r '.id')")
    
    def wait_for_funds(self) -> None:
        self._write_line(f"""
    while [[ $({self.__lightning_cli_command_prefix()} listfunds | jq -r ".outputs") == "[]" ]]; do
        sleep 1
    done
    """)
    
    def establish_channel(
        self,
        peer: LightningCommandsGenerator,
        peer_listen_port: int,
        initial_balance_sat: int,
    ) -> None:
        bash_var = f"ID_{peer.idx}"
        peer.set_id(bash_var=bash_var)
        self._write_line(f"{self.__lightning_cli_command_prefix()} connect ${bash_var} localhost:{peer_listen_port}")
        self._write_line(
            f"{self.__lightning_cli_command_prefix()} fundchannel ${bash_var} {initial_balance_sat}")
    
    def __set_riskfactor(self) -> None:
        self._write_line("RISKFACTOR=1")
    
    def wait_to_route(self, receiver: LightningCommandsGenerator, amount_msat: int) -> None:
        self.__set_riskfactor()
        receiver.set_id(bash_var="RECEIVER_ID")
        self._write_line(f"""
    while [[ "$({self.__lightning_cli_command_prefix()} getroute $RECEIVER_ID {amount_msat} $RISKFACTOR | jq -r ".route")" == "null" ]]; do
        sleep 1;
    done
        """)
    
    def wait_to_route_via(
        self,
        src: LightningCommandsGenerator,
        dest: LightningCommandsGenerator,
        amount_msat: int,
    ) -> None:
        self.__set_riskfactor()
        src.set_id("SRC")
        dest.set_id("DEST")
        self._write_line(f"""
        while [[ "$({self.__lightning_cli_command_prefix()} getroute $DEST {amount_msat} $RISKFACTOR null $SRC | jq -r ".route")" == "null" ]]; do
            sleep 1;
        done
        """)
    
    def create_invoice(self, payment_req_bash_var, amount_msat: int) -> None:
        self._write_line(f"""LABEL="invoice-label-$(date +%s.%N)" """)
        self._write_line(
            f"""{payment_req_bash_var}=$({self.__lightning_cli_command_prefix()} invoice {amount_msat} $LABEL "" | jq -r ".bolt11")"""
        )
    
    def make_payments(
        self,
        receiver: LightningCommandsGenerator,
        num_payments: int,
        amount_msat: int,
    ) -> None:
        self._write_line("""
        show-progress-bar(){
            PERCENT=$1
            TERMINAL_WIDTH=$(tput cols)
            TOTAL_SLOTS=$((TERMINAL_WIDTH - 10))
            NUM_FULL_SLOTS=$(((TOTAL_SLOTS * PERCENT) / 100))
            NUM_EMPTY_SLOTS=$((TOTAL_SLOTS - NUM_FULL_SLOTS))
            printf "\\r["
            printf "%0.s=" $(seq 1 $NUM_FULL_SLOTS)
            printf "%0.s " $(seq 1 $NUM_EMPTY_SLOTS)
            printf "] ${PERCENT}%% "
        }
        """)
        
        self._write_line(f"NUM_PAYMENTS={num_payments}")
        self.__set_riskfactor()
        receiver.set_id(bash_var="RECEIVER_ID")
        self._write_line(f"for i in $(seq 1 $NUM_PAYMENTS); do")
        receiver.create_invoice(payment_req_bash_var="PAYMENT_REQ", amount_msat=amount_msat)
        self._write_line(
            f"""PAYMENT_HASH=$({self.__lightning_cli_command_prefix()} decodepay $PAYMENT_REQ | jq -r ".payment_hash")"""
        )
        self._write_line(
            f"""ROUTE=$({self.__lightning_cli_command_prefix()} getroute $RECEIVER_ID {amount_msat} $RISKFACTOR | jq -r ".route")"""
        )
        self._write_line(
            f"""{self.__lightning_cli_command_prefix()} sendpay "$ROUTE" "$PAYMENT_HASH" > /dev/null"""
        )
        self._write_line(f"show-progress-bar $(((i*100)/NUM_PAYMENTS))")
        self._write_line(f"done")
        self._write_line(f"echo")  # to start a new line after the progress bar
    
    def print_node_htlcs(self) -> None:
        self._write_line(
            f"""{self.__lightning_cli_command_prefix()} listpeers| jq ".peers[] | .channels[0].htlcs" | jq length"""
        )
    
    def close_all_channels(self) -> None:
        self._write_line(
            f"""PEER_IDS=$({self.__lightning_cli_command_prefix()} listpeers | jq -r ".peers[] | .id")"""
        )
        self._write_line(f"""
    for id in $PEER_IDS; do
        {self.__lightning_cli_command_prefix()} close $id {CLOSE_CHANNEL_TIMEOUT_SEC}
    done
        """)
    
    def dump_balance(self, filepath: str) -> None:
        self._write_line(f"""printf "node {self.idx} balance: " >> {filepath}""")
        self._write_line(
            f"{self.__lightning_cli_command_prefix()} listfunds | jq '.outputs[] | .value' | jq -s add >> {filepath}")
    
    def reveal_preimages(self, peer: "LightningCommandsGenerator" = None) -> None:
        if peer:
            peer.set_id(bash_var="PEER_ID")
        else:
            self._write_line("PEER_ID=")  # make this variable empty
        self._write_line(f"""
    while [[ $({self.__lightning_cli_command_prefix()} revealpreimages $PEER_ID | jq -r ".htlcs_processed") != 0 ]]; do
        sleep 1
    done
    """)
    
    def sweep_funds(self) -> None:
        addr_var = f"ADDR_{self.idx}"
        self.set_address(bash_var=addr_var)
        self._write_line(f"{self.__lightning_cli_command_prefix()} withdraw ${{{addr_var}}} all")
    
    def dump_channels_info(self, filepath: str) -> None:
        self._write_line(
            f"{self.__lightning_cli_command_prefix()} listchannels >> {filepath}"
        )
        self._write_line(
            f"{self.__lightning_cli_command_prefix()} listpeers >> {filepath}"
        )
