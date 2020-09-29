#!/bin/bash

# calculate embedding gain
# for the moment not considering reconstruction
# (assumes prior running of embedding_benchmark.sh)
BKGSIMTIME=$(awk '//{print $2}' ${PWD}/bkgsim.log_time)
SGNTIME=$(awk 'BEGIN{c=0} //{c+=$2} END {print c}' sgnsim*.log_time)
DIGITIME=$(awk 'BEGIN{c=0} //{c+=$2} END {print c}' *digi*.log_time)

# GAIN = (NTIMEFRAME * BKGSIMTIME + SGNTIME + DIGITIME) / (BKGSIMTIME + SGNTIME + DIGITIME)
awk -v BT=${BKGSIMTIME} -v ST=${SGNTIME} -v DT=${DIGITIME} -v NTF=${NTIMEFRAMES} 'END {print "SPEEDUP="(NTF*BT + ST + DT)/(BT + ST + DT)}' < /dev/null
