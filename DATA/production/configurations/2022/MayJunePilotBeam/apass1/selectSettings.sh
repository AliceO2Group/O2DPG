#!/bin/bash

# default
GRPMAG=o2sim_grp_b5m_128HB.root

if [[ $RUNNUMBER -le 518547 ]]; then
  # default B GRP till run 518547 
  GRPMAG=o2sim_grp_b5m_128HB.root
fi

# LHC22e: 519041 - 520099
if [[ $RUNNUMBER -ge 519041 ]] && [[ $RUNNUMBER -le 520099 ]]; then
  # +30kA/+6kA
  GRPMAG=o2sim_grp_b5p_128HB.root
fi

# LHC22f: 520143 - 520473
if [[ $RUNNUMBER -ge 520143 ]] && [[ $RUNNUMBER -le 520473 ]]; then
  # +30kA/+6kA
  GRPMAG=o2sim_grp_b5p_128HB.root
fi

# LHC22g: 520474 - 520477
if [[ $RUNNUMBER -ge 520474 ]] && [[ $RUNNUMBER -le 520477 ]]; then
  # +12kA/+6kA
  GRPMAG=o2sim_grp_b2p_128HB.root
fi

# LHC22h: 520495 - 520509
if [[ $RUNNUMBER -ge 520495 ]] && [[ $RUNNUMBER -le 520509 ]]; then
  # 0kA/0kA
  GRPMAG=o2sim_grp_b0_128HB.root
fi

# LHC22i: 520529 - 520542
if [[ $RUNNUMBER -ge 520529 ]] && [[ $RUNNUMBER -le 520542 ]]; then
  # -12kA/-6kA
  GRPMAG=o2sim_grp_b2m_128HB.root
fi

# LHC22j: 520543 - 521150
if [[ $RUNNUMBER -ge 520543 ]] && [[ $RUNNUMBER -le 521150 ]]; then
  # -30kA/-6kA
  GRPMAG=o2sim_grp_b5m_128HB.root
fi

# LHC22m: 521326 - 521907
if [[ $RUNNUMBER -ge 521326 ]]; then
  # -30kA/-6kA
  GRPMAG=o2sim_grp_b5m_128HB.root
fi

echo "GRP B field = $GRPMAG"

ln -s $GRPMAG o2sim_grp.root
