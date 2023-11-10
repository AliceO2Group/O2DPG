#!/bin/bash

# ------------------------------------------------------------------------
#         ALICE HMPID detector
# Workflow to calculate pedestals   v.3.0  = 24/08/2023
#
#  Extra Env Variables:
#     HMP_SIGMACUT : The value of sigams for the threshold cut [=4]
#     HMP_CCDB_REC : True if we want the recording into ALICE CCDB [=False]
#     HMP_PED_TAG :  A string that tags the pedestals [=Latest]
#     HMP_NODCSCCDB_REC : True if we want disable DCS CCDB recording [=False]
#     HMP_FILES_REC : True if we want store on files (Only for debug) [=False]
#
#   14/09/2023 - rebase
#
#   Auth. A.Franco  - INFN  Sez.BARI - ITALY
# ------------------------------------------------------------------------

# Set general arguments
source common/setenv.sh
source common/gen_topo_helper_functions.sh
source common/getCommonArgs.sh

# Define the Input/Output streams
PROXY_INSPEC="A:HMP/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
PROXY_OUTSPEC="A:HMP/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"

# assign the HMP extra Env Vars.
if [ -z ${HMP_SIGMACUT+x} ];
then
    HMP_SIGMACUT="4"
fi
if [ -z ${HMP_NODCSCCDB_REC+x} ];
then
    HMP_NODCSCCDB_REC="false"
else
    HMP_NODCSCCDB_REC="true"
fi
if [ -z ${HMP_CCDB_REC+x} ];
then
    HMP_CCDB_REC="false"
else
    HMP_CCDB_REC="true"
fi
if [ -z ${HMP_FILES_REC+x} ];
then
    HMP_FILES_REC="false"
else
    HMP_FILES_REC="true"
fi
if [ -z ${HMP_PED_TAG+x} ];
then
    HMP_PED_TAG="Latest"
fi

# Compose the specific parameters
SPEC_PARAM=""
if [ $HMP_NODCSCCDB_REC == 'false' ];
then
  SPEC_PARAM+="--use-dcsccdb --dcsccdb-uri 'http://alio2-cr1-flp199.cern.ch:8083' --dcsccdb-alivehours 3 "
fi
if [ $HMP_CCDB_REC == 'true' ];
then
  SPEC_PARAM+="--use-ccdb --ccdb-uri 'http://o2-ccdb.internal' "
fi
if [ $HMP_FILES_REC == 'true' ];
then
  SPEC_PARAM+="--use-files "
fi

SPEC_PARAM+="--files-basepath 'HMP' "
SPEC_PARAM+="--pedestals-tag ${HMP_PED_TAG} --sigmacut ${HMP_SIGMACUT}"

#  Here we compose the workflow
# Start with an empty workflow
WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,rateLogging=1,transport=shmem\"" "" 0
add_W o2-hmpid-raw-to-pedestals-workflow "--fast-decode $SPEC_PARAM"

# Finally add the o2-dpl-run workflow manually, allow for either printing the workflow or creating a topology (default)
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

[[ $WORKFLOWMODE != "print" ]] && WORKFLOW+=" --${WORKFLOWMODE} ${WORKFLOWMODE_FILE:-}"
[[ $WORKFLOWMODE == "print" || "${PRINT_WORKFLOW:-}" == "1" ]] && echo "#HMPID Pedestals Calculation (v.3) workflow command:\n\n${WORKFLOW}\n" | sed -e "s/\\\\n/\n/g" -e"s/| */| \\\\\n/g" | eval cat $( [[ $WORKFLOWMODE == "dds" ]] && echo '1>&2')
if [[ $WORKFLOWMODE != "print" ]]; then eval $WORKFLOW; else true; fi

# -------  EOF --------
