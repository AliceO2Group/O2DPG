#!/bin/bash

#
# Steering script for HF enhanced dielectron MC anchored to LHC24ap,aq apass1
#

# example anchoring
# taken from https://its.cern.ch/jira/browse/O2-5670
export ALIEN_JDL_LPMANCHORPASSNAME=apass1
export ALIEN_JDL_MCANCHOR=apass1
export ALIEN_JDL_CPULIMIT=8
export ALIEN_JDL_LPMRUNNUMBER=559348
export ALIEN_JDL_LPMPRODUCTIONTYPE=MC
export ALIEN_JDL_LPMINTERACTIONTYPE=pp
export ALIEN_JDL_LPMPRODUCTIONTAG=LHC24a6
export ALIEN_JDL_LPMANCHORRUN=559348
export ALIEN_JDL_LPMANCHORPRODUCTION=LHC24ap
export ALIEN_JDL_LPMANCHORYEAR=2024
export ALIEN_JDL_OUTPUT=*.dat@disk=1,*.txt@disk=1,*.root@disk=2

export NTIMEFRAMES=1
export NSIGEVENTS=20
export SPLITID=100
export PRODSPLIT=153
export CYCLE=0

# on the GRID, this is set and used as seed; when set, it takes precedence over SEED
#export ALIEN_PROC_ID=2963436952
export SEED=0

# for pp and 50 events per TF, we launch only 4 workers.
export NWORKERS=2

# define the generator via ini file
# use 20/40/40 sampling for different generators
# generate random number
#RNDSIG=$(($RANDOM % 100))

CONFIGNAME="GeneratorDYee_GapTriggered_Gap5_pp5360GeV.ini"

export ALIEN_JDL_ANCHOR_SIM_OPTIONS="-gen external -ini $O2DPG_ROOT/MC/config/PWGEM/ini/$CONFIGNAME"

# run the central anchor steering script; this includes
# * derive timestamp
# * derive interaction rate
# * extract and prepare configurations (which detectors are contained in the run etc.)
# * run the simulation (and QC)
# To disable QC, uncomment the following line
#export DISABLE_QC=1
${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh
