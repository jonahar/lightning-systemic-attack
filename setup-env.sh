#!/usr/bin/env bash

export LNPATH="/cs/usr/jonahar/ln"


lncli-alice(){
    builtin cd $LNPATH/dev/alice;
    lncli --rpcserver=localhost:10001 --macaroonpath=data/chain/bitcoin/simnet/admin.macaroon $*
    builtin cd - # return to previous directory
}

lncli-bob(){
    builtin cd $LNPATH/dev/bob;
    lncli --rpcserver=localhost:10002 --macaroonpath=data/chain/bitcoin/simnet/admin.macaroon $*
    builtin cd -
}

lncli-charlie(){
    builtin cd $LNPATH/dev/charlie;
    lncli --rpcserver=localhost:10003 --macaroonpath=data/chain/bitcoin/simnet/admin.macaroon $*
    builtin cd -
}


# export the custom lnclis to subshells
export -f lncli-alice
export -f lncli-bob
export -f lncli-charlie


# commands to run in the different tmux windows
BTCD_COMMAND="cd ${LNPATH}; run-btcd.sh"
ALICE_COMMAND="cd ${LNPATH}/dev/alice; bash --init-file ${LNPATH}/dev-bashrc.sh"
BOB_COMMAND="cd ${LNPATH}/dev/bob; bash --init-file ${LNPATH}/dev-bashrc.sh"
CHARLIE_COMMAND="cd ${LNPATH}/dev/charlie; bash --init-file ${LNPATH}/dev-bashrc.sh"
LNCLI_COMMAND="bash --init-file ${LNPATH}/dev-bashrc.sh"


# kill any existing tmux sessions
tmux kill-server; sleep 1;

tmux new-session -d -n btcd "$BTCD_COMMAND"
tmux new-window -n a-lnd "$ALICE_COMMAND"
tmux new-window -n b-lnd "$BOB_COMMAND"
tmux new-window -n b-lnd "$CHARLIE_COMMAND"

tmux new-window -n lncli "$LNCLI_COMMAND"

tmux attach-session
