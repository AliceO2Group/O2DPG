# Run as:  ${O2DPG_ROOT}/GRID/utils/grid_submit.sh --script ./runUpcgenANCHOR.sh --jobname SLtest --outputspec "*.log@disk=1","*.root@disk=2" --packagespec "VO_ALICE@O2sim::v20240626-1" --wait --fetch-output --asuser pbuhler --local

export ALIEN_JDL_LPMANCHORPASSNAME=apass2
export ALIEN_JDL_MCANCHOR=apass2
export ALIEN_JDL_COLLISIONSYSTEM=PbPb
export ALIEN_JDL_CPULIMIT=8
export ALIEN_JDL_LPMPASSNAME=apass2
export ALIEN_JDL_LPMRUNNUMBER=544389
export ALIEN_JDL_LPMPRODUCTIONTYPE=MC
export ALIEN_JDL_LPMINTERACTIONTYPE=PbPb
export ALIEN_JDL_LPMPRODUCTIONTAG=MyPass2Test
export ALIEN_JDL_LPMANCHORRUN=544389
export ALIEN_JDL_LPMANCHORPRODUCTION=LHC23zzi
export ALIEN_JDL_LPMANCHORYEAR=2023

export NTIMEFRAMES=2
export NSIGEVENTS=5
export NBKGEVENTS=1
export SPLITID=2
export PRODSPLIT=100
export CYCLE=0
export ALIEN_PROC_ID=2963436952


#export ALIEN_JDL_ANCHOR_SIM_OPTIONS="-gen external -ini ${PWD}/GenUpcgen.ini --embedding -nb ${NBKGEVENTS} -colBkg PbPb -genBkg pythia8 -procBkg heavy_ion"

${O2DPG_ROOT}/MC/config/PWGUD/ini/makeUpcgenConfig.py --process kDiTau --collType PbPb --eCM 5360 --rapidity cent_eta
export ALIEN_JDL_ANCHOR_SIM_OPTIONS="-gen external -ini ${PWD}/GenUpcgen.ini"

${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC.sh
