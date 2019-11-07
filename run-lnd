#!/usr/bin/env bash

I=$1

if [[ -z $I ]]; then
    echo "please specify lnd index"
    exit 1
fi

echo "running lnd number $I"

$LNPATH/lnd/lnd \
    --rpclisten=localhost:1000${I} \
    --listen=localhost:1001${I} \
    --restlisten=localhost:800${I} \
    --datadir=data \
    --logdir=log \
    --debuglevel=info \
    --bitcoin.simnet \
    --bitcoin.active \
    --bitcoin.node=btcd \
    --btcd.rpcuser=kek \
    --btcd.rpcpass=kek
