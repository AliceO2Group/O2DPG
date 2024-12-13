# Run as:  ${O2DPG_ROOT}/GRID/utils/grid_submit.sh --script ./runGraniittiANCHOR.sh --jobname SLtest --outputspec "*.log@disk=1","*.root@disk=2" --packagespec "VO_ALICE@O2sim::v20240626-1" --wait --fetch-output --asuser pbuhler --local

export ALIEN_JDL_LPMANCHORPASSNAME=apass4
export ALIEN_JDL_MCANCHOR=apass4
export ALIEN_JDL_COLLISIONSYSTEM=pp
export ALIEN_JDL_CPULIMIT=8
export ALIEN_JDL_LPMPASSNAME=apass4
export ALIEN_JDL_LPMRUNNUMBER=535084
export ALIEN_JDL_LPMPRODUCTIONTYPE=MC
export ALIEN_JDL_LPMINTERACTIONTYPE=PbPb
export ALIEN_JDL_LPMPRODUCTIONTAG=MyPass2Test
export ALIEN_JDL_LPMANCHORRUN=535084
export ALIEN_JDL_LPMANCHORPRODUCTION=LHC23f
export ALIEN_JDL_LPMANCHORYEAR=2023

export NTIMEFRAMES=2
export NSIGEVENTS=100
export NBKGEVENTS=1
export SPLITID=20
export PRODSPLIT=100
export CYCLE=30
export ALIEN_PROC_ID=2963436952


#export ALIEN_JDL_ANCHOR_SIM_OPTIONS="-gen external -ini ${PWD}/GenGraniitti.ini --embedding -nb ${NBKGEVENTS} -colBkg PbPb -genBkg pythia8 -procBkg heavy_ion"

${O2DPG_ROOT}/MC/config/PWGUD/ini/makeGraniittiConfig.py --process kConRes_pipi --eCM 13600 --nEvents 300 --rapidity cent_eta
export ALIEN_JDL_ANCHOR_SIM_OPTIONS="-gen external -ini ${PWD}/GenGraniitti.ini"

${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh
