#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh 

export SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM
export GPUMEMSIZE=$(( 24 << 30 ))
export HOSTMEMSIZE=$(( 5 << 30 ))
export GPUTYPE="HIP"


if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

### Comment: MAKE SURE the channels match address=ipc://@tf-builder-pipe-0
HOST=localhost
QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-raw-qcmn"
QC_CONFIG_CONSUL="/o2/components/qc/ANY/any/tpc-raw-qcmn"
EXTRA_CONFIG="TPCDigitDump.NoiseThreshold=3;TPCDigitDump.LastTimeBin=600"


WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\"" "" 0
add_W o2-tpc-raw-to-digits-workflow "--ignore-grp --input-spec \"$CALIB_INSPEC\" --remove-duplicates --pipeline tpc-raw-to-digits-0:20" "${EXTRA_CONFIG}"
add_QC_from_consul "${QC_CONFIG_CONSUL}" "--local --host lcoalhost"



WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"
if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi





#o2-dpl-raw-proxy $ARGS_ALL \
#    --dataspec "$PROXY_INSPEC" --inject-missing-data \
#    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
#    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
#    --input-spec "$CALIB_INSPEC"  \
#    --configKeyValues "TPCDigitDump.NoiseThreshold=3;TPCDigitDump.LastTimeBin=600;$ARGS_ALL_CONFIG" \
#    --pipeline tpc-raw-to-digits-0:20 \
#    --remove-duplicates \
#    | o2-qc $ARGS_ALL --config $QC_CONFIG --local --host $HOST \
#    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE}

