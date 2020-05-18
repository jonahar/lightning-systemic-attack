DIR=/tmp/lightning-simulations
#find $DIR -name log -exec du -sh "{}" ";"
find $DIR -name log -exec truncate -s 0 "{}" ";"

#find $DIR -name lnd.log -exec du -sh "{}" ";"
find $DIR -name lnd.log -exec truncate -s 0 "{}" ";"
