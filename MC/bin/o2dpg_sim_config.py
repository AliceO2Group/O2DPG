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

    # FIT digitizer settings for 2023 PbPb
    if 543437 <= int(args.run) and int(args.run) <= 545367:
        add(config, {"FT0DigParam.mMip_in_V": "7", "FT0DigParam.mMV_2_Nchannels": "2", "FT0DigParam.mMV_2_NchannelsInverse": "0.5"})
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
