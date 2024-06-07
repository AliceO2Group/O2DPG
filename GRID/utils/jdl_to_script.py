#!/usr/bin/env python3

# Produces a local shell script that emulates the execution of a JDL on the GRID.
# This can be useful for local debugging of failing GRID jobs.

# started 01.12.2022; Sandro Wenzel

import argparse
import os, stat
import subprocess

parser = argparse.ArgumentParser(description='Produce local shell script from an ALIEN JDL')

# the run-number of data taking or default if unanchored
parser.add_argument('--jdl', type=str, help="A local JDL file")
parser.add_argument('--from-proc-id', type=str, help="Scrap the JDL directly from a known ALIEN PROCID")
parser.add_argument('-o', type=str, help="output filename of shell script to produce")
args = parser.parse_args()
print (args)

# converts a JDL list to a python list
def toList(token):
  if token == None or len(token)==0:
    return token
  if token[0]=='{' and token[-1]=='}':
    inner=token[1:-1]
    # attention, this might not work if comma inside a string
    return [l.lstrip().rstrip() for l in inner.split(",")]
  return [token]

def cleanFileName(filename):
  # remove " and 'LF:' from alien file names
  return filename.replace('LF:','').replace('"','')

def removeQuote(token):
  return token.replace('"','')

# fetches a JDL for a known PROC ID to a local file
def fetchJDL(alien_proc_id):
  print('Fetching JDL directly from ALIEN')
  # we rely on alien.py functionality
  filename="jdl_local_"+alien_proc_id+".jdl"
  cmd="alien.py ps --jdl " + alien_proc_id + " > " + filename
  proc = subprocess.Popen([cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
  out, err = proc.communicate()
  if proc.returncode == 0:
    return filename
  print('Fetching failed. Make sure to have access to jalien')
  return None

# let's start with a JDL parser
# lets tokenize the jdl and return a dictionary of keys and values
# The function assumes a syntactically correct JDL (that has been processed and expanded by Alien into the standard format; no comments; etc)
def parseJDL(jdlfile, proc_id = -1):
  parsed_dict={}
  if jdlfile==None or len(jdlfile)==0:
    return parsed_dict

  f=open(jdlfile)
  if f:
    linelist = [line.rstrip('\n') for line in f if not "LPMMetaData" in line]
    # flatten text into one line
    flatjdl="".join(linelist)
    # tokenize on ';' (unless a ; is part of a string --> which is why we take out the LPMMetaData)
    statements=flatjdl.split(";")
    for s in statements:
      if len(s) > 0:
        key, value = s.split(" = ")
        parsed_dict[key.lstrip().rstrip()]=value.lstrip().rstrip()
    
    print (parsed_dict)
    f.close()
    return parsed_dict
  
  else:
    print("File could not be opened")
    return {}


# produces a bash script that runs the jdl locally
def constructRuntimeScript(jdldict):
  script=["#!/usr/bin/env bash"]
  # we have to instanteate the right software environment
  packagelist=toList(jdldict['Packages'])
  packagestring=",".join(packagelist)
  script.append("/cvmfs/alice.cern.ch/bin/alienv printenv " + packagestring + " &> environment")
  script.append("source environment")

  # now fetch all required input files
  # a) the executable 
  script.append("alien.py cp " + cleanFileName(jdldict['Executable']) + " file:./")
  # b) any other input
  for f in toList(jdldict['InputFile']):
    script.append("alien.py cp " + cleanFileName(f) + " file:./")

  # export the original PROC if we have it
  if args.from_proc_id != None:
    script.append("export ALIEN_PROC_ID="+args.from_proc_id)

  # export everything mentioned in JDL variables
  for env in toList(jdldict['JDLVariables']):
    var=removeQuote(env).lstrip().rstrip()
    script.append("export ALIEN_JDL_" + var.upper() + "=" + jdldict[var])

  # run the script --> call executable with ARGS -- and stripped path
  revexec=removeQuote(jdldict['Executable'][::-1])
  firstslashindex=revexec.find('/')
  nopathexec=revexec[0:firstslashindex][::-1]
  script.append("chmod +x " + nopathexec)
  script.append("./" + nopathexec + " " + jdldict.get('Arguments',''))

  return script

# runs the script which is encoded in a line by line list
def convertToScript(scriptlist, outfilename):
  f=open(outfilename,'w')
  if f:
    for line in scriptlist:
      f.write(line + '\n')
    f.close()
    # mark script as executable
    os.system("chmod +x " + outfilename)
    # this is more complicated: os.chmod(outfilename, stat.S_IEXEC | stat.S)

jdlfilename=''
if args.from_proc_id!=None:
  jdlfilename=fetchJDL(args.from_proc_id)
else:
  jdlfilename=args.jdl

jdl_dict = parseJDL(jdlfilename)
print (jdl_dict)
script = constructRuntimeScript(jdl_dict)
convertToScript(script, args.o)
