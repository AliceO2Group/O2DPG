export WORKFLOW_DETECTORS_CTF="EMC" 
export WORKFLOW_DETECTORS="EMC"
export ARGS_EXTRA_PROCESS_o2_ctf_writer_workflow=" --no-grp "
export ARGS_EXTRA_PROCESS_o2_emcal_reco_workflow=" --fitmethod=standard "
export ARGS_EXTRA_PROCESS_o2_raw_tf_reader_workflow=" --raw-only-det all "
export EXTRA_WORKFLOW=" o2-emcal-standalone-aod-producer-workflow --aod-writer-keep dangling --aod-writer-resfile \"AO2D\" --aod-writer-resmode UPDATE "

# Enabling QC
export WORKFLOW_PARAMETERS="QC,${WORKFLOW_PARAMETERS}"
export GEN_TOPO_WORKDIR="./"
export QC_CONFIG_PARAM="--local-batch=QC.root --override-values \"qc.config.Activity.number=$RUNNUMBER;qc.config.Activity.passName=$PASS;qc.config.Activity.periodName=$PERIOD\""
export GEN_TOPO_WORKDIR="./"
export QC_JSON_FROM_OUTSIDE="$O2DPG_ROOT/DATA/production/configurations/$YEAR/ctf_recreation/emc-qc.json"

if [[ ! -z $QC_JSON_FROM_OUTSIDE ]]; then
    sed -i 's/REPLACE_ME_RUNNUMBER/'"${RUNNUMBER}"'/g' $QC_JSON_FROM_OUTSIDE
    sed -i 's/REPLACE_ME_PASS/'"${PASS}"'/g' $QC_JSON_FROM_OUTSIDE
    sed -i 's/REPLACE_ME_PERIOD/'"${PERIOD}"'/g' $QC_JSON_FROM_OUTSIDE
fi
