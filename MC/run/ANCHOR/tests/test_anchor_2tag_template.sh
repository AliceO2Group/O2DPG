#!/bin/bash
#JDL_OUTPUT=*.txt@disk=1,AO2D.root@disk=2,*.log@disk=1,*stat*@disk=1,*.json@disk=1,debug*tgz@disk=2
#JDL_ERROROUTPUT=*.txt@disk=1,AO2D.root@disk=2,*.log@disk=1,*.json@disk=1,debug*tgz@disk=2
#JDL_PACKAGE=%{SOFTWARETAG_SIM}
#JDL_REQUIRE=%{JDL_REQUIREMENT}

#
# A template anchoring script to test various anchoring setups
# and software combinations
#

# only relevant if executed locally
if [ ! ${O2_ROOT} ]; then
  source <(/cvmfs/alice.cern.ch/bin/alienv printenv %{SOFTWARETAG_SIM})
fi

# meta configuration of the job (influences reco config)
export ALIEN_JDL_LPMPRODUCTIONTYPE=MC
export ALIEN_JDL_CPULIMIT=8

export ALIEN_JDL_LPMANCHORPASSNAME=%{PASSNAME}
export ALIEN_JDL_MCANCHOR=%{PASSNAME}
export ALIEN_JDL_COLLISIONSYSTEM=%{COL_SYSTEM}
export ALIEN_JDL_LPMPASSNAME=%{PASSNAME}
export ALIEN_JDL_LPMRUNNUMBER=%{RUN_NUMBER}
export ALIEN_JDL_LPMANCHORRUN=%{RUN_NUMBER}

export ALIEN_JDL_LPMINTERACTIONTYPE=%{INTERACTIONTYPE}
export ALIEN_JDL_LPMPRODUCTIONTAG=%{PRODUCTION_TAG}
export ALIEN_JDL_LPMANCHORPRODUCTION=%{ANCHOR_PRODUCTION}
export ALIEN_JDL_LPMANCHORYEAR=%{ANCHORYEAR}
export ALIEN_JDL_O2DPG_ASYNC_RECO_TAG="%{SOFTWARETAG_ASYNC}"

# get custom O2DPG for 2tag treatment (could be used to test different O2DPG branches)
# git clone https://github.com/AliceO2Group/O2DPG O2DPG
# export O2DPG_ROOT=${PWD}/O2DPG
# export ALIEN_JDL_O2DPG_OVERWRITE=${PWD}/O2DPG

# dimension the job
export NTIMEFRAMES=1

# further configuration of the job
export ALIEN_JDL_ADDTIMESERIESINMC=0
export DISABLE_QC=1
export ALIEN_JDL_MC_ORBITS_PER_TF=10000:10000000:2 # puts just 2 orbit for large enough interaction rates
export ALIEN_JDL_O2DPGWORKFLOWTARGET="aod"

# select anchoring points
export PRODSPLIT=${ALIEN_O2DPG_GRIDSUBMIT_PRODSPLIT:-100}
export SPLITID=${ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID:-50}
export CYCLE=0

# generator and other sim configuration
export ALIEN_JDL_ANCHOR_SIM_OPTIONS="%{SIM_OPTIONS}"

export O2DPG_CUSTOM_REPO="%{O2DPG_CUSTOM_REPO}"

# we allow the possibility to use a special O2DPG version
if [ "${O2DPG_CUSTOM_REPO}" ]; then
  echo "Checking out custom O2DPG repo ${O2DPG_CUSTOM_REPO}"
  git clone "${O2DPG_CUSTOM_REPO}" O2DPG
  export O2DPG_ROOT=${PWD}/O2DPG
  export ALIEN_JDL_O2DPG_OVERWRITE=${PWD}/O2DPG
else
  echo "Using O2DPG from released software tag ${O2DPG_ROOT}"
fi

# execute MC
${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh
