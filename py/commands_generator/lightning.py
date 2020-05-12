from abc import ABC, abstractmethod
from typing import TextIO

from datatypes import NodeIndex


class LightningCommandsGenerator(ABC):
    
    def __init__(self, index: NodeIndex, file: TextIO) -> None:
        self.index = index
        self.file = file
    
    def _write_line(self, line: str) -> None:
        """
        write the given string as a new line to the destination TextIO
        sub-classes should use this method to write the generated code
        """
        self.file.write(line)
        self.file.write("\n")
    
    @property
    def idx(self) -> NodeIndex:
        return self.index
    
    @abstractmethod
    def start(self) -> None:
        """
        generate code to start this lightning node
        """
        pass
    
    def start_silent(self) -> None:
        """
        generate code to start this lightning node in silent mode.
        optional method
        """
        raise TypeError("method start_silent() not supported by this client")
    
    @abstractmethod
    def stop(self) -> None:
        """
        generate code to stop this lightning node
        """
        pass
    
    @abstractmethod
    def set_address(self, bash_var: str) -> None:
        """
        generate code that sets a bash variable named `bash_var` with
        an address of that node
        """
        pass
    
    @abstractmethod
    def set_id(self, bash_var: str) -> None:
        """
        generate code that sets a bash variable named `bash_var` with
        the id of that node
        """
        pass
    
    @abstractmethod
    def wait_for_funds(self) -> None:
        """
        generate code that waits until this node detects received funds
        """
        pass
    
    @abstractmethod
    def connect(self, peer: "LightningCommandsGenerator", peer_listen_port: int):
        """
        generate code to connect this node to "peer". no channel is established
        """
        pass
    
    @abstractmethod
    def establish_channel(
        self,
        peer: "LightningCommandsGenerator",
        peer_listen_port: int,
        initial_balance_sat: int,
    ) -> None:
        """
        generate code to open a channel with another node. Channel is funded
        by this node
        
        Args:
            peer: a LightningCommandsGenerator of the peer we want to connect to.
                  may be useful to generate peer identifying information (id, etc.)
            peer_listen_port: the port on which the peer is listening
            initial_balance_sat: the channel balance in satoshis
        """
        pass
    
    @abstractmethod
    def wait_to_route(
        self,
        receiver: "LightningCommandsGenerator",
        amount_msat: int,
    ) -> None:
        """
        generate code that waits until there is a known route from this node to
        another node
        
        Args:
            receiver: a LightningCommandsGenerator of the node we are looking a route to
            amount_msat: the amount we expect the route to have (lightning find routes
                         for specific amounts)
        """
        pass
    
    @abstractmethod
    def wait_to_route_via(
        self,
        src: "LightningCommandsGenerator",
        dest: "LightningCommandsGenerator",
        amount_msat: int,
    ) -> None:
        """
        generate code that waits until this node recognizes a path from src to dest.
        
        Args:
            src: a LightningCommandsGenerator of the source node
            dest: a LightningCommandsGenerator of the destination node
            amount_msat: the amount we expect the route to have (lightning find routes
                         for specific amounts)
        """
        pass
    
    @abstractmethod
    def create_invoice(self, payment_req_bash_var, amount_msat: int) -> None:
        """
        generate code that creates a new invoice by this node with the given amount.
        the payment request encoding (bolt-11) is inserted to the given bash variable
        """
        pass
    
    @abstractmethod
    def make_payments(
        self,
        receiver: "LightningCommandsGenerator",
        num_payments: int,
        amount_msat: int,
    ) -> None:
        """
        generate code that makes payments from this node to another
        
        Args:
            receiver: a LightningCommandsGenerator of the node receiving the payments
            num_payments: number of payments to make
            amount_msat: the amount in millisatoshi for each of the payments
        """
        pass
    
    @abstractmethod
    def print_node_htlcs(self) -> None:
        """
        generate code that prints the amount of htlcs this node has on its channels
        """
        pass
    
    @abstractmethod
    def close_all_channels(self) -> None:
        """
        generate code to close all channels of this node
        """
        pass
    
    @abstractmethod
    def dump_balance(self, filepath: str) -> None:
        """
        generate code to dump this node's balance to the given file.
        data MUST be appended to the file as a single line in the following format:
        'node <NODE_IDX> balance: <BALANCE IN SAT>'
        """
        pass
    
    def reveal_preimages(self, peer: "LightningCommandsGenerator" = None) -> None:
        """
        generate code that reveals preimages that are being held by this node.
        if 'peer' is given, reveal only preimages in channels with that peer.
        
        optional method
        """
        raise TypeError("method reveal_preimages() not supported by this client")
    
    @abstractmethod
    def sweep_funds(self) -> None:
        """
        generate code that sweeps the entire available balance of that node.
        The coins are sent to a new address of that node.
        """
        pass
    
    @abstractmethod
    def dump_channels_info(self, filepath: str) -> None:
        """
        dump all channels information this node has into a file with the given name.
        It is up to the specific LightningCommandsGenerator implementation to decide
        what information exactly is written
        """
        pass
    
    @abstractmethod
    def wait_for_known_channels(self, num_channels: int) -> None:
        """
        wait until this node knows at least num_channels channels in the network,
        whether this node is a side in the channel or not.
        this includes directed channels (so one channel may be counted twice)
        """
        pass
