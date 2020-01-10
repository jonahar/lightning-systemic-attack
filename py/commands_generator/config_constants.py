import os

LAB = os.path.expandvars("$LAB")
LN = os.path.expandvars("$LN")

LIGHTNING_DIR_BASE = os.path.join(LN, "lightning-dirs")
BITCOIN_DIR_BASE = os.path.join(LN, "bitcoin-dirs")

CLIGHTNING_CONF_PATH = os.path.join(LN, "conf/clightning.conf")
LND_CONF_PATH = os.path.join(LN, "conf/lnd.conf")
BITCOIN_CONF_PATH = os.path.join(LN, "conf/bitcoin.conf")

CLIGHTNING_BINARY = os.path.join(LAB, "lightning/lightningd/lightningd")
CLIGHTNING_BINARY_EVIL = os.path.join(LAB, "lightning-evil/lightningd/lightningd")
LND_BINARY = os.path.join(LAB, "lnd/lnd")

LIGHTNING_LISTEN_PORT_BASE = 12000
LIGHTNING_RPC_PORT_BASE = 10000
LIGHTNING_REST_PORT_BASE = 11000
BITCOIN_LISTEN_PORT_BASE = 8300
BITCOIN_RPC_PORT_BASE = 18000
ZMQPUBRAWBLOCK_PORT_BASE = 28000
ZMQPUBRAWTX_PORT_BASE = 30000

INITIAL_CHANNEL_BALANCE_SAT = 10000000  # 0.1 BTC

BITCOIN_MINER_IDX = 0
