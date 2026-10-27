#!/usr/bin/env bash
#JDL_PACKAGE=VO_ALICE@O2PDPSuite::MC-prod-2026-v13-1
#JDL_OUTPUT=AO2D.root@disk=2,debug_log_archive.tgz@disk=2
#JDL_ERROROUTPUT=debug_log_archive.tgz@disk=2

# Anchored Pb-Pb MC: STARlight UPC events on top of hadronic (Pythia8 Angantyr) pile-up.
#
# The hadronic Pb-Pb collisions follow the interaction rate of the anchor run. On top of them,
# UPC events are injected as an independent random stream at UPC_RATE, each in its own bunch
# crossing. The interaction-rate dependence is obtained by choosing anchor runs at different rates.
# In the AOD, the UPC collisions have generator ID 51 (mcCollision.getGeneratorId()).
#
# Knobs:
#   UPC_PROCESS    STARlight process (as in makeStarlightConfig.py)
#   UPC_RATE       rate of the UPC stream in Hz; 67000 is about one per ITS readout frame
#   NBKG           distinct Angantyr events per job, reused in turn; a repeated event
#                  appears milliseconds later, far beyond an ITS readout frame or the TPC drift time
#   ANCHOR_RUN     anchor run; the interaction rate is taken from its CTP scalers
#   NTIMEFRAMES    timeframes per job; the background is simulated once per job,
#                  so more timeframes per job is cheaper than many short jobs
#
# The timeframe length is taken from the anchor run (32 orbits for 2023 Pb-Pb).
# Do not force longer timeframes with ALIEN_JDL_MC_ORBITS_PER_TF: with realistic
# hadronic pile-up, TPC digitisation then exceeds the memory of a GRID slot.
#
# Use MC-prod-2026-v12-1 or later: older tags anchor the first job at the start of the run,
# where the ITS dead map masks all chips and the AOD has no ITS and no collisions.
#
# Submit to the GRID with
#   ${O2DPG_ROOT}/GRID/utils/grid_submit.sh --script upc_in_hadronic_pileup.sh --jobname upc --cores 8 --ttl 43200

UPC_PROCESS=${UPC_PROCESS:-kCohJpsiToMu}
UPC_RATE=${UPC_RATE:-67000}
NBKG=${NBKG:-30}
ANCHOR_RUN=${ANCHOR_RUN:-544868}

export O2DPG_MC_CONFIG_ROOT=${O2DPG_MC_CONFIG_ROOT:-${O2DPG_ROOT}}

# anchoring: Pb-Pb 2023, apass5
export ALIEN_JDL_LPMANCHORPASSNAME=apass5
export ALIEN_JDL_MCANCHOR=apass5
export ALIEN_JDL_LPMANCHORYEAR=2023
export ALIEN_JDL_LPMINTERACTIONTYPE=PbPb
export ALIEN_JDL_LPMPRODUCTIONTYPE=MC
export ALIEN_JDL_LPMPRODUCTIONTAG=${ALIEN_JDL_LPMPRODUCTIONTAG:-UPCPileupExample}
export ALIEN_JDL_LPMRUNNUMBER=${ANCHOR_RUN}
export ALIEN_JDL_LPMANCHORRUN=${ANCHOR_RUN}
export ALIEN_JDL_LPMANCHORPRODUCTION=LHC23zzh
# reconstruction with the software of the data pass (2-tag setup)
export ALIEN_JDL_O2DPG_ASYNC_RECO_TAG=VO_ALICE@O2PDPSuite::async-async-2023-PbPb-apass5-v8-slc9-alidist-async-2023-PbPb-apass5-v8-1
export ALIEN_JDL_TPCDEDXCLMASK=7
export ALIEN_JDL_TPCCLUSTERFILTER=2
export ALIEN_JDL_TPCCHICUTOPT=0
export ALIEN_JDL_TPCCLUSEDGEREDEF=0.5

export NTIMEFRAMES=${NTIMEFRAMES:-2}
export NSIGEVENTS=10000          # no cap: the timeframe is filled by the interaction rate
export SPLITID=${ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID:-1}
export PRODSPLIT=${ALIEN_O2DPG_GRIDSUBMIT_PRODSPLIT:-1}
export CYCLE=0
export DISABLE_QC=1
export PUBLISH_MCPRODINFO=0     # example: do not publish to CCDB

cat > simconfig.json <<'EOF'
{
  "ConfigParams": {
    "TPCEleParam": {
      "doSaturationTail" : "1"
    }
  }
}
EOF

${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGUD/ini/makeStarlightConfig.py --process ${UPC_PROCESS} --collType PbPb --eCM 5360 --rapidity cent_rap

export ALIEN_JDL_ANCHOR_SIM_OPTIONS="-gen external -trigger external -ini ../GenStarlight.ini \
 -confKey 'PrimaryGenerator.id=51;SimCutParams.stepTrackRefHook=true' \
 --embedding -genBkg pythia8 -procBkg heavy_ion -nb ${NBKG} --embeddPattern ${UPC_RATE},1000000:1000000 \
 --overwrite-config simconfig.json --no-tpc-digitchunking --tpc-distortion-type 2 --tpc-corrmap-lumi-mode 2"

${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh
