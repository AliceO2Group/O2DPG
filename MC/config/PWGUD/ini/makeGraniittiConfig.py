#! /usr/bin/env python3

### @author: Paul Buehler
### @email: paul.buhler@cern.ch

import argparse
import os
import subprocess

def createJson(args):
  templateFile = os.getenv("O2DPG_ROOT")+"/MC/config/PWGUD/templates/ALICE_Graniitti.temp"
  jsonFile = "ALICE_Graniitti.json"
  processes = {
    "kCon_pipi" : {
      "OUTPUT" : "ALICE_Con_pipi",
      "ENERGY" : 13600,
      "PROCESS" : "PP[RES+CON]<C> -> pi+ pi-",
      "RES" : ""
    },
    "kConRes_pipi" : {
      "OUTPUT" : "ALICE_Con_pipi",
      "ENERGY" : 13600,
      "PROCESS" : "PP[RES+CON]<C> -> pi+ pi-",
      "RES" : '["f0_500", "rho_770", "f0_980", "phi_1020", "f2_1270", "f0_1500", "f2_1525", "f0_1710", "f2_2150"]'
    },
    "kCon_KK" : {
      "OUTPUT" : "ALICE_Con_pipi",
      "ENERGY" : 13600,
      "PROCESS" : "PP[RES+CON]<C> -> pi+ pi-",
      "RES" : ""
    },
    "kConRes_KK" : {
      "OUTPUT" : "ALICE_Con_pipi",
      "ENERGY" : 13600,
      "PROCESS" : "PP[RES+CON]<C> -> pi+ pi-",
      "RES" : '["f0_500", "rho_770", "f0_980", "phi_1020", "f2_1270", "f0_1500", "f2_1525", "f0_1710", "f2_2150"]'
    }
  }

  # is process defined?
  if not args.process in processes.keys():
    print("FATAL ERROR: ")
    print("  Process ", args.process)
    print("  is not defined!")
    exit()
  procdefs = processes[args.process]

  # copy templateFile to jsonFile
  cmd = "cp "+templateFile+" "+jsonFile
  if subprocess.call(cmd, shell=True) > 0:
    print("FATAL ERROR: ")
    print("  ", templateFile)
    print("  can not be copied to")
    print("  ", jsonFile)
    exit()
    
  # update jsonFile
  stat = 0
  # OUTPUT
  nl = '    "OUTPUT"     : "' + procdefs["OUTPUT"] + '",'
  cmd = "sed -i '/\"OUTPUT\"/c\\" + nl + "' " + jsonFile
  stat = stat + subprocess.call(cmd, shell=True)
  # NEVENTS
  nl = '    "NEVENTS"    : ' + args.nEvents + ','
  cmd = "sed -i '/\"NEVENTS\"/c\\" + nl + "' " + jsonFile
  stat = stat + subprocess.call(cmd, shell=True)
  # ENERGY
  beamEne = str(int(args.eCM)/2)
  nl = '    "ENERGY"  : [' + beamEne + ', ' + beamEne + '],'
  cmd = "sed -i '/\"ENERGY\"/c\\" + nl + "' " + jsonFile
  stat = stat + subprocess.call(cmd, shell=True)
  # PROCESS
  nl = '    "PROCESS" : "' + procdefs["PROCESS"] + '",'
  cmd = "sed -i '/\"PROCESS\"/c\\" + nl + "' " + jsonFile
  stat = stat + subprocess.call(cmd, shell=True)
  # RES
  if procdefs["RES"] == "":
    nl = '    "RES"     : [],'
  else:
    nl = '    "RES"     : ' + procdefs["RES"] + ','
  cmd = "sed -i '/\"RES\"/c\\" + nl + "' " + jsonFile
  stat = stat + subprocess.call(cmd, shell=True)
  
  return jsonFile
  
# main
  
parser = argparse.ArgumentParser(description='Make Graniitti configuration',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('--process',default=None, choices=['kCon_pipi', 'kConRes_pipi', 'kCon_KK', 'kConRes_KK'],
                    help='Process to switch on')
                    
parser.add_argument('--nEvents', default='100',
                    help='Number of events to generate per TF')

parser.add_argument('--eCM', type=float, default='13600',
                    help='Centre-of-mass energy')

parser.add_argument('--rapidity', default='cent', choices=['cent_eta', 'muon_eta'],
                    help='Rapidity to select')

parser.add_argument('--output', default='GenGraniitti.ini',
                    help='Where to write the configuration')

args = parser.parse_args()

### prepare the json configuration file for graniitti
jsonFile = createJson(args)

### open output file
fout = open(args.output, 'w')

### Generator
fout.write('[GeneratorExternal] \n')
fout.write('fileName = ${O2DPG_ROOT}/MC/config/PWGUD/external/generator/GeneratorGraniitti.C \n')
fout.write('funcName = GeneratorGraniitti("%s")  \n' % ("../"+jsonFile))
    
###Trigger
fout.write('[TriggerExternal] \n')
fout.write('fileName = ${O2DPG_ROOT}/MC/config/PWGUD/trigger/selectParticlesInAcceptance.C \n')
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
