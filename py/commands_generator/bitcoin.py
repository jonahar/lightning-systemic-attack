from abc import ABC, abstractmethod
from typing import TextIO

from datatypes import BTC, NodeIndex


class BitcoinCommandsGenerator(ABC):
    
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
        generate code to start this bitcoin node
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """
        generate code to stop this bitcoin node
        """
        pass
    
    @abstractmethod
    def wait_until_synced(self, height: int) -> None:
        """
        generate code that waits until this node's blockchain have reached the given height
        """
        pass
    
    @abstractmethod
    def wait_until_ready(self) -> None:
        """
        generate code that waits until this node is ready to accept requests/commands
        """
        pass
    
    @abstractmethod
    def add_peer(self, host: str, port: int) -> None:
        """
        generate code to add a peer that listens on host:port
        """
        pass
    
    @abstractmethod
    def mine(self, num_blocks) -> None:
        """generate code that mines num_blocks blocks by this node"""
        pass
    
    @abstractmethod
    def fund(self, amount: BTC, addr_bash_var: str) -> None:
        """
        generate code to send 'amount' btc to the address that is set in the bash
        variable 'addr_bash_var'
        """
        pass
    
    @abstractmethod
    def wait_for_txs_in_mempool(self, num_txs: int) -> None:
        """
        generate code that waits until the mempool contains at least 'num_txs' transactions
        """
        pass
    
    @abstractmethod
    def advance_blockchain(self, num_blocks: int, block_time_sec: int):
        """
        generate code to advance the blockchain by 'num_blocks' blocks.
        blocks are mined at a rate corresponding to block_time_sec until the
        blockchain reaches height CURRENT_HEIGHT+num_blocks.
        Note, this may be different than mining 'num_blocks' blocks, in case
        someone else is also mining
        """
        pass
    
    @abstractmethod
    def dump_blockchain(self, dir_path: str) -> None:
        """
        generate code that dumps all blockchain info to files inside 'dir_path'.
        That includes jsons of every block and every transaction in the blockchain
        """
        pass

    @abstractmethod
    def set_node_balance(self, bash_var: str) -> None:
        """
        set the given bash var with the balance of this node in satoshis
        """
        pass

    @abstractmethod
    def sweep_funds(self) -> None:
        """
        sweep all funds of this bitcoin node, back to itself.
        """
        pass

    def fill_blockchain(self, num_blocks) -> None:
        """
        generate code that fills the mempool and mine 'num_blocks' full blocks.
        This is an optional method and is not required to be implemented by sub-classes
        """
        raise NotImplementedError("method fill_blockchain not implemented")
