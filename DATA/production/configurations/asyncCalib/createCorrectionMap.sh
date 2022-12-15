#!/bin/bash

# Create correction maps for a list of input files.
# The scripts assumes to get as input parameters 
# - the xml collection of the o2tpc_residuals*.root files created for a single run
# - the pattern of the calibration interval extracted by the 'createJobList.sh' macro.
# It creates an two output files
# - TPCDebugVoxRes*.root, containing the tree of extracted residuals
# - TPCFastTransform*.root, containing the spline object to be used in the reconstruction

# ===| input parameters & output file names  |==================================
inputCollection=$1
mergePattern=$2
filePattern="o2tpc_residuals_${mergePattern}\.root"

# This could be used for the old file format
if [[ $ALIEN_JDL_OLDFILENAME == "1" ]]; then
  filePattern="o2tpc_residuals${mergePattern}.*\.root"
fi

# job is over all files
if [[ "$mergePattern" == "all" ]]; then
  filePattern=".*"
fi

fileList=inputFileList.txt
voxResOutFile=TPCDebugVoxRes_${mergePattern}.root
splineOutFile=TPCFastTransform_${mergePattern}.root

[[ -z "${ALIEN_JDL_MAPCREATORARGS}" ]] && ALIEN_JDL_MAPCREATORARGS='--configKeyValues "scdcalib.maxSigY=2;scdcalib.maxSigZ=2"'
[[ -z "${ALIEN_JDL_MAPKNOTSY}" ]] && ALIEN_JDL_MAPKNOTSY=10
[[ -z "${ALIEN_JDL_MAPKNOTSZ}" ]] && ALIEN_JDL_MAPKNOTSZ=20

# ===| create intput list |=====================================================
sed -rn 's|.*turl="([^"]*)".*|\1|p' $inputCollection | grep "$filePattern" | sort -n > ${fileList}

declare -i nLines=$(wc -l ${fileList} | awk '{print $1}')
if [[ $nLines -eq 0 ]]; then
  echo "ERROR: Could not find lines matching '${mergePattern}' in file '${inputCollection}'. Cannot continue with SCD correction."
  exit
fi
echo "Creating residual map for $nLines input files"

# ===| create tree with residuals |=============================================
cmd="o2-tpc-static-map-creator $ALIEN_JDL_MAPCREATORARGS --residuals-infiles ${fileList} --outfile ${voxResOutFile} &> residuals.log"
echo "running: '$cmd'"
if [[ $ALIEN_JDL_DONTEXTRACTTPCCALIB != "1" ]]; then
  eval $cmd
  if [[ ! -s ${voxResOutFile} ]]; then
    echo "ERROR: Output file '${voxResOutFile}' not created, or zero size. Cannot continue with SCD correction."
    exit
  fi
fi

# ===| create spline object |===================================================
cmd="root.exe -q -x -l -n $O2_ROOT/share/macro/TPCFastTransformInit.C'(\"${voxResOutFile}\", \"${splineOutFile}\")' &> splines.log"
if [[ $(grep 'TPCFastTransformInit(' $O2_ROOT/share/macro/TPCFastTransformInit.C) =~ nKnots ]]; then
  cmd="root.exe -q -x -l -n $O2_ROOT/share/macro/TPCFastTransformInit.C'(${ALIEN_JDL_MAPKNOTSY}, ${ALIEN_JDL_MAPKNOTSZ}, \"${voxResOutFile}\", \"${splineOutFile}\")' &> splines.log"
fi
echo "running: '$cmd'"
if [[ $ALIEN_JDL_DONTEXTRACTTPCCALIB != "1" ]]; then
  eval $cmd
fi
