#!/bin/bash

GRPMAG=o2sim_grp_b5p_128HB.root
COLLISIONCONTEXT=collisioncontext_Single_3b_2_2_2.root

#if [[ $RUNNUMBER -ge 517676 ]] && [[ $RUNNUMBER -le 517679 ]]; then
#  COLLISIONCONTEXT=collisioncontext_Single_3b_0_2_2.root
#fi

# B field update
#if [[ $RUNNUMBER -ge 519041 ]]; then
#  GRPMAG=o2sim_grp_b5p_128HB.root
#fi

echo "GRP B field = $GRPMAG"
echo "filling scheme = $COLLISIONCONTEXT"

ln -s $COLLISIONCONTEXT collisioncontext.root
ln -s $GRPMAG o2sim_grp.root
