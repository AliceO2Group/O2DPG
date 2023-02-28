#!/bin/bash

TIMEFRAMESPERJOB=${ALIEN_JDL_TIMEFRAMESPERJOB-100000}
if [[ -f timeBins.log ]]; then
  rm timeBins.log
fi

# creating list of files
sed -rn 's/.*turl="([^"]*)".*/\1/p' $1 | sort -u > o2currents_tpc.txt

# now extracting timBins.log
cp $O2DPG_ROOT/DATA/production/configurations/asyncCalib/prepareBins.C
root -b -q "prepareBins.C+(\"o2currents_tpc.txt\", $TIMEFRAMESPERJOB)"
