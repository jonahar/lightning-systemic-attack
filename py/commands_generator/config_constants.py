import os

LN = os.path.expandvars("$LN")
BIN = os.path.join(LN, "bin")

CLIGHTNING_CONF_PATH = os.path.join(LN, "conf/clightning.conf")
LND_CONF_PATH = os.path.join(LN, "conf/lnd.conf")
BITCOIN_CONF_PATH = os.path.join(LN, "conf/bitcoin.conf")

BITCOIND_BINARY = os.path.join(BIN, "bitcoind")
BITCOIN_CLI_BINARY = os.path.join(BIN, "bitcoin-cli")
CLIGHTNING_BINARY = os.path.join(BIN, "lightningd")
CLIGHTNING_BINARY_EVIL = os.path.join(BIN, "lightningd-evil")
CLIGHTNING_CLI_BINARY = os.path.join(BIN, "lightning-cli")
LND_BINARY = os.path.join(BIN, "lnd")
LND_CLI_BINARY = os.path.join(BIN, "lncli")
ECLAIR_NODE_JAR = os.path.join(BIN, "eclair.jar")
ECLAIR_CLI = os.path.join(BIN, "eclair-cli")
