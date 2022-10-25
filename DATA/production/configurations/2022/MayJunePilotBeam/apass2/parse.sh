#!/bin/bash

line=`grep $1 $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$ALIEN_JDL_LPMPASSNAME/ctf2epn.txt`
echo "line found in file = $line"
if [[ -z $line ]]; then
  echo "CTF file not present in our list, no remapping needed"
  export remappingITS=0
  export remappingMFT=0
  echo "remappingITS = $remappingITS, remappingMFT = $remappingMFT"
else
  epn=`echo $line | cut -d' ' -f1`
  start=`echo $line | cut -d' ' -f2`
  echo "epn = $epn"
  echo "start of CTF data = $start"

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

  echo "good ITS: month = $goodITSmonth, day = $goodITSday, hour = $goodITShour, minute = $goodITSminute, seconds = $goodITSsecond"
  echo "good MFT: month = $goodMFTmonth, day = $goodMFTday, hour = $goodMFThour, minute = $goodMFTminute, seconds = $goodMFTsecond"
  echo "checking: month = $startmonth, day = $startday, hour = $starthour, minute = $startminute, seconds = $startsecond"

  # check for ITS
  if [[ $startmonth < $goodITSmonth ]]; then
    echo "month triggers remappingITS"
    remappingITS=1
  elif [[ $startmonth == $goodITSmonth ]]; then
    if [[ $startday < $goodITSday ]]; then
      echo "day triggers remappingITS"
      remappingITS=1
    elif [[ $startday == $goodITSday ]]; then
      if [[ $starthour < $goodITShour ]]; then
	echo "hour triggers remappingITS"
	remappingITS=1
      elif [[ $starthour == $goodITShour ]]; then
	if [[ $startminute < $goodITSminute ]]; then
	  echo "minute triggers remappingITS"
	  remappingITS=1
	elif [[ $startminute == $goodITSminute ]]; then
	  if [[ $startsecond -le $goodITSsecond ]]; then
	    echo "second triggers remappingITS"
	    remappingITS=1
	  else
	    echo "month, day, hour, minute would trigger remapping, but seconds are larger than what is needed to trigger remapping for ITS"
	  fi
	else
	  echo "month, day, hour would trigger remapping, but minutes are larger than what is needed to trigger remapping for ITS"
	fi
      else
	echo "month, day would trigger remapping, but hours are larger than what is needed to trigger remapping for ITS"
      fi
    else
      echo "month, would trigger remapping, but days are larger than what is needed to trigger remapping for ITS"
    fi
  else 
    echo "start month is later than what is needed to trigger remapping for ITS"
  fi

  # check for MFT
  if [[ $startmonth < $goodMFTmonth ]]; then
    echo "month triggers remappingMFT"
    remappingMFT=1
  elif [[ $startmonth == $goodMFTmonth ]]; then
    if [[ $startday < $goodMFTday ]]; then
      echo "day triggers remappingMFT"
      remappingMFT=1
    elif [[ $startday == $goodMFTday ]]; then
      if [[ $starthour < $goodMFThour ]]; then
	echo "hour triggers remappingMFT"
	remappingMFT=1
      elif [[ $starthour == $goodMFThour ]]; then
	if [[ $startminute < $goodMFTminute ]]; then
	  echo "minute triggers remappingMFT"
	  remappingMFT=1
	elif [[ $startminute == $goodMFTminute ]]; then
	  if [[ $startsecond -le $goodMFTsecond ]]; then
	    echo "second triggers remappingMFT"
	    remappingMFT=1
	  else
	    echo "month, day, hour, minute would trigger remapping, but seconds are larger than what is needed to trigger remapping for MFT"
	  fi
	else
	  echo "month, day, hour would trigger remapping, but minutes are larger than what is needed to trigger remapping for MFT"
	fi
      else
	echo "month, day would trigger remapping, but hours are larger than what is needed to trigger remapping for MFT"
      fi
    else
      echo "month, would trigger remapping, but days are larger than what is needed to trigger remapping for MFT"
    fi
  else 
    echo "start month is later than what is needed to trigger remapping for MFT"
  fi


  echo "start = $start, goodITS = $goodITS, goodMFT = $goodMFT, remappingITS = $remappingITS, remappingMFT = $remappingMFT"
fi


