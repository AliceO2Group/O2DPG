#!/usr/bin/env bash

RNDSEED=${RNDSEED:-0}
NWORKERS=${NWORKERS:-8}


export ALIEN_JDL_LPMPRODUCTIONTYPE=MC
export ALIEN_JDL_CPULIMIT=20
export ALIEN_JDL_LPMANCHORPASSNAME=apass4
export ALIEN_JDL_MCANCHOR=apass4
export ALIEN_JDL_COLLISIONSYSTEM=PbPb
export ALIEN_JDL_LPMPASSNAME=apass4
export ALIEN_JDL_LPMRUNNUMBER=544474
export ALIEN_JDL_LPMANCHORRUN=544474

export ALIEN_JDL_LPMINTERACTIONTYPE=PbPb
export ALIEN_JDL_LPMPRODUCTIONTAG="TestProd17032026"
export ALIEN_JDL_LPMANCHORPRODUCTION="LHC26ac"
export ALIEN_JDL_LPMANCHORYEAR=2023

export ALIEN_JDL_O2DPGWORKFLOWTARGET="aod"

export PRODSPLIT=${ALIEN_O2DPG_GRIDSUBMIT_PRODSPLIT:-10}
export SPLITID=${ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID:-10}
export CYCLE=0
export NTIMEFRAMES=8
export NSIGEVENTS=20
export NBKGEVENTS=10

# define the generator via ini file
# use 20/40/40 sampling for different generators
# generate random number
RNDSIG=$(($RANDOM % 100))


if [[ $RNDSIG -ge 0 && $RNDSIG -lt 20 ]];
then	  
	CONFIGNAME="GeneratorHF_Charm_PbPb_electron.ini"
elif [[ $RNDSIG -ge 20 && $RNDSIG -lt 100 ]];
then
	CONFIGNAME="GeneratorHF_BeautyNoForcedDecay_PbPb_electron.ini"
fi


# generator and other sim configuration; parallel world for ITS
SIM_OPTIONS="-eCM 5360 -gen external -j ${NWORKERS} -tf ${NTIMEFRAMES} -e TGeant4 -seed 0 -ini ${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/ini/$CONFIGNAME -genBkg pythia8 -procBkg \"heavy_ion\" -colBkg PbPb --embedding -nb $NBKGEVENTS"

export ALIEN_JDL_ANCHOR_SIM_OPTIONS="${SIM_OPTIONS}"

${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh

