import os

LN = os.path.expandvars("$LN")
BIN = os.path.join(LN, "bin")
DATA = os.path.join(LN, "data")
FEE_ESTIMATIONS_DIR = os.path.join(LN, "data", "fee-estimations")
CACHES_DIR = os.path.join(DATA, "caches")
SIMULATIONS_DIR = os.path.join(LN, "simulations")

CLIGHTNING_CONF_PATH = os.path.join(LN, "conf/clightning.conf")
LND_CONF_PATH = os.path.join(LN, "conf/lnd.conf")
BITCOIN_CONF_PATH = os.path.join(LN, "conf/bitcoin.conf")

BITCOIND_BINARY = os.path.join(BIN, "bitcoind")
BITCOIN_CLI_BINARY = os.path.join(BIN, "bitcoin-cli")

LIGHTNINGD_BINARY = os.path.join(BIN, "lightningd")
LIGHTNINGD_BINARY_EVIL = os.path.join(BIN, "lightningd-evil")
LIGHTNING_CLI_BINARY = os.path.join(BIN, "lightning-cli")

LND_BINARY = os.path.join(BIN, "lnd")
LND_CLI_BINARY = os.path.join(BIN, "lncli")

ECLAIR_NODE = os.path.join(BIN, "eclair-node")
ECLAIR_CLI = os.path.join(BIN, "eclair-cli")
