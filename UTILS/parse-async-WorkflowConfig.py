#!/usr/bin/env python3

# A script helping to parse configuration
# from a reco workflow, in order to apply the same settings
# in MC. Spits out a json with the configuration.

# things to parse
# - detector list
# - components of reco workflow
# - vertexing sources etc
# - config - key params ; per job
# - we can produce a json or a dict

import re
import json
import os

def get_topology_cmd(filename):
   """
   returns the command for the topology; from a workflow filename
   """
   f = open(filename, 'r')
   lines = f.readlines()
   output = []
   for l in lines:
     if l.count('--session') and l.count("o2-") > 0:
        output.append(l)
   return output


def extract_detector_list():
   """
   extracts list of sensitive detectors used
   """

def extract_config_key_values(tokenlist):
   kvconfig = {}
   for i,t in enumerate(tokenlist):
     if t == '--configKeyValues':
         configs = tokenlist[i+1]
         # individual key-values:
         if configs[0]=='"':
           configs = configs[1:]
         if configs[-1] == '"':
           configs = configs[:-1]
         keyvals = configs.split(";")
         for kv in keyvals:
            tmp = kv.rstrip().split("=")
            if len(tmp) > 1:
              key = tmp[0]
              value = tmp[1]
              kvconfig[key]=value
   return kvconfig

def extract_args(tokens, arg):
   """
   extract the value for a given argument from a list of argument tokens
   """
   i = 0
   while i < len(tokens):
       t = tokens[i]
       if t == arg:
          return tokens[i+1] if i+1 < len(tokens) else ""
       i += 1
   return ""

def remove_tokens(tokens, argument, stride=1):
   # take out arguments; that we definitely do not want to take over
   outtokens = []
   i = 0
   while i < len(tokens):
       t = tokens[i]
       if t == argument:
          i += stride
          continue
       outtokens.append(t)
       i += 1
   return outtokens


def flatten_config_values(commandlist):
   """
   let's see if we have any duplicates or contradicting things
   and if we can produce a flat dictionary of config values
   """
   main_sub_config = {}
   for task in commandlist:
      thisconfig = task.get('configval')
      if thisconfig:
         for compoundkey in thisconfig:
            mainkey = compoundkey.split(".")[0]
            subkey = compoundkey.split(".")[1]
            if main_sub_config.get(mainkey) == None:
               main_sub_config[mainkey] = {}
            preventry = main_sub_config[mainkey].get(subkey)
            value = thisconfig[compoundkey]
            if preventry and preventry != value:
                  print("Found inconsistent duplicate key .. cannot simply flatten")
            else:
               main_sub_config[mainkey][subkey] = value
   return main_sub_config

# write INI files gives config values
def configValues_to_ini(flatconfig):
   """
   supposedly, there is an INI conversion but not sure where
   ... so we fake it here
   """
   # write ini
   f = open("ini-file","w")
   for mainkey in flatconfig:
      f.write("["+mainkey+"]\n")
      for subkey in flatconfig[mainkey]:
         f.write(subkey+"="+flatconfig[mainkey][subkey]+"\n")

def configValues_to_json(flatconfig):
   """
   """
   with open('config-json.json', 'w') as outfile:
        json.dump(flat_config, outfile, indent=2)


def parse_important_DPL_args(cmds, flat_config):
   """
   Here we parse important other options that are not part of config-params such --vertexing-sources and --vertex-track-matching sources for various reco tasks.
   Unfortunately, we cannot just blindly take everything as some of these things are
   specific to reco, so we need to maintain a list.

   The options are attached to same config as for configurable params ... under
   specific keys which can be queried during MC workflow creation.

   So this reads cmds dictionary and modifies flat_config dictionary.
   """

   for tasks in cmds:
      # we just to it by specific tasks until we have a better way
      cmd = tasks['cmd']
      tokens = tasks['remainingargs']
      # primary vertex finder -- here we need "vertexing sources and vertex-track-matching-sources"
      if cmd == 'o2-primary-vertexing-workflow':
         c = {}
         c['vertexing-sources'] = extract_args(tokens, '--vertexing-sources')
         c['vertex-track-matching-sources'] = extract_args(tokens, '--vertex-track-matching-sources')
         flat_config[cmd + '-options'] = c

      # secondary vertex finder
      if cmd == 'o2-secondary-vertexing-workflow':
         c = {}
         c['vertexing-sources'] = extract_args(tokens, '--vertexing-sources')
         flat_config[cmd + '-options'] = c

      # aod
      if cmd == 'o2-aod-producer-workflow':
         c = {}
         c['info-sources'] = extract_args(tokens, '--info-sources')
         flat_config[cmd + '-options'] = c

      # its reco
      if cmd == 'o2-its-reco-workflow':
         pass

      # trd tracking
      if cmd == 'o2-trd-global-tracking':
         c = {}
         c['track-sources'] = extract_args(tokens, '--track-sources')
         flat_config[cmd + '-options'] = c

      # tof matching
      if cmd == 'o2-tof-matcher-workflow':
         c = {}
         c['track-sources'] = extract_args(tokens, '--track-sources')
         flat_config[cmd + '-options'] = c

      # ctf reader workflow (with this we can constrain
      # sensitive detectors and reduce the overal graph workflow)
      if cmd == 'o2-ctf-reader-workflow':
         c = {}
         c['onlyDet'] = extract_args(tokens, '--onlyDet')
         flat_config[cmd + '-options'] = c

      # gpu/tpc tracking
      if cmd == 'o2-gpu-reco-workflow':
         c = {}
         c['gpu-reconstruction'] = extract_args(tokens, '--gpu-reconstruction')
         flat_config[cmd + '-options'] = c

      # itstpc matching
      if cmd == 'o2-tpcits-match-workflow':
         corrstring = ''
         s1 = extract_args(tokens, '--lumi-type')
         if s1:
            corrstring += ' --lumi-type ' + s1
         s2 = extract_args(tokens, '--corrmap-lumi-mode')
         if s2:
            corrstring += ' --corrma-lumi-mode ' + s2
         # these are some options applied in multiple places (so save them flatly under tpc-corr-scaling)
         flat_config['tpc-corr-scaling'] = corrstring

def print_untreated_args(cmds):
   """
   let's see the content in remaining_args
   """
   for task in cmds:
      rargs = task.get("remainingargs")
      if rargs and len(rargs) > 0:
         print (task["cmd"]," ",rargs)


def print_principalconfigkeys_pertask(cmds):
   """
   prints list of principal config keys per task
   """
   for task in cmds:
      c = task.get("configval")
      if c != None:
         keyset = set()
         for k in c:
            keyset.add(k.split(".")[0])
         print (task["cmd"]," ",keyset)


def split_string_with_quotes(string):
    # function to split a string into tokens on whitespace but only
    # if whitespace not within quoted section
    pattern = r'\s+(?=(?:[^\'"]*[\'"][^\'"]*[\'"])*[^\'"]*$)'
    # Split the string using the pattern
    tokens = re.split(pattern, string)
    return tokens

def extract_commands(commandlist):
   commands = []
   for l in commandlist:
       task = {}
       # each l is a standalone command piped together
       l.rstrip('\n')
       l.rstrip()
       l.rstrip('|')
       tokens = split_string_with_quotes(l)
       # take out stuff we don't care about
       tokens = remove_tokens(tokens,'', 1)
       tokens = remove_tokens(tokens,'\n', 1)
       tokens = remove_tokens(tokens,'|', 1)
       tokens = remove_tokens(tokens,'\\\n', 1)
       tokens = remove_tokens(tokens,"--session", 2)
       tokens = remove_tokens(tokens,"--severity", 2)
       tokens = remove_tokens(tokens,"--shm-segment-id", 2)
       tokens = remove_tokens(tokens,"--shm-segment-size", 2)
       tokens = remove_tokens(tokens,"--resources-monitoring", 2)
       tokens = remove_tokens(tokens,"--resources-monitoring-dump-interval", 2)
       tokens = remove_tokens(tokens,"--delay", 2)
       tokens = remove_tokens(tokens,"--loop", 2)
       tokens = remove_tokens(tokens,"--early-forward-policy", 2)
       tokens = remove_tokens(tokens,"--fairmq-rate-logging", 2)
       tokens = remove_tokens(tokens,"--pipeline", 2)
       tokens = remove_tokens(tokens,"--disable-mc", 1)
       tokens = remove_tokens(tokens,"--disable-root-input", 1)

       cmd = tokens[0]
       tokens = tokens[1:len(tokens)]
       task['cmd'] = cmd
       # we look out for a list of special settings

       # config-params
       task['configval'] = extract_config_key_values(tokens)
       tokens = remove_tokens(tokens,"--configKeyValues", 2)

       # we store the remaining options for further processing later
       task['remainingargs'] = tokens
       commands.append(task)

   return commands

# some manual intervention (could and should be done from outside)
def postadjust_ConfigValues(flat_config):
  gpuglobal = flat_config.get("GPU_global")
  # fix location of root files for TPC
  d=os.getcwd()
  for key in gpuglobal:
      if gpuglobal[key].count(".root") > 0:
         gpuglobal[key] = d + "/" + gpuglobal[key]


def extract_readout_detectors(path, flat_config):
   """
   Get list of readout detectors

   Expect the input file to contain exactly one line with readout detectors split by whitespaces

   Returns a string of the form DET1,DET2,DET3,...,DETN
   """
   with open(path) as f:
      for line in f:
         line = line.strip().split()
         detectors = ",".join([d.strip() for d in line])
         flat_config["readout_detectors"] = detectors
         break


cmdlist = get_topology_cmd("workflowconfig.log")
#print (cmdlist)
cmds = extract_commands(cmdlist)
# print_untreated_args(cmds)
print_principalconfigkeys_pertask(cmds)
flat_config = flatten_config_values(cmds)
#print (flat_config)
postadjust_ConfigValues(flat_config)
parse_important_DPL_args(cmds, flat_config)
extract_readout_detectors("DetList.txt", flat_config)
configValues_to_json(flat_config)
