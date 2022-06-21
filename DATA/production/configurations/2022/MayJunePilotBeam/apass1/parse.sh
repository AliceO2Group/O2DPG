#!/bin/bash

line=`grep $1 $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$ALIEN_JDL_LPMPASSNAME/ctf2epn.txt`
echo $line
epn=`echo $line | cut -d' ' -f1`
start=`echo $line | cut -d' ' -f2`
echo epn = $epn
echo start = $start

lineTimes=`grep ${epn} $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$ALIEN_JDL_LPMPASSNAME/goodITSMFT_fixed.txt`
echo lineTimes = $lineTimes
goodITS=`echo $lineTimes | cut -d' ' -f2`
echo goodITS = $goodITS
goodMFT=`echo $lineTimes | sed 's/^[0-9][0-9][0-9] \(2022-[0-9]*-[0-9]*-[0-9]*-[0-9]*-[0-9]*\) \(2022-[0-9]*-[0-9]*-[0-9]*-[0-9]*-[0-9]*\)/\2/'`
echo goodMFT = $goodMFT

startmonth=`echo $start | cut -d'-' -f2`
startday=`echo $start | cut -d'-' -f3`
starthour=`echo $start | cut -d'-' -f4`
startminute=`echo $start | cut -d'-' -f5`
startsecond=`echo $start | cut -d'-' -f6`

goodITSmonth=`echo $goodITS | cut -d'-' -f2`
goodITSday=`echo $goodITS | cut -d'-' -f3`
goodITShour=`echo $goodITS | cut -d'-' -f4`
goodITSminute=`echo $goodITS | cut -d'-' -f5`
goodITSsecond=`echo $goodITS | cut -d'-' -f6`

goodMFTmonth=`echo $goodMFT | cut -d'-' -f2`
goodMFTday=`echo $goodMFT | cut -d'-' -f3`
goodMFThour=`echo $goodMFT | cut -d'-' -f4`
goodMFTminute=`echo $goodMFT | cut -d'-' -f5`
goodMFTsecond=`echo $goodMFT | cut -d'-' -f6`

export remappingITS=0
if [[ $startday < $goodITSday ]]; then
    remappingITS=1
elif [[ $starthour < $goodITShour ]]; then
    remappingITS=1
elif [[ $startminute < $goodITSminute ]]; then
    remappingITS=1
elif [[ $startsecond < $goodITSsecond ]]; then
    remappingITS=1
fi

export remappingMFT=0
if [[ $startday < $goodMFTday ]]; then
    remappingMFT=1
elif [[ $starthour < $goodMFThour ]]; then
    remappingMFT=1
elif [[ $startminute < $goodMFTminute ]]; then
    remappingMFT=1
elif [[ $startsecond < $goodMFTsecond ]]; then
    remappingMFT=1
fi

echo "start = $start, goodITS = $goodITS, goodMFT = $goodMFT, remappingITS = $remappingITS, remappingMFT = $remappingMFT"



