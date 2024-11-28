#! /usr/bin/env python3

### @author: Paul Buehler
### @email: paul.buhler@cern.ch

import argparse

parser = argparse.ArgumentParser(description='Make Upcgen configuration',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('--collType',default='PbPb', choices=['PbPb', 'OO'],
                   help='Colission system')
                   
parser.add_argument('--eCM', type=float, default='5360',
                    help='Centre-of-mass energy')

parser.add_argument('--rapidity', default='cent', choices=['cent_eta', 'muon_eta'],
                    help='Rapidity to select')

parser.add_argument('--process',default=None, choices=['kDiElectron', 'kDiMuon', 'kDiTau', 'kLightByLight', 'kAxionLike'],
                    help='Process to switch on')
                    
                    
parser.add_argument('--output', default='GenUpcgen.ini',
                    help='Where to write the configuration')


args = parser.parse_args()

if 'PbPb' in args.collType:
    pZ = 82
    pA = 208

if 'OO' in args.collType:
    pZ = 8
    pA = 16

### open output file
fout = open(args.output, 'w')

### Generator
fout.write('[GeneratorExternal] \n')
fout.write('fileName = ${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGUD/external/generator/GeneratorUpcgen.C \n')
fout.write('funcName = GeneratorUpcgen("%s", "%s", %f, %d, %d)  \n' % (args.process,"../.",args.eCM,pZ,pA))
    
###Trigger
fout.write('[TriggerExternal] \n')
fout.write('fileName = ${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGUD/trigger/selectParticlesInAcceptance.C \n')
if args.rapidity == 'cent_rap':
    fout.write('funcName = selectMotherPartInAcc(-0.9,0.9) \n')
if args.rapidity == 'muon_rap':
    fout.write('funcName = selectMotherPartInAcc(-4.0,-2.5) \n')
if args.rapidity == 'cent_eta':
    fout.write('funcName = selectDaughterPartInAcc(-0.95,0.95) \n')
if args.rapidity == 'muon_eta':
    fout.write('funcName = selectDaughterPartInAcc(-4.05,-2.45) \n')

### close outout file
fout.close()
