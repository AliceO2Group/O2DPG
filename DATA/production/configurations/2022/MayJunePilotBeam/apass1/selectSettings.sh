#!/bin/bash

if [[ $RUNNUMBER -le 518547 ]]; then
  # default B GRP till run 518547 
  GRPMAG=o2sim_grp_b5m_128HB.root
  # default collision context till 13.06.2022
  COLLISIONCONTEXT=collisioncontext_Single_4b_2_2_2_noLR.root
fi

if [[ $RUNNUMBER -ge 517676 ]] && [[ $RUNNUMBER -le 517679 ]]; then
  COLLISIONCONTEXT=collisioncontext_Single_3b_0_2_2.root
fi

if [[ $RUNNUMBER -ge 517684 ]] && [[ $RUNNUMBER -le 517693 ]]; then
  COLLISIONCONTEXT=collisioncontext_Single_3b_3_1_1.root
fi

if [[ $RUNNUMBER -ge 519041 ]] && [[ $RUNNUMBER -le 519507 ]]; then
  COLLISIONCONTEXT=collisioncontext_Single_16b_8_8_8_noLR.root
fi

if [[ $RUNNUMBER -ge 519903 ]] && [[ $RUNNUMBER -le 520099 ]]; then
  COLLISIONCONTEXT=collisioncontext_Single_4b_2_2_2_noLR.root
fi

# B field update
if [[ $RUNNUMBER -ge 519041 ]]; then
  GRPMAG=o2sim_grp_b5p_128HB.root
fi

echo "GRP B field = $GRPMAG"
echo "filling scheme = $COLLISIONCONTEXT"

ln -s $COLLISIONCONTEXT collisioncontext.root
ln -s $GRPMAG o2sim_grp.root
