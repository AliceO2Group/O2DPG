#!/bin/bash

export ALIEN_JDL_LPMANCHORPASSNAME="apass4"
export ALIEN_JDL_MCANCHOR="apass4"
export ALIEN_JDL_COLLISIONSYSTEM="pp"
export ALIEN_JDL_LPMPASSNAME="apass4"
export ALIEN_JDL_LPMRUNNUMBER="539071"
export ALIEN_JDL_LPMPRODUCTIONTYPE="MC"
export ALIEN_JDL_LPMINTERACTIONTYPE="pp"
export ALIEN_JDL_LPMPRODUCTIONTAG="LHC24_2023zg_apass4_MC_test"
export ALIEN_JDL_LPMANCHORRUN="539071"
export ALIEN_JDL_LPMANCHORPRODUCTION="LHC23zg"
export ALIEN_JDL_LPMANCHORYEAR="2023"

# added export
export NTIMEFRAMES=8
export NSIGEVENTS=100
export SPLITID=100
export PRODSPLIT=153
export CYCLE=0
export ALIEN_PROC_ID=2963436952

# disable the QC
export DISABLE_QC=1

# modify ini file, to have external generator and/or config from a specific tag different from the one used for anchoring
ORIGINALINI=${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF_D2H_bbbar_Bforced_gap5_Mode2.ini # original .ini file to be modified
MODIFIEDINI=GeneratorHF_D2H_bbbar_Bforced_gap5_Mode2_fromCVMFS.ini # output name for the modified .ini file

CFGTOREPLACE="\${O2DPG_ROOT}/MC/config/PWGHF/pythia8/generator/pythia8_beautyhadronic_with_decays_Mode2.cfg" # original config file name to be modified
CFGFROMCVMFS="/cvmfs/alice.cern.ch/el9-x86_64/Packages/O2DPG/daily-20240912-0200-1/MC/config/PWGHF/pythia8/generator/pythia8_beautyhadronic_with_decays_Mode2.cfg" # new config file name to use

GENTOREPLACE="\${O2DPG_ROOT}/MC/config/PWGHF/external/generator/generator_pythia8_gaptriggered_hf.C" # original external generator file name to be modified
GENFROMCVMFS="/cvmfs/alice.cern.ch/el9-x86_64/Packages/O2DPG/daily-20240912-0200-1/MC/config/PWGHF/external/generator/generator_pythia8_gaptriggered_hf.C" # new external generator file name to use

if [ ! -f $MODIFIEDINI ]; then
    sed -e "s|$CFGTOREPLACE|$CFGFROMCVMFS|g" -e "s|$GENTOREPLACE|$GENFROMCVMFS|g" $ORIGINALINI > $MODIFIEDINI
fi

export ALIEN_JDL_ANCHOR_SIM_OPTIONS="-gen external -ini $MODIFIEDINI"

${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh
