#!/bin/bash

#
# An example steering script for anchored MC simulations, pp
#

# example anchoring
# taken from https://its.cern.ch/jira/browse/O2-4586
export ALIEN_JDL_LPMANCHORPASSNAME=apass2
export ALIEN_JDL_MCANCHOR=apass2
export ALIEN_JDL_COLLISIONSYSTEM=p-p
export ALIEN_JDL_CPULIMIT=8
export ALIEN_JDL_LPMPASSNAME=apass2
export ALIEN_JDL_LPMRUNNUMBER=535069
export ALIEN_JDL_LPMPRODUCTIONTYPE=MC
export ALIEN_JDL_LPMINTERACTIONTYPE=pp
export ALIEN_JDL_LPMPRODUCTIONTAG=LHC24a2
export ALIEN_JDL_LPMANCHORRUN=535069
export ALIEN_JDL_LPMANCHORPRODUCTION=LHC23f
export ALIEN_JDL_LPMANCHORYEAR=2023

export NTIMEFRAMES=1
export NSIGEVENTS=50
export SPLITID=100
export PRODSPLIT=153
export CYCLE=0

# on the GRID, this is set, for our use case, we can mimic any job ID
export ALIEN_PROC_ID=2963436952

# for pp and 50 events per TF, we launch only 4 workers.
export NWORKERS=4

# run the central anchor steering script; this includes
# * derive timestamp
# * derive interaction rate
# * extract and prepare configurations (which detectors are contained in the run etc.)
# * run the simulation (and QC)
${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh
