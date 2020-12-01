#!/usr/bin/env bash

# Generate gamma-jet events, Pythia8 in a given pt hard bin.
# Execute: ./run_dirgamma.sh 
# Set at least before running PTHATBIN with 1 to 6


#set -x 

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

RNDSEED=${RNDSEED:-0}   # [default = 0] time-based random seed

NSIGEVENTS=${NSIGEVENTS:-20}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC" #"PIPE ITS TPC EMCAL"
CONFIG_ENERGY=${CONFIG_ENERGY:-5020.0}
CONFIG_NUCLEUSA=${CONFIG_NUCLEUSA:-2212}
CONFIG_NUCLEUSB=${CONFIG_NUCLEUSB:-2212}

# Define the pt hat bin arrays
pthatbin_loweredges=(5 11 21 36 57 84)
pthatbin_higheredges=(11 21 36 57 84 -1)

# Recover environmental vars for pt binning
#PTHATBIN=${PTHATBIN:-1} 

if [ -z "$PTHATBIN" ]; then
    echo "Pt-hat bin (env. var. PTHATBIN) not set, abort."
    exit 1
fi

PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}

# We will collect output files of the workflow in a dedicated output dir
# (these are typically the files that should be left-over from a GRID job)
[ ! -d output ] && mkdir output

copypersistentsimfiles() {
  simprefix=$1
  outputdir=$2
  cp ${simprefix}_Kine.root ${simprefix}_grp.root ${simprefix}*.ini ${outputdir}
}

# Loop over timeframes
for tf in `seq 1 ${NTIMEFRAMES}`; do

# Generate Pythia8 gamma-jet configuration
${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
        --output=pythia8_dirgamma.cfg \
        --seed=${RNDSEED}             \
        --idA=${CONFIG_NUCLEUSA}      \
        --idB=${CONFIG_NUCLEUSB}      \
        --eCM=${CONFIG_ENERGY}        \
        --process=dirgamma            \
        --ptHatMin=${PTHATMIN}        \
        --ptHatMax=${PTHATMAX}

# Generate signal 
taskwrapper sgnsim_${tf}.log o2-sim -j ${NWORKERS} -n ${NSIGEVENTS}         \
           -g pythia8 -m ${MODULES}                                         \
           --configKeyValues "GeneratorPythia8.config=pythia8_dirgamma.cfg" \
           -o sgn${tf}
 
# Register some signal output --> make this declarative
copypersistentsimfiles sgn${tf} output
# We need to copy the current grp for tpc-reco
cp sgn${tf}_grp.root o2sim_grp.root

CONTEXTFILE=collisioncontext_${tf}.root
 
# Add from here digitization, reconstruction?
 
# Cleanup step for this timeframe (we cleanup disc space early so as to make possible checkpoint dumps smaller)
#taskwrapper cleanup_${tf}.log "[ -f tpcreco_${tf}.log_done ] && rm sgn${tf}* && rm *digits*.root"
taskwrapper cleanup_${tf}.log "rm sgn${tf}*"

done

# We need to exit for the ALIEN JOB HANDLER!
exit 0
