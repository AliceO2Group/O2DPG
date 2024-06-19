#! /usr/bin/env python3

### @author: Michal Broz
### @email: michal.broz@cern.ch

import argparse

parser = argparse.ArgumentParser(description='Make Starlight configuration',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('--pZ', type=int, default='82',
                   help='Projectile charge')
                   
parser.add_argument('--pA', type=int, default='208',
                   help='Projectile atomic number')                

parser.add_argument('--tZ', type=int, default='82',
                   help='Target charge')
                   
parser.add_argument('--tA', type=int, default='208',
                   help='Target atomic number') 

parser.add_argument('--eCM', type=float, default='5360',
                    help='Centre-of-mass energy')

parser.add_argument('--rapidity', default='cent', choices=['cent', 'muon'],
                    help='Rapidity to select')

parser.add_argument('--process',default=None, choices=['kTwoGammaToMuLow', 'kTwoGammaToElLow', 'kTwoGammaToMuMedium', 'kTwoGammaToElMedium', 'kTwoGammaToMuHigh', 'kTwoGammaToElHigh', 'kTwoGammaToRhoRho', 'kTwoGammaToF2', 'kCohRhoToPi', 'kCohRhoToElEl', 'kCohRhoToMuMu', 'kCohRhoToPiWithCont', 'kCohRhoToPiFlat', 'kCohPhiToKa', 'kDirectPhiToKaKa','kCohOmegaTo2Pi', 'kCohOmegaTo3Pi', 'kCohOmegaToPiPiPi', 'kCohJpsiToMu', 'kCohJpsiToEl', 'kCohJpsiToElRad', 'kCohJpsiToProton', 'kCohPsi2sToMu','kCohPsi2sToEl', 'kCohPsi2sToMuPi', 'kCohPsi2sToElPi', 'kCohUpsilonToMu', 'kCohUpsilonToEl', 'kIncohRhoToPi', 'kIncohRhoToElEl', 'kIncohRhoToMuMu', 'kIncohRhoToPiWithCont', 'kIncohRhoToPiFlat', 'kIncohPhiToKa', 'kIncohOmegaTo2Pi', 'kIncohOmegaTo3Pi', 'kIncohOmegaToPiPiPi', 'kIncohJpsiToMu', 'kIncohJpsiToEl', 'kIncohJpsiToElRad', 'kIncohJpsiToProton', 'kIncohJpsiToLLbar', 'kIncohPsi2sToMu', 'kIncohPsi2sToEl', 'kIncohPsi2sToMuPi', 'kIncohPsi2sToElPi', 'kIncohUpsilonToMu', 'kIncohUpsilonToEl'],
                    help='Process to switch on')
                    
                    
parser.add_argument('--output', default='GenStarlight.ini',
                    help='Where to write the configuration')


args = parser.parse_args()

### open output file
fout = open(args.output, 'w')

### Generator
fout.write('[GeneratorExternal] \n')
if  'Psi2sToMuPi' in args.process or 'Psi2sToElPi' in args.process or 'RhoPrime' in args.process or 'OmegaTo3Pi' in args.process or 'JpsiToElRad' in args.process :
    fout.write('fileName = ${O2DPG_ROOT}/MC/config/PWGUD/external/generator/GeneratorStarlightToEvtGen.C \n')
    fout.write('funcName = GeneratorStarlightToEvtGen("%s", %f, %d, %d, %d, %d)  \n' % (args.process,args.eCM ,args.pZ ,args.pA,args.tZ,args.tA))
else:
    fout.write('fileName = ${O2DPG_ROOT}/MC/config/PWGUD/external/generator/GeneratorStarlight.C \n')
    fout.write('funcName = GeneratorStarlight("%s", %f, %d, %d, %d, %d)  \n' % (args.process,args.eCM ,args.pZ ,args.pA,args.tZ,args.tA))
    
###Trigger
fout.write('[TriggerExternal] \n')
fout.write('fileName = ${O2DPG_ROOT}/MC/config/PWGUD/trigger/selectParticlesInAcceptance.C \n')
if args.rapidity == 'cent':
    fout.write('funcName = selectMotherPartInAcc(-0.9,0.9) \n')
if args.rapidity == 'muon':
    fout.write('funcName = selectMotherPartInAcc(-4.0,-2.5) \n')

### close outout file
fout.close()
