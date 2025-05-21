from functools import lru_cache
import subprocess
import re
import os

def create_sim_config(args):
    # creates a generic simulation config
    # based on arguments args (run number, energy, ...) originally passed
    # to o2dpg_sim_workflow.py

    COLTYPEIR = args.col
    if args.embedding==True:
        COLTYPEIR = args.colBkg

    config = {}
    def add(cfg, flatconfig):
       for entry in flatconfig:
           mk = entry.split(".")[0]
           sk = entry.split(".")[1]
           d = cfg.get(mk,{})
           d[sk] = flatconfig[entry]
           cfg[mk] = d

    # some specific settings for pp productions
    if COLTYPEIR == 'pp':
       # Alpide chip settings
       add(config, {"MFTAlpideParam.roFrameLengthInBC" : 198})
       if 302000 <= int(args.run) and int(args.run) < 309999:
           add(config, {"ITSAlpideParam.roFrameLengthInBC" : 198})
       # ITS reco settings
       add(config, {"ITSVertexerParam.phiCut" : 0.5,
                    "ITSVertexerParam.clusterContributorsCut" : 3,
                    "ITSVertexerParam.tanLambdaCut" : 0.2})
       # primary vertexing settings
       if 301000 <= int(args.run) and int(args.run) <= 301999:
          add(config, {"pvertexer.acceptableScale2" : 9,
                       "pvertexer.minScale2" : 2.,
                       "pvertexer.nSigmaTimeTrack" : 4.,
                       "pvertexer.timeMarginTrackTime" : 0.5,
                       "pvertexer.timeMarginVertexTime" : 7.,
                       "pvertexer.nSigmaTimeCut" : 10,
                       "pvertexer.dbscanMaxDist2" : 36,
                       "pvertexer.dcaTolerance" : 3.,
                       "pvertexer.pullIniCut" : 100,
                       "pvertexer.addZSigma2" : 0.1,
                       "pvertexer.tukey" : 20.,
                       "pvertexer.addZSigma2Debris" : 0.01,
                       "pvertexer.addTimeSigma2Debris" : 1.,
                       "pvertexer.maxChi2Mean" : 30,
                       "pvertexer.timeMarginReattach" : 3.,
                       "pvertexer.addTimeSigma2Debris" : 1.,
                       "pvertexer.dbscanDeltaT" : 24,
                       "pvertexer.maxChi2TZDebris" : 100,
                       "pvertexer.maxMultRatDebris" : 1.,
                       "pvertexer.dbscanAdaptCoef" : 20.})
       elif 302000 <= int(args.run) and int(args.run) <= 309999:
          # specific tunes for high pp
          # run range taken from https://twiki.cern.ch/twiki/bin/viewauth/ALICE/O2DPGMCSamplingSchema
          # taken from JIRA https://alice.its.cern.ch/jira/browse/O2-2691
          # remove extra errors on time margin for tracks and ITS clusters
          add(config, {"pvertexer.timeMarginTrackTime" : 0.,
                       "pvertexer.dbscanDeltaT" : 7,
                       "pvertexer.maxChi2TZDebris": 50,
                       "pvertexer.maxMultRatDebris": 1.,
                       "pvertexer.dbscanAdaptCoef" : 20,
                       "pvertexer.maxVerticesPerCluster" : 20,
                       "pvertexer.dbscanMaxDist2" : 36})
       else:
          # generic pp
          # remove extra errors on time margin for tracks and ITS clusters
          add(config, {"pvertexer.acceptableScale2" : 9,
                       "pvertexer.dbscanMaxDist2" : 36,
                       "pvertexer.dbscanDeltaT" : 24,
                       "pvertexer.maxChi2TZDebris" : 100,
                       "pvertexer.maxMultRatDebris" : 1.,
                       "pvertexer.dbscanAdaptCoef" : 20.})

    # MFT tracking settings
    if args.mft_reco_full == True:
        add(config, {"MFTTracking.forceZeroField" : 0,
                     "MFTTracking.LTFclsRCut" : 0.0100})

    # Forward matching settings
    if args.fwdmatching_4_param == True:
        add(config, {"FwdMatching.matchFcn" : "matchsXYPhiTanl"})
    if args.fwdmatching_cut_4_param == True:
        add(config, {"FwdMatching.cutFcn" : "cut3SigmaXYAngles"})

    # deal with larger combinatorics
    if args.col == "PbPb" or (args.embedding and args.colBkg == "PbPb"):
        add(config, {"ITSVertexerParam.lowMultBeamDistCut": "0."})

    # FIT digitizer settings
    # 2023 PbPb
    if 543437 <= int(args.run) and int(args.run) <= 545367:
        add(config, {"FT0DigParam.mMip_in_V": "7", "FT0DigParam.mMV_2_Nchannels": "2", "FT0DigParam.mMV_2_NchannelsInverse": "0.5"})
        add(config, {"FV0DigParam.adcChannelsPerMip": "4"})
    # 2024
    # first and last run of 2024
    if 546088 <= int(args.run) and int(args.run) <= 560623:
        # 14 ADC channels / MIP for FT0
        add(config, {"FT0DigParam.mMip_in_V": "7", "FT0DigParam.mMV_2_Nchannels": "2", "FT0DigParam.mMV_2_NchannelsInverse": "0.5"})
        # 15 ADC channels / MIP for FV0
        add(config, {"FV0DigParam.adcChannelsPerMip": "15"})
        if COLTYPEIR == "PbPb":
            # 4 ADC channels / MIP
            add(config, {"FV0DigParam.adcChannelsPerMip": "4"})

    return config


def create_geant_config(args, externalConfigString):
    # creates generic transport simulation config key values
    # based on arguments args (run number, energy, ...) originally passed
    # to o2dpg_sim_workflow.py
    #
    # returns a dictionary of mainkey -> dictionary of subkey : values
    config = {}
    def add(cfg, flatconfig):
       for entry in flatconfig:
           mk = entry.split(".")[0]
           sk = entry.split(".")[1]
           d = cfg.get(mk,{})
           d[sk] = flatconfig[entry]
           cfg[mk] = d

    # ----- special setting for hepmc generator -----
    if args.gen == "hepmc":
      eventSkipPresent = config.get("HepMC",{}).get("eventsToSkip")
      if eventSkipPresent == None:
          # add it
          add(config, {"HepMC.eventsToSkip" : '${HEPMCEVENTSKIP:-0}'})

    # ----- add default settings -----

    add(config, {"MFTBase.buildAlignment" : "true"})

    # ----- apply external overwrites from command line -------
    for keyval in externalConfigString.split(";"):
        if len(keyval) > 0:
          key, val = keyval.split("=")
          add(config, {key : val})

    return config

def constructConfigKeyArg(config):
    # flattens dictionary constructed in create_geant_config
    # and constructs the --configKeyValues options for simulation
    if len(config) == 0:
        return ''
    arg = '--configKeyValues "'
    for mainkey in config:
      for subkey in config[mainkey]:
          arg = arg + mainkey + '.' + subkey + '=' + config[mainkey][subkey] + ';'
    arg = arg + '"'
    return arg

def load_env_file(env_file):
    """Transform an environment file generated with 'export > env.txt' into a python dictionary."""
    env_vars = {}
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()

            # Ignore empty lines or comments
            if not line or line.startswith("#"):
                continue

            # Remove 'declare -x ' if present
            if line.startswith("declare -x "):
                line = line.replace("declare -x ", "", 1)

            # Handle case: "FOO" without "=" (assign empty string)
            if "=" not in line:
                key, value = line.strip(), ""
            else:
                key, value = line.split("=", 1)
                value = value.strip('"')  # Remove surrounding quotes if present

            env_vars[key.strip()] = value
    return env_vars

# some functions to determine dpl option availability on the fly
def parse_dpl_help_output(executable, envfile):
    """Parses the --help full output of an executable to extract available options."""
    try:
        env = os.environ.copy()
        if envfile != None:
           print ("Loading from alternative environment")
           env = load_env_file(envfile)

        # the DEVNULL is important for o2-dpl workflows not to hang on non-interactive missing tty environments
        # it is cleaner that the echo | trick
        output = subprocess.check_output([executable, "--help", "full"], env=env, text=True, stdin=subprocess.DEVNULL, timeout = 100)
    except subprocess.CalledProcessError:
        return {}, {}
    
    option_pattern = re.compile(r"(\-\-[\w\-]+)")
    sections = {}
    inverse_lookup = {}
    current_section = "global"
    
    for line in output.split("\n"):
        section_match = re.match(r"^([A-Za-z\s]+):$", line.strip())
        if section_match:
            current_section = section_match.group(1).strip()
            sections[current_section] = []
            continue
        
        option_match = option_pattern.findall(line)
        if option_match:
            for option in option_match:
                sections.setdefault(current_section, []).append(option)
                inverse_lookup.setdefault(option, []).append(current_section)
    
    return sections, inverse_lookup

@lru_cache(maxsize=10)
def get_dpl_options_for_executable(executable, envfile):
    """Returns available options and inverse lookup for a given executable, caching the result."""
    return parse_dpl_help_output(executable, envfile)

def option_if_available(executable, option, envfile = None):
    """Checks if an option is available for a given executable and returns it as a string. Otherwise empty string"""
    _, inverse_lookup = get_dpl_options_for_executable(executable, envfile)
    return ' ' + option if option in inverse_lookup else ''


# helper function to overwrite some values; prints out stuff that it changes
def overwrite_config(config, mainkey, subkey, value):
    oldvalue = config.get(mainkey,{}).get(subkey, None)
    print (f"Overwriting {mainkey}.{subkey}: {'None' if oldvalue is None else oldvalue} -> {value}")
    if mainkey not in config:
      # Initialize the main key in the dictionary if it does not already exist
      config[mainkey] = {}
    config[mainkey][subkey] = value