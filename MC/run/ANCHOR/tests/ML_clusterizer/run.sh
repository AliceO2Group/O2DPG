#!/bin/bash

#JDL_OUTPUT=*.txt@disk=1,AO2D*.root@disk=2,*.log@disk=1,*stat*@disk=1,*.json@disk=1,debug*tgz@disk=2,tf*/coll*.root
#JDL_ERROROUTPUT=*.txt@disk=1,AO2D*.root@disk=2,*.log@disk=1,*.json@disk=1,debug*tgz@disk=2
#JDL_PACKAGE=O2PDPSuite::daily-20251215-0000-1

#
# An **EXAMPLE** showing injection of GPU_proc_nn config_keys into the workflow creation, so
# that TPC clusterizer runs with ML kernel.
#

# example anchoring
export ALIEN_JDL_LPMANCHORPASSNAME=apass4
export ALIEN_JDL_MCANCHOR=apass4
export ALIEN_JDL_CPULIMIT=8
export ALIEN_JDL_LPMRUNNUMBER=544124
export ALIEN_JDL_LPMPRODUCTIONTYPE=MC
export ALIEN_JDL_LPMINTERACTIONTYPE=PbPb
export ALIEN_JDL_LPMPRODUCTIONTAG=MLClusterTest
export ALIEN_JDL_LPMANCHORRUN=544124
export ALIEN_JDL_LPMANCHORPRODUCTION=LHC23zz
export ALIEN_JDL_LPMANCHORYEAR=2023

export NTIMEFRAMES=1
export PRODSPLIT=${ALIEN_O2DPG_GRIDSUBMIT_PRODSPLIT:-100}
export SPLITID=${ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID:-50}
export CYCLE=0

# this file modifies few config key values for GPU_proc_nn for application in TPC clusterization
LOCAL_CONFIG="customize_ml_clusterizing.json"
cat > ${LOCAL_CONFIG} <<EOF
{
  "ConfigParams": {
    "GPU_proc_nn" : {
      "nnInferenceDevice" : "CPU",
      "nnInferenceAllocateDevMem" : "0",
      "nnInferenceInputDType" : "FP16",
      "nnInferenceOutputDType" : "FP16",
      "nnSigmoidTrafoClassThreshold" : "1",
      "nnClusterizerAddIndexData" : "1",
      "nnInferenceIntraOpNumThreads" : "1",
      "nnInferenceInterOpNumThreads" : "1",
      "nnInferenceVerbosity" : "3",
      "nnClusterizerVerbosity" : "2",
      "nnClusterizerApplyCfDeconvolution" : "0",
      "nnLoadFromCCDB" : "1",
      "nnClusterizerBoundaryFillValue" : "0",
      "nnInferenceOrtProfiling" : "0",
      "nnClusterizerSetDeconvolutionFlags" : "1",
      "nnClusterizerSizeInputRow" : "1",
      "nnClusterizerSizeInputPad" : "4",
      "nnClusterizerSizeInputTime" : "4",
      "nnClassThreshold" : "0.05",
      "nnClusterizerUseCfRegression" : "0",
      "nnClusterizerBatchedMode" : "262144",
      "applyNNclusterizer" : "1"
    }
  }
  "Executables": {   
  }
}
EOF

# we use pp event gen just to get faster results
export ALIEN_JDL_ANCHOR_SIM_OPTIONS="-gen pythia8pp -confKey \"GeometryManagerParam.useParallelWorld=1;GeometryManagerParam.usePwGeoBVH=1;GeometryManagerParam.usePwCaching=1\" ${LOCAL_CONFIG:+--overwrite-config ${LOCAL_CONFIG}}"

export ALIEN_JDL_O2DPGWORKFLOWTARGET="tpcclus"
${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh
