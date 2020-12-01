#!/usr/bin/env bash

# Embed jet-jet events in a pre-defined pT hard bin into HI events, both Pythia8
# Execute: ./run_jets_embedding.sh 
# Set at least before running PTHATBIN with 1 to 21

#set -x

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

RNDSEED=${RNDSEED:-0}   # [default = 0] time-based random seed
NSIGEVENTS=${NSIGEVENTS:-20}
NBKGEVENTS=${NBKGEVENTS:-20}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC" #"PIPE ITS TPC EMCAL"
CONFIG_ENERGY=${CONFIG_ENERGY:-5020.0}
CONFIG_NUCLEUSA=${CONFIG_NUCLEUSA:-2212}
CONFIG_NUCLEUSB=${CONFIG_NUCLEUSB:-2212}

# Define the pt hat bin arrays
pthatbin_loweredges=(0 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235)
pthatbin_higheredges=( 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235 -1)

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

# Generate background
taskwrapper bkgsim.log  o2-sim -j ${NWORKERS} -n ${NBKGEVENTS}         \
             -g pythia8hi -m ${MODULES} -o bkg                         \
             --configFile ${O2DPG_ROOT}/MC/config/common/ini/basic.ini 

# Register some background output --> make this declarative
copypersistentsimfiles bkg output      

# Loop over timeframes
for tf in `seq 1 ${NTIMEFRAMES}`; do

# Generate Pythia8 jet-jet configuration
${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
         --output=pythia8_jets.cfg \
         --seed=${RNDSEED}         \
         --idA=${CONFIG_NUCLEUSA}  \
         --idB=${CONFIG_NUCLEUSB}  \
         --eCM=${CONFIG_ENERGY}    \
         --process=jets            \
         --ptHatMin=${PTHATMIN}    \
         --ptHatMax=${PTHATMAX}

# Generate and embed signal into background
taskwrapper sgnsim_${tf}.log o2-sim -j ${NWORKERS} -n ${NSIGEVENTS} \
       -g pythia8 -m ${MODULES}                                     \
       --configKeyValues "GeneratorPythia8.config=pythia8_jets.cfg" \
       --embedIntoFile bkg_Kine.root                                \
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
