#! /usr/bin/env python3

### @author: Michal Broz
### @email: michal.broz@cern.ch

import argparse

parser = argparse.ArgumentParser(description='Make Starlight configuration',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('--collType',default='PbPb', choices=['PbPb', 'pPb', 'Pbp', 'pp', 'OO', 'pO', 'Op', 'NeNe'],
                   help='Colission system')
                   
parser.add_argument('--eCM', type=float, default='5360',
                    help='Centre-of-mass energy')

parser.add_argument('--rapidity', default='cent', choices=['cent_rap', 'muon_rap', 'cent_eta', 'muon_eta'],
                    help='Rapidity to select')

parser.add_argument('--process',default=None, choices=['kTwoGammaToMuLow', 'kTwoGammaToElLow', 'kTwoGammaToMuMedium', 'kTwoGammaToElMedium', 'kTwoGammaToMuHigh', 'kTwoGammaToElHigh', 'kTwoGammaToRhoRho', 'kTwoGammaToF2', 'kCohRhoToPi', 'kCohRhoToElEl', 'kCohRhoToMuMu', 'kCohRhoToPiWithCont', 'kCohRhoToPiFlat', 'kCohPhiToKa', 'kDirectPhiToKaKa', 'kCohPhiToEl', 'kCohOmegaTo2Pi', 'kCohOmegaTo3Pi', 'kCohOmegaToPiPiPi', 'kCohRhoPrimeTo4Pi', 'kCohJpsiToMu', 'kCohJpsiToEl', 'kCohJpsiToElRad', 'kCohJpsiToProton', 'kCohJpsiToLLbar', 'kCohJpsi4Prong', 'kCohJpsi6Prong',  'kCohPsi2sToMu','kCohPsi2sToEl', 'kCohPsi2sToMuPi', 'kCohPsi2sToElPi', 'kCohUpsilonToMu', 'kCohUpsilonToEl', 'kIncohRhoToPi', 'kIncohRhoToElEl', 'kIncohRhoToMuMu', 'kIncohRhoToPiWithCont', 'kIncohRhoToPiFlat', 'kIncohPhiToKa', 'kIncohOmegaTo2Pi', 'kIncohOmegaTo3Pi', 'kIncohOmegaToPiPiPi', 'kIncohRhoPrimeTo4Pi', 'kIncohJpsiToMu', 'kIncohJpsiToEl', 'kIncohJpsiToElRad', 'kIncohJpsiToProton', 'kIncohJpsiToLLbar', 'kIncohPsi2sToMu', 'kIncohPsi2sToEl', 'kIncohPsi2sToMuPi', 'kIncohPsi2sToElPi', 'kIncohUpsilonToMu', 'kIncohUpsilonToEl', 'kDpmjetSingleA', 'kDpmjetSingleA_Dzero', 'kDpmjetSingleA_Dcharged', 'kDpmjetSingleA_Dstar', 'kDpmjetSingleA_Phi', 'kDpmjetSingleA_Kstar', 'kDpmjetSingleC', 'kDpmjetSingleC_Dzero', 'kDpmjetSingleC_Dcharged', 'kDpmjetSingleC_Dstar', 'kDpmjetSingleC_Phi', 'kDpmjetSingleC_Kstar', 'kTauLowToEl3Pi', 'kTauLowToPo3Pi', 'kTauMediumToEl3Pi', 'kTauMediumToPo3Pi', 'kTauHighToEl3Pi', 'kTauHighToPo3Pi', 'kTauLowToElMu', 'kTauLowToElPiPi0', 'kTauLowToPoPiPi0'],
                    help='Process to switch on')
                    
                    
parser.add_argument('--output', default='GenStarlight.ini',
                    help='Where to write the configuration')

parser.add_argument('--extraPars', default='',
                    help='Extra parameters for SL config')

parser.add_argument('--dpmjetConf', default='',
                    help='DPMJET config file')

parser.add_argument('--nOOn', action='store_true',
                    help="Enable the neutron production with nOOn")


args = parser.parse_args()

if args.nOOn:
    args.extraPars = 'BREAKUP_MODE = 4'

if 'PbPb' in args.collType:
    pZ = 82
    pA = 208
    tZ = 82
    tA = 208
if 'pPb' in args.collType:
    pZ = 1
    pA = 1
    tZ = 82
    tA = 208
if 'Pbp' in args.collType:
    pZ = 82
    pA = 208
    tZ = 1
    tA = 1
if 'pp' in args.collType:
    pZ = 1
    pA = 1
    tZ = 1
    tA = 1
if 'OO' in args.collType:
    pZ = 8
    pA = 16
    tZ = 8
    tA = 16    
if 'pO' in args.collType:
    pZ = 1
    pA = 1
    tZ = 8
    tA = 16 
if 'Op' in args.collType:
    pZ = 8
    pA = 16
    tZ = 1
    tA = 1 
if 'NeNe' in args.collType:
    pZ = 10
    pA = 20
    tZ = 10
    tA = 20

### open output file
fout = open(args.output, 'w')

### Generator
fout.write('[GeneratorExternal] \n')
if args.nOOn:
    fout.write('fileName = ${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGUD/external/generator/Generator_nOOn.C \n')
    fout.write('funcName = Generator_nOOn("%s", %f, %d, %d, %d, %d, "%s")  \n' % (args.process,args.eCM ,pZ,pA,tZ,tA,args.extraPars))
else:
    if  'Psi2sToMuPi' in args.process or 'Psi2sToElPi' in args.process or 'OmegaTo3Pi' in args.process or 'JpsiToElRad' in args.process or 'Jpsi4Prong' in args.process or 'Jpsi6Prong' in args.process or 'kTau' in args.process or 'Dpmjet' in args.process:
        fout.write('fileName = ${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGUD/external/generator/GeneratorStarlightToEvtGen.C \n')
        fout.write('funcName = GeneratorStarlightToEvtGen("%s", %f, %d, %d, %d, %d, "%s", "%s")  \n' % (args.process.split('_')[0],args.eCM ,pZ,pA,tZ,tA,args.extraPars,args.dpmjetConf))
    else:
        fout.write('fileName = ${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGUD/external/generator/GeneratorStarlight.C \n')
        fout.write('funcName = GeneratorStarlight("%s", %f, %d, %d, %d, %d, "%s", "%s")  \n' % (args.process.split('_')[0],args.eCM ,pZ,pA,tZ,tA,args.extraPars,args.dpmjetConf))
    
###Trigger
if not 'kDpmjet' in args.process:
    fout.write('[TriggerExternal] \n')
    fout.write('fileName = ${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGUD/trigger/selectParticlesInAcceptance.C \n')
    if 'kTwoGamma' in args.process or 'kTau' in args.process:
        if args.rapidity == 'cent_eta':
            fout.write('funcName = selectDirectPartInAcc(-0.9,0.9) \n')
        if args.rapidity == 'muon_eta':
            fout.write('funcName = selectDirectPartInAcc(-4.0,-2.5) \n')
    else:
        if args.rapidity == 'cent_rap':
            fout.write('funcName = selectMotherPartInAcc(-0.9,0.9) \n')
        if args.rapidity == 'muon_rap':
            fout.write('funcName = selectMotherPartInAcc(-4.0,-2.5) \n')
        if args.rapidity == 'cent_eta':
            fout.write('funcName = selectDaughterPartInAcc(-0.9,0.9) \n')
        if args.rapidity == 'muon_eta':
            fout.write('funcName = selectDaughterPartInAcc(-4.0,-2.5) \n')
elif '_' in args.process:
    fout.write('[TriggerExternal] \n')
    fout.write('fileName = ${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGUD/trigger/triggerDpmjetParticle.C \n')
    if 'Dzero' in args.process:
        fout.write('funcName = triggerDzero(-0.9,0.9) \n')
    if 'Dcharged' in args.process:
        fout.write('funcName = triggerDcharged(-0.9,0.9) \n')
    if 'Dstar' in args.process:
        fout.write('funcName = triggerDstar(-0.9,0.9) \n')
    if 'Phi' in args.process:
        fout.write('funcName = triggerPhi(-0.9,0.9) \n')
    if 'Kstar' in args.process:
        fout.write('funcName = triggerKstar(-0.9,0.9) \n')

### close outout file
fout.close()
