import os
import tempfile
from enum import Enum

from datatypes import NodeIndex


class ServiceType(Enum):
    LIGHTNING_LISTEN = "0"
    LIGHTNING_RPC = "1"
    LIGHTNING_REST = "2"
    BITCOIN_LISTEN = "3"
    BITCOIN_RPC = "4"
    BITCOIN_ZMQPUBRAWBLOCK = "5"
    BITCOIN_ZMQPUBRAWTX = "6"


class ResourcesAllocator:
    """
    A ResourcesAllocator is responsible for allocating resources such as ports/directories to
    different nodes, in different simulations, for different purposes.
    
    It takes care of allocating unique resources so processes will not have
    intra-simulation or inter-simulation collisions.
    
    Ports allocation:
        Each port is 5 digits: XYZZZ
        X: simulation number. 1-6
        Y: service type (see ServiceType). 0-9
        ZZZ: an id of some node in simulation X. 0-999 (zero padded if needed)
    
    Data-dirs allocation:
        a root dir for the entire simulation is allocated in the system temp dir, and
        inside it all datadirs for specific bitcoin/lightning nodes
    
    """
    
    def __init__(self, simulation: int) -> None:
        if not 1 <= simulation <= 6:
            raise ValueError(f"simulation number must be between 1 and 6")
        self.simulation: str = str(simulation)
    
    # Ports
    
    def __get_port(self, service: ServiceType, node_idx: NodeIndex) -> int:
        if not 0 <= node_idx <= 999:
            raise ValueError(f"node_idx must be between 0 and 999")
        
        return int(self.simulation + service.value + str(node_idx).zfill(3))
    
    def get_lightning_node_rpc_port(self, node_idx: NodeIndex) -> int:
        return self.__get_port(service=ServiceType.LIGHTNING_RPC, node_idx=node_idx)
    
    def get_lightning_node_rest_port(self, node_idx: NodeIndex) -> int:
        return self.__get_port(service=ServiceType.LIGHTNING_REST, node_idx=node_idx)
    
    def get_lightning_node_listen_port(self, node_idx: NodeIndex) -> int:
        return self.__get_port(service=ServiceType.LIGHTNING_LISTEN, node_idx=node_idx)
    
    def get_bitcoin_node_rpc_port(self, node_idx: NodeIndex) -> int:
        return self.__get_port(service=ServiceType.BITCOIN_RPC, node_idx=node_idx)
    
    def get_bitcoin_node_listen_port(self, node_idx: NodeIndex) -> int:
        return self.__get_port(service=ServiceType.BITCOIN_LISTEN, node_idx=node_idx)
    
    def get_bitcoin_node_zmqpubrawblock_port(self, node_idx: NodeIndex) -> int:
        return self.__get_port(service=ServiceType.BITCOIN_ZMQPUBRAWBLOCK, node_idx=node_idx)
    
    def get_bitcoin_node_zmqpubrawtx_port(self, node_idx: NodeIndex) -> int:
        return self.__get_port(service=ServiceType.BITCOIN_ZMQPUBRAWTX, node_idx=node_idx)
    
    # Datadirs
    
    def __get_simulation_dir(self) -> str:
        return os.path.join(tempfile.gettempdir(), "lightning-simulations", self.simulation)
    
    def get_lightning_node_datadir(self, node_idx: NodeIndex) -> str:
        return os.path.join(self.__get_simulation_dir(), "lightning-datadirs", str(node_idx))
    
    def get_bitcoin_node_datadir(self, node_idx: NodeIndex) -> str:
        return os.path.join(self.__get_simulation_dir(), "bitcoin-datadirs", str(node_idx))
