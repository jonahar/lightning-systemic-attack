#!/usr/bin/env bash

export LNPATH="/cs/usr/jonahar/ln"

# commands to run in the different tmux windows
BTCD_COMMAND="cd ${LNPATH}; run-btcd.sh"

ALICE_COMMAND="cd ${LNPATH}/dev/alice; bash --init-file ${LNPATH}/dev-bashrc.sh"
BOB_COMMAND="cd ${LNPATH}/dev/bob; bash --init-file ${LNPATH}/dev-bashrc.sh"
CHARLIE_COMMAND="cd ${LNPATH}/dev/charlie; bash --init-file ${LNPATH}/dev-bashrc.sh"

tmux new-session -d -n btcd "$BTCD_COMMAND"
tmux new-window -n a-lnd "$ALICE_COMMAND"
tmux new-window -n b-lnd "$BOB_COMMAND"
tmux new-window -n b-lnd "$CHARLIE_COMMAND"

tmux new-window -n a-cli "$ALICE_COMMAND"
tmux new-window -n b-cli "$BOB_COMMAND"
tmux new-window -n c-cli "$CHARLIE_COMMAND"

tmux attach-session
