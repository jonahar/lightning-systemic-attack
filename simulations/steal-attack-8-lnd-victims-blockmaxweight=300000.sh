#!/usr/bin/env bash
SCRIPT_NAME="steal-attack-8-lnd-victims-blockmaxweight=300000"
TOPOLOGY="$LN/topologies/topology-8-lnd-victims.json"
DATA_DIR="$LN/simulations/$SCRIPT_NAME"
OUTPUT_FILE="$LN/simulations/$SCRIPT_NAME.out"
SIMULATION=4
COMMANDS_FILE=$LN/generated_commands_$SIMULATION
cd $LN/py
python3 -m commands_generator.commands_generator \
    --topology "$TOPOLOGY" \
    --establish-channels \
    --make-payments 1 3 11592 11000000 \
    --steal-attack 1 3 150 \
    --dump-data "$DATA_DIR" \
    --block-time 180 \
    --bitcoin-blockmaxweight 300000 \
    --simulation-number $SIMULATION \
    --outfile $COMMANDS_FILE

rm -rf /tmp/lightning-simulations/$SIMULATION
bash $COMMANDS_FILE 2>&1 | tee "$OUTPUT_FILE"

