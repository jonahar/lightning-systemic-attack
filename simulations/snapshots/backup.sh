IDX=$1
mv $IDX.tar $IDX.tar.old
tar -cvf $IDX.tar -C /tmp/lightning-simulations $IDX
