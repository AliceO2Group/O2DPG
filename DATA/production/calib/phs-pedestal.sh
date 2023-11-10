#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

if [ -z $PHS_MAX_STATISTICS ] ; then
  PHS_MAX_STATISTICS=10000
fi

PROXY_INSPEC="A:PHS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

EXTRA_CONFIG=" "

if [ -z $PHS_CCDB_PATH ] ; then
  PHS_CCDB_PATH="http://o2-ccdb.internal"
fi

QC_CONFIG=consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/phs-pedestal-qc

o2-dpl-raw-proxy $ARGS_ALL \
		 --dataspec "$PROXY_INSPEC" --inject-missing-data \
		 --readout-proxy '--channel-config "name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"' \
    | o2-phos-reco-workflow $ARGS_ALL \
			    --input-type raw  \
			    --output-type cells \
			    --pedestal on \
			    --disable-root-input \
			    --disable-root-output \
    | o2-phos-calib-workflow $ARGS_ALL \
			     --pedestals \
			     --statistics $PHS_MAX_STATISTICS \
			     --configKeyValues "NameConf.mCCDBServer=${PHS_CCDB_PATH}" \
			     --forceupdate \
    | o2-qc $ARGS_ALL \
            --config $QC_CONFIG \
    | o2-calibration-ccdb-populator-workflow $ARGS_ALL \
					     --ccdb-path $PHS_CCDB_PATH \
    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE}
