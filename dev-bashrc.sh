#!/usr/bin/env bash

source $HOME/.bashrc
PATH=$PATH:$LNPATH:$LNPATH/btcd:$LNPATH/lnd

alias lncli-alice="cd $LNPATH/dev/alice; lncli --rpcserver=localhost:10001 --macaroonpath=data/chain/bitcoin/simnet/admin.macaroon"
alias lncli-bob="cd $LNPATH/dev/bob; lncli --rpcserver=localhost:10002 --macaroonpath=data/chain/bitcoin/simnet/admin.macaroon"
alias lncli-charlie="cd $LNPATH/dev/charlie; lncli --rpcserver=localhost:10003 --macaroonpath=data/chain/bitcoin/simnet/admin.macaroon"
