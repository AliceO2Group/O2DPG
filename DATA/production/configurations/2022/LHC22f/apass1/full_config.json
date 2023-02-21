{
  "max_df_size": 100000000,
  "dataset_id": 274,
  "cpu_cores": 1,
  "workflows": [
    {
      "subwagon_id": 2272,
      "subwagon_name": "base",
      "configuration": {
        "central-event-filter-task": {
          "MultFilters": {
            "values": [
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ]
            ]
          },
          "DiffractionFilters": {
            "values": [
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ]
            ]
          },
          "cfgTimingCut": "1",
          "DqFilters": {
            "values": [
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ]
            ]
          },
          "NucleiFilters": {
            "values": [
              [
                0
              ],
              [
                0
              ],
              [
                1
              ]
            ]
          },
          "CFFilters": {
            "values": [
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ]
            ]
          },
          "StrangenessFilters": {
            "values": [
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ]
            ]
          },
          "HfFilters": {
            "values": [
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                1
              ],
              [
                0
              ],
              [
                0
              ]
            ]
          },
          "CFFiltersTwoN": {
            "values": [
              [
                1
              ],
              [
                1
              ]
            ]
          },
          "JetFilters": {
            "values": [
              [
                0
              ],
              [
                0
              ]
            ]
          }
        }
      },
      "wagon_id": 2040,
      "workflow_name": "o2-analysis-central-event-filter-task",
      "suffix": ""
    },
    {
      "subwagon_id": 17,
      "subwagon_name": "base",
      "configuration": {
        "timestamp-task": {
          "rct-path": "RCT/Info/RunInformation",
          "orbit-reset-path": "CTP/Calib/OrbitReset",
          "ccdb-url": "http://alice-ccdb.cern.ch",
          "verbose": "0",
          "isRun2MC": "0"
        }
      },
      "wagon_id": 17,
      "workflow_name": "o2-analysis-timestamp",
      "suffix": ""
    },
    {
      "subwagon_id": 371,
      "subwagon_name": "base",
      "configuration": {
        "nuclei-filter": {
          "yBeam": "0",
          "nucleiCutsPID": {
            "values": [
              [
                -3,
                3,
                -4,
                4,
                1
              ],
              [
                -3,
                3,
                -4,
                4,
                1.600000023841858
              ],
              [
                -7,
                999,
                -4,
                4,
                14000
              ]
            ]
          },
          "cfgMomentumScalingBetheBloch": {
            "values": [
              [
                1,
                1
              ],
              [
                1,
                1
              ],
              [
                1,
                1
              ]
            ]
          },
          "cfgBetheBlochParams": {
            "values": [
              [
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32
              ],
              [
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32
              ],
              [
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32,
                -1e+32
              ]
            ]
          },
          "cfgCutVertex": "10",
          "cfgCutEta": "1"
        }
      },
      "wagon_id": 322,
      "workflow_name": "o2-analysis-nuclei-filter",
      "suffix": ""
    },
    {
      "subwagon_id": 717,
      "subwagon_name": "base",
      "configuration": {
        "bc-selection-task": {
          "processRun3": "1",
          "processRun2": "0"
        },
        "event-selection-task": {
          "syst": "pp",
          "isMC": "0",
          "processRun3": "1",
          "processRun2": "0",
          "muonSelection": "0",
          "customDeltaBC": "-1"
        }
      },
      "wagon_id": 661,
      "workflow_name": "o2-analysis-event-selection",
      "suffix": ""
    },
    {
      "subwagon_id": 1050,
      "subwagon_name": "base",
      "configuration": {
        "d-q-filter-p-p-task": {
          "cfgBarrelSels": "jpsiO2MCdebugCuts2::1,jpsiO2MCdebugCuts2:pairNoCut:1",
          "cfgMuonSels": "muonLowPt::1,muonHighPt::1,muonLowPt:pairNoCut:1",
          "processDummy": "0",
          "cfgWithQA": "1",
          "processFilterPP": "1"
        },
        "d-q-barrel-track-selection": {
          "ccdb-path-tpc": "Users/i/iarsene/Calib/TPCpostCalib",
          "ccdb-no-later-than": "1675645165122",
          "processSelection": "1",
          "cfgBarrelTrackCuts": "jpsiO2MCdebugCuts2,jpsiO2MCdebugCuts2",
          "ccdb-url": "http://alice-ccdb.cern.ch",
          "processDummy": "0",
          "cfgWithQA": "0",
          "cfgTPCpostCalib": "0"
        },
        "d-q-muons-selection": {
          "cfgMuonsCuts": "muonLowPt,muonHighPt,muonLowPt",
          "processSelection": "1",
          "processDummy": "0",
          "cfgWithQA": "0"
        },
        "d-q-event-selection-task": {
          "processEventSelection": "1",
          "processDummy": "0",
          "cfgWithQA": "0",
          "cfgEventCuts": ""
        }
      },
      "wagon_id": 920,
      "workflow_name": "o2-analysis-dq-filter-pp",
      "suffix": ""
    },
    {
      "subwagon_id": 1172,
      "subwagon_name": "base",
      "configuration": {
        "tof-pid-full": {
          "param-file": "",
          "param-sigma": "TOFResoParams",
          "enableTimeDependentResponse": "0",
          "processWSlice": "1",
          "processWoSlice": "0",
          "pid-he": "-1",
          "pid-ka": "-1",
          "ccdbPath": "Analysis/PID/TOF",
          "pid-pi": "-1",
          "pid-pr": "-1",
          "ccdb-timestamp": "-1",
          "pid-tr": "-1",
          "processWoSliceDev": "0",
          "pid-de": "-1",
          "pid-al": "-1",
          "ccdb-url": "http://alice-ccdb.cern.ch",
          "pid-el": "-1",
          "pid-mu": "-1"
        }
      },
      "wagon_id": 1036,
      "workflow_name": "o2-analysis-pid-tof-full",
      "suffix": ""
    },
    {
      "subwagon_id": 1571,
      "subwagon_name": "base",
      "configuration": {
        "hf-filter": {
          "femtoMaxNsigmaProton": "3",
          "ccdbPathGrpMag": "GLO/Config/GRPMagField",
          "cutsTrackBeauty4Prong": {
            "values": [
              [
                0.002,
                10
              ],
              [
                0.002,
                10
              ],
              [
                0.002,
                10
              ],
              [
                0.002,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ]
            ]
          },
          "femtoMaxRelativeMomentum": "0.8",
          "deltaMassLb": "0.3",
          "nsigmaTPCProtonLc": "4",
          "pTMinSoftPion": "0.1",
          "nsigmaTOFKaon3Prong": "4",
          "onnxFileDPlusToPiKPiConf": "/cvmfs/alice.cern.ch/data/analysis/2022/vAN-20220818/PWGHF/o2/trigger/ModelHandler_onnx_DplusToPiKPi.onnx",
          "onnxFileXicToPiKPConf": "",
          "onnxFileDSToPiKKConf": "/cvmfs/alice.cern.ch/data/analysis/2022/vAN-20220818/PWGHF/o2/trigger/ModelHandler_onnx_DsToKKPi.onnx",
          "timestampCCDB": "-1",
          "ccdbPathTPC": "Users/i/iarsene/Calib/TPCpostCalib",
          "deltaMassBs": "0.3",
          "nsigmaTOFPionKaonDzero": "4",
          "deltaMassXib": "0.3",
          "deltaMassDStar": "0.04",
          "pTThreshold3Prong": "8",
          "pTBinsBDT": {
            "values": [
              0,
              1000
            ]
          },
          "deltaMassB0": "0.3",
          "applyOptimisation": "0",
          "deltaMassBPlus": "0.3",
          "onnxFileD0ToKPiConf": "/cvmfs/alice.cern.ch/data/analysis/2022/vAN-20220818/PWGHF/o2/trigger/ModelHandler_onnx_D0ToKPi.onnx",
          "activateQA": "2",
          "computeTPCPostCalib": "0",
          "pTThreshold2Prong": "8",
          "femtoMinProtonPt": "0.5",
          "nsigmaTPCKaon3Prong": "4",
          "pTMinBeautyBachelor": "0.5",
          "mlModelPathCCDB": "Analysis/PWGHF/ML/HFTrigger/",
          "onnxFileLcToPiKPConf": "/cvmfs/alice.cern.ch/data/analysis/2022/vAN-20220818/PWGHF/o2/trigger/ModelHandler_onnx_LcToPKPi.onnx",
          "cutsTrackBeauty3Prong": {
            "values": [
              [
                0.002,
                10
              ],
              [
                0.002,
                10
              ],
              [
                0.002,
                10
              ],
              [
                0.002,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ]
            ]
          },
          "thresholdBDTScoreLcToPiKP": {
            "values": [
              [
                0.1,
                0.5,
                0.5
              ]
            ]
          },
          "thresholdBDTScoreD0ToKPi": {
            "values": [
              [
                0.1,
                0.4,
                0.6
              ]
            ]
          },
          "thresholdBDTScoreDSToPiKK": {
            "values": [
              [
                0.1,
                0.5,
                0.5
              ]
            ]
          },
          "thresholdBDTScoreXicToPiKP": {
            "values": [
              [
                0.1,
                0.5,
                0.5
              ]
            ]
          },
          "applyML": "1",
          "loadModelsFromCCDB": "0",
          "nsigmaTOFProtonLc": "4",
          "nsigmaTPCPionKaonDzero": "4",
          "pTBinsTrack": {
            "values": [
              0,
              0.5,
              1,
              1.5,
              2,
              3,
              1000
            ]
          },
          "ccdb-url": "http://ccdb-test.cern.ch:8080",
          "deltaMassCharmHadronForBeauty": "0.04",
          "femtoProtonOnlyTOF": "0",
          "thresholdBDTScoreDPlusToPiKPi": {
            "values": [
              [
                0.1,
                0.5,
                0.5
              ]
            ]
          }
        }
      },
      "wagon_id": 1385,
      "workflow_name": "o2-analysis-hf-filter",
      "suffix": ""
    },
    {
      "subwagon_id": 2796,
      "subwagon_name": "base",
      "configuration": {
        "mult-filter": {
          "selt0time": "0",
          "selHMFv0": "33559.5",
          "selt0vtx": "0",
          "sel1Fft0": "0.845",
          "selHTrkMult": "30",
          "sel1Ffv0": "0.93",
          "sel8": "1",
          "sel1Mft0cfv0": "187",
          "sel1Mft0": "112",
          "cfgTrkLowPtCut": "0.15",
          "selPtTrig": "5",
          "cfgTrkEtaCut": "0.8",
          "sel1Fft0cfv0": "0.885"
        }
      },
      "wagon_id": 2471,
      "workflow_name": "o2-analysis-mult-filter",
      "suffix": ""
    },
    {
      "subwagon_id": 2813,
      "subwagon_name": "base",
      "configuration": {
        "lf-strangeness-filter": {
          "nsigmatpcpr": "6",
          "lowerradiusXiYN": "18",
          "dcav0dau": "2",
          "kint7": "0",
          "processRun3": "1",
          "dcamesontopv": "0.05",
          "processRun2": "0",
          "v0radius": "1",
          "hMinPt": "5",
          "omegarej": "0.005",
          "xirej": "0.008",
          "v0cospa": "0.95",
          "cutzvertex": "1000",
          "cascradius": "0.3",
          "eta": "2",
          "nsigmatpcpi": "6",
          "properlifetimefactor": "5",
          "dcabachtopv": "0.05",
          "dcacascdau": "2",
          "doextraQA": "1",
          "casccospaomega": "0.95",
          "rapidity": "2",
          "ptthrtof": "1",
          "minpt": "0",
          "sel7": "0",
          "casccospaxi": "0.95",
          "sel8": "0",
          "isTrackFilter": "1",
          "etadau": "1.1",
          "ximasswindow": "0.075",
          "omegamasswindow": "0.075",
          "dcabaryontopv": "0.05",
          "hastof": "0",
          "nsigmatpcka": "6",
          "hEta": "1.1",
          "masslambdalimit": "0.02",
          "dcav0topv": "0"
        }
      },
      "wagon_id": 2487,
      "workflow_name": "o2-analysis-lf-strangeness-filter",
      "suffix": ""
    },
    {
      "subwagon_id": 3147,
      "subwagon_name": "base",
      "configuration": {
        "c-f-filter": {
          "ConfTrkTPCcRowsMin": "50",
          "ConfTrkITSRefit": "0",
          "ConfUseManualPIDproton": "1",
          "ConfPIDRejection": {
            "values": [
              [
                -4,
                4
              ],
              [
                -4,
                4
              ],
              [
                -4,
                4
              ]
            ]
          },
          "ConfV0InvMassUpLimit": "1.2",
          "ConfV0InvMassLowLimit": "1.05",
          "ConfTrkDCAzMax": "0.3",
          "ConfDeuteronThPVMom": "0",
          "ConfPIDCuts": {
            "values": [
              [
                -5,
                5,
                -5,
                5,
                6
              ],
              [
                -4,
                4,
                -99,
                99,
                99
              ]
            ]
          },
          "ConfV0TranRadV0Max": "100",
          "ConfUseManualPIDpion": "0",
          "ConfPtCuts": {
            "values": [
              [
                0.3499999940395355,
                6,
                0.75
              ],
              [
                0.3499999940395355,
                1.600000023841858,
                99
              ],
              [
                0.3499999940395355,
                6,
                99
              ]
            ]
          },
          "ConfTrkITSnclsIbMin": "0",
          "ConfPIDTPCTOFAvg": {
            "values": [
              [
                0,
                0
              ],
              [
                0,
                0
              ],
              [
                0,
                0
              ],
              [
                0,
                0
              ]
            ]
          },
          "ConfEvtZvtx": "12",
          "ConfTrkRequireChi2MaxITS": "0",
          "ConfDaughTPCnclsMin": "50",
          "ConfV0TranRadV0Min": "0.2",
          "ConfV0RejectKaons": "1",
          "ConfPIDBBAntiPion": "Users/l/lserksny/PIDAntiPion",
          "ConfTrkTPCRefit": "0",
          "ConfPIDBBProton": "Users/l/lserksny/PIDProton",
          "ConfPIDBBAntiElectron": "Users/l/lserksny/PIDAntiElectron",
          "ConfUseManualPIDel": "0",
          "ConfTrkTPCfCls": "0.83",
          "ConfRejectNOTDeuteron": "1",
          "ConfTPCNClustersMin": {
            "values": [
              [
                60,
                60
              ]
            ]
          },
          "ConfDaughEta": "0.85",
          "ConfPIDBBElectron": "Users/l/lserksny/PIDElectron",
          "ConfTrkEta": "0.85",
          "ConfV0CPAMin": "0.96",
          "ConfQ3Limits": {
            "values": [
              [
                1.5,
                1.5,
                1.5,
                1.5
              ]
            ]
          },
          "ConfUseManualPIDdaughterPion": "0",
          "ConfTrkMaxChi2PerClusterTPC": "4",
          "ConfV0PtMin": "0",
          "ConfTrkITSnclsMin": "0",
          "ConfUseManualPIDdaughterProton": "0",
          "ConfV0DecVtxMax": "100",
          "ConfAvgPath": "Users/l/lserksny/TPCTOFAvg",
          "ConfRejectNotPropagatedTracks": "0",
          "ConfEvtOfflineCheck": "0",
          "ConfUseAvgFromCCDB": "0",
          "ConfTrkTPCsClsMax": "160",
          "ConfAutocorRejection": "1",
          "ConfPIDBBDeuteron": "Users/l/lserksny/PIDDeuteron",
          "ConfIsRun3": "1",
          "ConfDaughPIDCuts": {
            "values": [
              [
                -6,
                6
              ],
              [
                -6,
                6
              ]
            ]
          },
          "ConfPIDBBAntiProton": "Users/l/lserksny/PIDAntiProton",
          "ConfV0DCADaughMax": "1.8",
          "ConfDaughDCAMin": "0.04",
          "ConfPIDBBPion": "Users/l/lserksny/PIDPion",
          "ConfTrkDCAxyMax": "0.15",
          "ConfTrkRequireChi2MaxTPC": "0",
          "ConfPIDCutsAnti": {
            "values": [
              [
                -5,
                5,
                -5,
                5,
                6
              ],
              [
                -4,
                4,
                -99,
                99,
                99
              ]
            ]
          },
          "ConfEvtSelectZvtx": "0",
          "ConfUseManualPIDdeuteron": "1",
          "ConfPIDBBAntiDeuteron": "Users/l/lserksny/PIDAntiDeuteron",
          "ConfV0InvKaonMassUpLimit": "0.505",
          "ConfTriggerSwitches": {
            "values": [
              [
                1,
                1,
                1,
                1,
                1,
                1
              ]
            ]
          },
          "ConfKstarLimits": {
            "values": [
              [
                1.2000000476837158,
                1.2000000476837158
              ]
            ]
          },
          "ConfTrkMaxChi2PerClusterITS": "36",
          "ConfV0InvKaonMassLowLimit": "0.49"
        }
      },
      "wagon_id": 2790,
      "workflow_name": "o2-analysis-cf-filter",
      "suffix": ""
    },
    {
      "subwagon_id": 313,
      "subwagon_name": "base",
      "configuration": {
        "tpc-pid-full": {
          "param-file": "",
          "networkPathCCDB": "Analysis/PID/TPC/ML",
          "pid-he": "-1",
          "pid-ka": "-1",
          "ccdbPath": "Analysis/PID/TPC/Response",
          "pid-pi": "-1",
          "pid-pr": "-1",
          "autofetchNetworks": "1",
          "ccdb-timestamp": "0",
          "enableNetworkOptimizations": "1",
          "pid-tr": "-1",
          "pid-de": "-1",
          "networkSetNumThreads": "0",
          "pid-al": "-1",
          "ccdb-url": "http://alice-ccdb.cern.ch",
          "useNetworkCorrection": "0",
          "pid-el": "-1",
          "pid-mu": "-1",
          "networkPathLocally": "network.onnx"
        }
      },
      "wagon_id": 268,
      "workflow_name": "o2-analysis-pid-tpc-full",
      "suffix": ""
    },
    {
      "subwagon_id": 1242,
      "subwagon_name": "base",
      "configuration": {
        "track-selection": {
          "ptMax": "1e+10",
          "etaMin": "-0.8",
          "isRun3": "1",
          "itsMatching": "0",
          "etaMax": "0.8",
          "compatibilityIU": "0",
          "ptMin": "0.1",
          "produceFBextendedTable": "0"
        }
      },
      "wagon_id": 1093,
      "workflow_name": "o2-analysis-trackselection",
      "suffix": ""
    },
    {
      "subwagon_id": 2339,
      "subwagon_name": "base",
      "configuration": {
        "multiplicity-table": {
          "doVertexZeq": "1",
          "processRun3": "1",
          "processRun2": "0"
        }
      },
      "wagon_id": 2093,
      "workflow_name": "o2-analysis-multiplicity-table",
      "suffix": ""
    },
    {
      "subwagon_id": 1716,
      "subwagon_name": "base",
      "configuration": {
        "track-propagation": {
          "lutPath": "GLO/Param/MatLUT",
          "mVtxPath": "GLO/Calib/MeanVertex",
          "geoPath": "GLO/Config/GeometryAligned",
          "grpmagPath": "GLO/Config/GRPMagField",
          "ccdb-url": "http://alice-ccdb.cern.ch",
          "minPropagationDistance": "5",
          "processStandard": "0",
          "processCovariance": "1"
        }
      },
      "wagon_id": 1524,
      "workflow_name": "o2-analysis-track-propagation",
      "suffix": ""
    },
    {
      "subwagon_id": 1933,
      "subwagon_name": "base",
      "configuration": {
        "fwd-track-extension": {}
      },
      "wagon_id": 1725,
      "workflow_name": "o2-analysis-fwdtrackextension",
      "suffix": ""
    },
    {
      "subwagon_id": 1337,
      "subwagon_name": "base",
      "configuration": {
        "tof-signal": {},
        "tof-event-time": {
          "param-file": "",
          "param-sigma": "TOFReso",
          "minMomentum": "0.5",
          "ccdb-timestamp": "-1",
          "maxMomentum": "2",
          "processOnlyFT0": "0",
          "processRun2": "0",
          "processFT0": "0",
          "processNoFT0": "1",
          "ccdb-url": "http://alice-ccdb.cern.ch",
          "ccdbPath": "Analysis/PID/TOF"
        }
      },
      "wagon_id": 1178,
      "workflow_name": "o2-analysis-pid-tof-base",
      "suffix": ""
    },
    {
      "subwagon_id": 634,
      "subwagon_name": "base",
      "configuration": {
        "hf-track-index-skim-creator-cascades": {
          "maxDZIni": "4",
          "tpcRefitV0Daugh": "1",
          "ccdbPathGrpMag": "GLO/Config/GRPMagField",
          "processCascades": "0",
          "propagateToPCA": "1",
          "cutInvMassCascLc": "1",
          "ccdbPathGrp": "GLO/GRP/GRP",
          "processNoCascades": "1",
          "ccdbUrl": "http://alice-ccdb.cern.ch",
          "doCutQuality": "1",
          "nCrossedRowsMinBach": "50",
          "etaMaxV0Daugh": "1.1",
          "dcaXYNegToPvMin": "0.1",
          "maxR": "200",
          "nCrossedRowsMinV0Daugh": "50",
          "useAbsDCA": "1",
          "minRelChi2Change": "0.9",
          "cpaV0Min": "0.995",
          "cutInvMassV0": "0.05",
          "dcaXYPosToPvMin": "0.1",
          "minParamChange": "0.001",
          "fillHistograms": "1",
          "isRun2": "0",
          "ptCascCandMin": "-1",
          "ccdbPathLut": "GLO/Param/MatLUT",
          "tpcRefitBach": "1",
          "ptMinV0Daugh": "0.05"
        },
        "hf-track-index-skim-creator-lf-cascades": {
          "maxDZIni": "4",
          "dcaBachToPv": "0.05",
          "dcaV0ToPv": "0.05",
          "ccdbPathGrpMag": "GLO/Config/GRPMagField",
          "v0Radius": "0.9",
          "tpcNsigmaBachelor": "4",
          "processCascades": "0",
          "dcaV0Dau": "2",
          "propagateToPCA": "1",
          "ccdbPathGrp": "GLO/GRP/GRP",
          "processNoCascades": "1",
          "do3Prong": "0",
          "v0MassWindow": "0.008",
          "ccdbUrl": "http://alice-ccdb.cern.ch",
          "rejDiffCollTrack": "1",
          "doCutQuality": "1",
          "tpcNsigmaPion": "4",
          "cascRadius": "0.5",
          "tpcNsigmaProton": "4",
          "maxR": "200",
          "useAbsDCA": "1",
          "minRelChi2Change": "0.9",
          "dcaPosToPv": "0.05",
          "cascCosPA": "0.95",
          "dcaNegToPv": "0.05",
          "dcaCascDau": "1",
          "minParamChange": "0.001",
          "v0CosPA": "0.95",
          "fillHistograms": "1",
          "isRun2": "0",
          "ccdbPathLut": "GLO/Param/MatLUT",
          "ccdbPathGeo": "GLO/Config/GeometryAligned"
        },
        "hf-track-index-skim-creator": {
          "maxDZIni": "4",
          "cutsDplusToPiKPi": {
            "values": [
              [
                1.75,
                2,
                0.96,
                0.02
              ],
              [
                1.75,
                2,
                0.98,
                0.02
              ]
            ]
          },
          "ccdbPathGrpMag": "GLO/Config/GRPMagField",
          "axisNumTracks": {
            "values": [
              250,
              -0.5,
              249.5
            ]
          },
          "binsPtDsToKKPi": {
            "values": [
              1,
              5,
              1000
            ]
          },
          "propagateToPCA": "1",
          "binsPtJpsiToEE": {
            "values": [
              1,
              5,
              1000
            ]
          },
          "cutsLcToPKPi": {
            "values": [
              [
                2.15,
                2.4,
                0.95,
                0
              ],
              [
                2.15,
                2.4,
                0.98,
                0.01
              ]
            ]
          },
          "ccdbPathGrp": "GLO/GRP/GRP",
          "binsPtLcToPKPi": {
            "values": [
              2,
              5,
              1000
            ]
          },
          "doPvRefit": "0",
          "axisPvRefitDeltaY": {
            "values": [
              1000,
              -0.5,
              0.5
            ]
          },
          "do3Prong": "1",
          "cutsJpsiToEE": {
            "values": [
              [
                0,
                0,
                1,
                -1000
              ],
              [
                0,
                0,
                1,
                -1000
              ]
            ]
          },
          "axisPvRefitDeltaZ": {
            "values": [
              1000,
              -0.5,
              0.5
            ]
          },
          "cutsD0ToPiK": {
            "values": [
              [
                1.7,
                2.1,
                0.95,
                1
              ],
              [
                1.7,
                2.15,
                0.98,
                1
              ]
            ]
          },
          "ccdbUrl": "http://alice-ccdb.cern.ch",
          "maxR": "200",
          "axisPvRefitDeltaX": {
            "values": [
              1000,
              -0.5,
              0.5
            ]
          },
          "useAbsDCA": "1",
          "minRelChi2Change": "0.9",
          "cutsJpsiToMuMu": {
            "values": [
              [
                0,
                0,
                1,
                -1000
              ],
              [
                0,
                0,
                1,
                -1000
              ]
            ]
          },
          "debug": "0",
          "binsPtXicToPKPi": {
            "values": [
              1,
              5,
              1000
            ]
          },
          "cutsDsToKKPi": {
            "values": [
              [
                1.78,
                2.18,
                0.95,
                0.01
              ],
              [
                1.78,
                2.18,
                0.98,
                0.02
              ]
            ]
          },
          "binsPtDplusToPiKPi": {
            "values": [
              1,
              5,
              1000
            ]
          },
          "process2And3Prongs": "1",
          "axisNumCands": {
            "values": [
              200,
              -0.5,
              199
            ]
          },
          "binsPtJpsiToMuMu": {
            "values": [
              1,
              5,
              1000
            ]
          },
          "binsPtD0ToPiK": {
            "values": [
              1,
              5,
              1000
            ]
          },
          "cutsXicToPKPi": {
            "values": [
              [
                0,
                0,
                1,
                1000
              ],
              [
                0,
                0,
                1,
                1000
              ]
            ]
          },
          "minParamChange": "0.001",
          "processNo2And3Prongs": "0",
          "ptTolerance": "0.1",
          "fillHistograms": "0",
          "isRun2": "0",
          "ccdbPathLut": "GLO/Param/MatLUT"
        },
        "hf-track-index-skim-creator-tag-sel-collisions": {
          "zVertexMin": "-100",
          "xVertexMax": "100",
          "useSel8Trigger": "0",
          "axisNumContributors": {
            "values": [
              200,
              -0.5,
              199.5
            ]
          },
          "triggerClassName": "kINT7",
          "processTrigSel": "0",
          "yVertexMax": "100",
          "fillHistograms": "0",
          "zVertexMax": "100",
          "xVertexMin": "-100",
          "chi2Max": "0",
          "processNoTrigSel": "1",
          "nContribMin": "0",
          "yVertexMin": "-100"
        },
        "hf-track-index-skim-creator-tag-sel-tracks": {
          "etaMaxTrack2Prong": "0.8",
          "ccdbPathGrpMag": "GLO/Config/GRPMagField",
          "cutsTrack3Prong": {
            "values": [
              [
                0,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ]
            ]
          },
          "binsPtTrack": {
            "values": [
              0,
              0.5,
              1,
              1.5,
              2,
              3,
              1000
            ]
          },
          "ccdbPathGrp": "GLO/GRP/GRP",
          "doPvRefit": "0",
          "useIsGlobalTrackWoDCA": "1",
          "axisPvRefitDeltaY": {
            "values": [
              1000,
              -0.5,
              0.5
            ]
          },
          "axisPvRefitDeltaZ": {
            "values": [
              1000,
              -0.5,
              0.5
            ]
          },
          "ptMinTrack3Prong": "0.3",
          "ccdbUrl": "http://alice-ccdb.cern.ch",
          "doCutQuality": "1",
          "ptMinTrackBach": "10000",
          "useIsGlobalTrack": "0",
          "axisPvRefitDeltaX": {
            "values": [
              1000,
              -0.5,
              0.5
            ]
          },
          "etaMaxTrackBach": "0",
          "cutsTrack2Prong": {
            "values": [
              [
                0,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ],
              [
                0,
                10
              ]
            ]
          },
          "ptMinTrack2Prong": "0.3",
          "debug": "0",
          "tpcNClsFoundMin": "50",
          "etaMaxTrack3Prong": "0.8",
          "fillHistograms": "0",
          "isRun2": "0",
          "cutsTrackBach": {
            "values": [
              [
                1000,
                10
              ],
              [
                1000,
                10
              ],
              [
                1000,
                10
              ],
              [
                1000,
                10
              ],
              [
                1000,
                10
              ],
              [
                1000,
                10
              ]
            ]
          },
          "ccdbPathLut": "GLO/Param/MatLUT"
        }
      },
      "wagon_id": 581,
      "workflow_name": "o2-analysis-hf-track-index-skim-creator",
      "suffix": ""
    },
    {
      "subwagon_id": 1768,
      "subwagon_name": "base",
      "configuration": {
        "lambdakzero-initializer": {},
        "lambdakzero-builder": {
          "lutPath": "GLO/Param/MatLUT",
          "dcav0dau": "6",
          "processRun3": "1",
          "processRun2": "0",
          "v0radius": "0",
          "dQALambdaMassWindow": "0.005",
          "d_UseAbsDCA": "1",
          "d_UseAutodetectMode": "0",
          "tpcrefit": "0",
          "grpPath": "GLO/GRP/GRP",
          "dQAMaxPt": "5",
          "v0cospa": "0.9",
          "useMatCorrType": "2",
          "d_doQA": "0",
          "d_UseWeightedPCA": "0",
          "rejDiffCollTracks": "0",
          "dQANBinsPtCoarse": "10",
          "geoPath": "GLO/Config/GeometryAligned",
          "dcanegtopv": "0.01",
          "dQANBinsMass": "400",
          "dcapostopv": "0.01",
          "createV0CovMats": "-1",
          "d_doTrackQA": "0",
          "grpmagPath": "GLO/Config/GRPMagField",
          "dQANBinsRadius": "500",
          "dQAK0ShortMassWindow": "0.005",
          "d_bz": "-999",
          "ccdb-url": "http://alice-ccdb.cern.ch"
        },
        "lambdakzero-v0-data-link-builder": {},
        "lambdakzero-preselector": {
          "dPreselectOnlyBaryons": "0",
          "ddEdxPreSelectAntiLambda": "1",
          "ddEdxPreSelectLambda": "1",
          "dIfMCgenerateLambda": "1",
          "dTPCNCrossedRows": "50",
          "ddEdxPreSelectHypertriton": "0",
          "dIfMCgenerateK0Short": "0",
          "dIfMCgenerateGamma": "0",
          "ddEdxPreSelectGamma": "0",
          "processBuildAll": "1",
          "processBuildMCAssociated": "0",
          "ddEdxPreSelectAntiHypertriton": "0",
          "ddEdxPreSelectionWindow": "7",
          "dIfMCgenerateHypertriton": "0",
          "dIfMCgenerateAntiHypertriton": "0",
          "processBuildValiddEdx": "0",
          "dIfMCgenerateAntiLambda": "1",
          "ddEdxPreSelectK0Short": "0",
          "processBuildValiddEdxMCAssociated": "0"
        }
      },
      "wagon_id": 1567,
      "workflow_name": "o2-analysis-lf-lambdakzerobuilder",
      "suffix": ""
    },
    {
      "subwagon_id": 3128,
      "subwagon_name": "base",
      "configuration": {
        "hf-track-to-collision-association": {
          "debug": "0",
          "timeMargin": "500",
          "applyMinimalTrackSelForRun2": "0",
          "applyIsGlobalTrackWoDCA": "1",
          "processAssocWithAmb": "0",
          "processStandardAssoc": "0",
          "processAssocWithTime": "1",
          "nSigmaForTimeCompat": "4"
        }
      },
      "wagon_id": 2771,
      "workflow_name": "o2-analysis-hf-track-to-collision-associator",
      "suffix": ""
    },
    {
      "subwagon_id": 3190,
      "subwagon_name": "base",
      "configuration": {
        "pid-multiplicity": {}
      },
      "wagon_id": 2832,
      "workflow_name": "o2-analysis-pid-tpc-base",
      "suffix": ""
    },
    {
      "subwagon_id": 65,
      "subwagon_name": "base",
      "configuration": {
        "tpc-pid": {
          "param-file": "",
          "networkPathCCDB": "Analysis/PID/TPC/ML",
          "pid-he": "-1",
          "pid-ka": "-1",
          "ccdbPath": "Analysis/PID/TPC/Response",
          "pid-pi": "-1",
          "pid-pr": "-1",
          "autofetchNetworks": "1",
          "ccdb-timestamp": "0",
          "enableNetworkOptimizations": "1",
          "pid-tr": "-1",
          "pid-de": "-1",
          "networkSetNumThreads": "0",
          "pid-al": "-1",
          "ccdb-url": "http://alice-ccdb.cern.ch",
          "useNetworkCorrection": "0",
          "pid-el": "-1",
          "pid-mu": "-1",
          "networkPathLocally": "network.onnx"
        }
      },
      "wagon_id": 59,
      "workflow_name": "o2-analysis-pid-tpc",
      "suffix": ""
    },
    {
      "subwagon_id": 2814,
      "subwagon_name": "base",
      "configuration": {
        "cascade-builder": {
          "lutPath": "GLO/Param/MatLUT",
          "casccospa": "0.7",
          "processRun3": "1",
          "processRun2": "0",
          "useMatCorrTypeCasc": "2",
          "d_UseAbsDCA": "1",
          "d_UseAutodetectMode": "0",
          "tpcrefit": "0",
          "grpPath": "GLO/GRP/GRP",
          "dQAMaxPt": "5",
          "cascradius": "0.3",
          "createCascCovMats": "1",
          "useMatCorrType": "2",
          "d_doQA": "0",
          "d_UseWeightedPCA": "0",
          "rejDiffCollTracks": "0",
          "dcabachtopv": "0.05",
          "dQANBinsPtCoarse": "10",
          "dcacascdau": "2",
          "dQAXiMassWindow": "0.005",
          "geoPath": "GLO/Config/GeometryAligned",
          "dQANBinsMass": "400",
          "lambdaMassWindow": "0.02",
          "dQAOmegaMassWindow": "0.005",
          "d_doTrackQA": "0",
          "grpmagPath": "GLO/Config/GRPMagField",
          "dQANBinsRadius": "500",
          "d_bz": "-999",
          "ccdb-url": "http://alice-ccdb.cern.ch"
        },
        "cascade-preselector": {
          "dPreselectOnlyBaryons": "0",
          "dIfMCgenerateOmegaPlus": "1",
          "ddEdxPreSelectXiMinus": "1",
          "dTPCNCrossedRows": "50",
          "processBuildAll": "1",
          "dIfMCgenerateXiPlus": "1",
          "processBuildMCAssociated": "0",
          "dIfMCgenerateXiMinus": "1",
          "dIfMCgenerateOmegaMinus": "1",
          "ddEdxPreSelectionWindow": "7",
          "ddEdxPreSelectOmegaPlus": "1",
          "ddEdxPreSelectXiPlus": "1",
          "processBuildValiddEdx": "0",
          "ddEdxPreSelectOmegaMinus": "1",
          "processBuildValiddEdxMCAssociated": "0"
        },
        "cascade-initializer": {}
      },
      "wagon_id": 2488,
      "workflow_name": "o2-analysis-lf-cascadebuilder",
      "suffix": ""
    }
  ],
  "allowed_parent_level": 0,
  "type": "test",
  "inputdata": [
    "/alice/data/2022/LHC22o/526712/apass2/0100"
  ],
  "package_tag": "VO_ALICE@O2Physics::nightly-20230215-1",
  "OutputDirector": {
    "debug_mode": true,
    "resfile": "AO2D",
    "OutputDescriptors": [
      {
        "table": "AOD/CefpDecision/0"
      }
    ],
    "ntfmerge": 1
  },
  "isProductionHY": false,
  "wagons_timestamp": 1676477223025,
  "train_id": "62824",
  "derived_data": true
}
