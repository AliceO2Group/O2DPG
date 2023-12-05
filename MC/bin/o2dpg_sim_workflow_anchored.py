#!/usr/bin/env python3

import sys
import time
import argparse
from os import environ, makedirs
from os.path import join, expanduser, exists, dirname
from os.path import split as ossplit
from copy import deepcopy
import array as arr
import os
import requests
import re
import json
import math

# Creates a time anchored MC workflow; positioned within a given run-number (as function of production size etc)

# Example:
#  ${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow_anchored.py -tf 500 --split-id ${s} --cycle ${cycle} --prod-split 100 --run-number 505600         \
#                                                       -- -gen pythia8 -eCM 900 -col pp -gen pythia8 -proc inel                             \
#                                                           -ns 22 -e TGeant4                                                                \
#                                                           -j 8 -interactionRate 2000                                                       \
#                                                           -field +2                                                                        \
#                                                           -confKey "Diamond.width[2]=6"
# (the first set of arguments is used to determine anchoring point; the second set of arguments are passed forward to workflow creation)


# this is PyROOT; enables reading ROOT C++ objects
from ROOT import o2, TFile, TString, TBufferJSON, TClass, std

# some global constants
# this should be taken from the C++ code (via PyROOT and library access to these constants)
LHCMaxBunches = 3564;                           # max N bunches
LHCRFFreq = 400.789e6;                          # LHC RF frequency in Hz
LHCBunchSpacingNS = 10 * 1.e9 / LHCRFFreq;      # bunch spacing in ns (10 RFbuckets)
LHCOrbitNS = LHCMaxBunches * LHCBunchSpacingNS; # orbit duration in ns
LHCOrbitMUS = LHCOrbitNS * 1e-3;                # orbit duration in \mus
LHCBunchSpacingMUS = LHCBunchSpacingNS * 1e-3   # bunch spacing in mus

# these need to go into a module / support layer
class CCDBAccessor:
    def __init__(self, url):
        # This is used for some special operations
        self.api = o2.ccdb.CcdbApi()
        self.api.init(url)

        # this is used for the actual fetching for now
        o2.ccdb.BasicCCDBManager.instance().setURL(url)
        # we allow nullptr responsens and will treat it ourselves
        o2.ccdb.BasicCCDBManager.instance().setFatalWhenNull(False)

    def list(self, path, dump_path=None):
        ret = self.api.list(path, False, "application/json")
        ret = json.loads(ret)
        if ret and "objects" in ret:
            ret = ret["objects"]
        if ret and dump_path:
            print(f"CCDB object information for path {path} stored in {dump_path}")
            dump_json(ret, dump_path)
        return ret

    def fetch(self, path, obj_type, timestamp=None, meta_info=None):
        """
        TODO We could use CcdbApi::snapshot at some point, needs revision
        """

        if not timestamp:
            timestamp = o2.ccdb.BasicCCDBManager.instance().getTimestamp()
        else:
            o2.ccdb.BasicCCDBManager.instance().setTimestamp(timestamp)

        if not meta_info:
            obj = o2.ccdb.BasicCCDBManager.instance().get[obj_type](path)
        else:
            obj = o2.ccdb.BasicCCDBManager.instance().get[obj_type](path, meta_info)

        return timestamp, obj

    def fetch_header(self, path, timestamp=None):
        meta_info = std.map["std::string", "std::string"]()
        if timestamp is None:
            timestamp = -1
        header = self.api.retrieveHeaders(path, meta_info, timestamp)
        return header



def retrieve_sor_eor(ccdbreader, run_number):
    """
    retrieves start of run (sor) and end of run (eor) given a run number
    from the RCT/Info/RunInformation table
    """

    path_run_info = "RCT/Info/RunInformation"
    header = ccdbreader.fetch_header(path_run_info, run_number)
    if not header:
       print(f"WARNING: Cannot find run information for run number {r}")
       return None
    # return this a dictionary
    return {"SOR": int(header["SOR"]), "EOR": int(header["EOR"])}


def retrieve_CCDBObject_asJSON(ccdbreader, path, timestamp, objtype_external = None):
    """
    Retrieves a CCDB object as a JSON/dictionary.
    No need to know the type of the object a-priori.
    """
    header = ccdbreader.fetch_header(path, timestamp)
    if not header:
       print(f"WARNING: Could not get header for path ${path} and timestamp {timestamp}")
       return None
    objtype=header["ObjectType"]
    if objtype == None:
       objtype = objtype_external
    if objtype == None:
       return None

    ts, obj = ccdbreader.fetch(path, objtype, timestamp)
    # convert object to json
    jsonTString = TBufferJSON.ConvertToJSON(obj, TClass.GetClass(objtype))
    return json.loads(jsonTString.Data())

def retrieve_params_fromGRPECS(ccdbreader, run_number, rct = None):
    """
    Retrieves start of run (sor), end of run (eor) and other global parameters from the GRPECS object,
    given a run number. We first need to find the right object
    ... but this is possible with a browsing request and meta_data filtering.
    Optionally, we can pass an existing result from RCT/Info/RunInformation to check for consistency.
    In this case and when information is inconsistent we will take time from RCT and issue a warning message.
    """

    # make a simple HTTP request on the "browsing" endpoint
    url="http://alice-ccdb.cern.ch/browse/GLO/Config/GRPECS/runNumber="+str(run_number)
    ansobject=requests.get(url)
    tokens=ansobject.text.split("\n")

    # look for the FIRST ID and validity token
    ID=None
    VALIDITY=None
    for t in tokens:
      if t.count("ID:") > 0:
        ID=t.split(":")[1]
      if t.count("Validity:") > 0:
        VALIDITY=t.split(":")[1]
      if ID!=None and VALIDITY!=None:
        break

    assert(ID != None)
    assert(VALIDITY != None)

    match_object=re.match("\s*([0-9]*)\s*-\s*([0-9]*)\s*.*", VALIDITY)
    SOV = -1  # start of object validity (not necessarily the same as actual run-start)
    EOV = -1  # end of object validity (not the same as actual run-end)
    if match_object != None:
      SOV=match_object[1]
      EOV=match_object[2]

    # we make a suitable request (at the start time) --> this gives the actual
    # object, with which we can query the end time as well
    grp=retrieve_CCDBObject_asJSON(ccdbreader, "/GLO/Config/GRPECS" + "/runNumber=" + str(run_number) + "/", int(SOV))


    # check that this object is really the one we wanted based on run-number
    assert(int(grp["mRun"]) == int(run_number))

    SOR=int(grp["mTimeStart"]) # in milliseconds
    EOR=int(grp["mTimeEnd"])
    # cross check with RCT if available
    if rct != None:
       # verify that the variaous sor_eor information are the same
       if SOR != rct["SOR"]:
         print ("WARNING: Inconsistent SOR information on CCDB (divergence between GRPECS and RCT) ... will take RCT one")
         SOR=rct["SOR"]

       if EOR != rct["EOR"]:
         print ("WARNING: Inconsistent EOR information on CCDB (divergence between GRPECS and RCT) ... will take RCT one")
         EOR=rct["EOR"]

    # fetch orbit reset to calculate orbitFirst
    ts, oreset = ccdbreader.fetch("CTP/Calib/OrbitReset", "vector<Long64_t>", timestamp = SOR)
    print ("All orbit resets")
    for i in range(len(oreset)):
        print (" oreset " + str(i) + " " + str(oreset[i]))

    print ("OrbitReset:", int(oreset[0]))
    print ("RunStart:", SOR)

    orbitFirst = int((1000*SOR - oreset[0])//LHCOrbitMUS)  # calc done in microseconds
    orbitLast = int((1000*EOR - oreset[0])//LHCOrbitMUS)
    print ("OrbitFirst", orbitFirst) # first orbit of this run
    print ("LastOrbit of run", orbitLast)

    # Now fetch the detector list
    print ("DetsReadout-Mask: ", grp["mDetsReadout"]['v'])
    detList = o2.detectors.DetID.getNames(grp["mDetsReadout"]['v'])
    print ("Detector list is ", detList)

    # orbitReset.get(run_number)
    return {"SOR": SOR, "EOR": EOR, "FirstOrbit" : orbitFirst, "LastOrbit" : orbitLast, "OrbitsPerTF" : int(grp["mNHBFPerTF"]), "detList" : detList}

def retrieve_GRP(ccdbreader, timestamp):
    """
    retrieves the GRP for a given time stamp
    """
    grp_path = "GLO/GRP/GRP"
    header = ccdbreader.fetch_header(grp_path, timestamp)
    if not header:
       print(f"WARNING: Could not download GRP object for timestamp {timestamp}")
       return None
    ts, grp = ccdbreader.fetch(grp_path, "o2::parameters::GRPObject", timestamp = timestamp)
    return grp

def retrieve_GRPLHCIF(ccdbreader, timestamp):
    """
    retrieves the GRPLHCIF object for a given time stamp
    """
    _, grplhcif = ccdbreader.fetch("GLO/Config/GRPLHCIF", "o2::parameters::GRPLHCIFData", timestamp = timestamp)
    return grplhcif

def retrieve_CTPScalers(ccdbreader, run_number, timestamp=None):
    """
    retrieves the CTP scalers object for a given timestamp and run_number
    and calculates the interation rate to be applied in Monte Carlo digitizers
    """
    path = "CTP/Calib/Scalers/runNumber=" + str(run_number)
    _, ctpscaler = ccdbreader.fetch(path, "o2::ctp::CTPRunScalers", timestamp = timestamp)
    if ctpscaler is not None:
      ctpscaler.convertRawToO2()
      return ctpscaler
    return None

def retrieve_MinBias_CTPScaler_Rate(ctpscaler, finaltime, trig_eff, NBunches, ColSystem):
    """
    retrieves the CTP scalers object for a given timestamp and run_number
    and calculates the interation rate to be applied in Monte Carlo digitizers
    """
    # this is the default for pp
    ctpclass = 0 # <---- we take the scaler for FT0
    ctptype = 1
    # this is the default for PbPb
    if ColSystem == "PbPb":
      ctpclass = 25  # <--- we take scalers for ZDC
      ctptype = 7
    print("Fetching rate with class " + str(ctpclass) + " type " + str(ctptype))
    rate = ctpscaler.getRateGivenT(finaltime, ctpclass, ctptype)
    #if ColSystem == "PbPb":
    #  rate.first = rate.first / 28.
    #  rate.second = rate.second / 28.

    print("Global rate " + str(rate.first) + " local rate " + str(rate.second))
    if rate.first >= 0:
      # calculate true rate (input from Chiara Zampolli) using number of bunches
      coll_bunches = NBunches
      mu = - math.log(1. - rate.second / 11245 / coll_bunches) / trig_eff
      finalRate = coll_bunches * mu * 11245
      return finalRate

    print (f"[ERROR]: Could not determine interaction rate; Some (external) default used")
    return None

def determine_timestamp(sor, eor, splitinfo, cycle, ntf, HBF_per_timeframe = 256):
    """
    Determines the timestamp and production offset variable based
    on the global properties of the production (MC split, etc) and the properties
    of the run. ntf is the number of timeframes per MC job

    Args:
        sor: int
            start-of-run in milliseconds since epoch
        eor: int
            end-of-run in milliseconds since epoch
        splitinfo: tuple (int, int)
            splitinfo[0]: split ID of this job
            splitinfo[1]: total number of jobs to split into
        cycle: int
            cycle of this productions. Typically a run is not entirely filled by and anchored simulation
            but only a proportion of events is simulated.
            With increasing number of cycles, the data run is covered more and more.
        ntf: int
            number of timeframes
        HBF_per_timeframe: int
            number of orbits per timeframe
    Returns:
        int: timestamp in milliseconds
        int: production offset aka "which timeslot in this production to simulate"
    """
    totaljobs = splitinfo[1]
    thisjobID = splitinfo[0]
    # length of this run in micro seconds, since we use the orbit duration in micro seconds
    time_length_inmus = 1000 * (eor - sor)

    # figure out how many timeframes fit into this run range
    # take the number of orbits per timeframe and multiply by orbit duration to calculate how many timeframes fit into this run
    ntimeframes = time_length_inmus / (HBF_per_timeframe * LHCOrbitMUS)
    # also calculate how many orbits fit into the run range
    print (f"This run has space for {ntimeframes} timeframes")

    # figure out how many timeframes can maximally be covered by one job
    maxtimeframesperjob = ntimeframes / totaljobs
    print (f"Each job can do {maxtimeframesperjob} maximally at a prod split of {totaljobs}")
    print (f"With each job doing {ntf} timeframes, this corresponds to a filling rate of {ntf / maxtimeframesperjob}")
    # filling rate should be smaller than 100%
    assert(ntf <= maxtimeframesperjob)

    # each cycle populates more and more run range. The maximum number of cycles to populate the run fully is:
    maxcycles = maxtimeframesperjob / ntf
    print (f"We can do this amount of cycle iterations to achieve 100%: {maxcycles}")

    # overall, we have maxcycles * totaljobs slots to fill the run range with ntf timeframes per slot
    # figure out in which slot to simulate
    production_offset = int(thisjobID * maxcycles) + cycle
    # add the time difference of this slot to start-of-run to get the final timestamp
    timestamp_of_production = sor + production_offset * ntf * HBF_per_timeframe * LHCOrbitMUS / 1000
    # this is a closure test. If we had prefect floating point precision everywhere, it wouldn't fail.
    # But since we don't have that and there are some int casts as well, better check again.
    assert (timestamp_of_production >= sor)
    assert (timestamp_of_production <= eor)
    return int(timestamp_of_production), production_offset

def main():
    parser = argparse.ArgumentParser(description='Creates an O2DPG simulation workflow, anchored to a given LHC run. The workflows are time anchored at regular positions within a run as a function of production size, split-id and cycle.')

    parser.add_argument("--run-number", type=int, help="Run number to anchor to", required=True)
    parser.add_argument("--ccdb-url", dest="ccdb_url", help="CCDB access RUL", default="http://alice-ccdb.cern.ch")
    parser.add_argument("--prod-split", type=int, help="The number of MC jobs that sample from the given time range",default=1)
    parser.add_argument("--cycle", type=int, help="MC cycle. Determines the sampling offset", default=0)
    parser.add_argument("--split-id", type=int, help="The split id of this job within the whole production --prod-split)", default=0)
    parser.add_argument("-tf", type=int, help="number of timeframes per job", default=1)
    parser.add_argument("--ccdb-IRate", type=bool, help="whether to try fetching IRate from CCDB/CTP", default=True)
    parser.add_argument("--trig-eff", type=float, dest="trig_eff", help="Trigger eff needed for IR", default=-1.0)
    parser.add_argument("--use-rct-info", dest="use_rct_info", action="store_true", help=argparse.SUPPRESS) # Use SOR and EOR information from RCT instead of SOX and EOX from CTPScalers
    parser.add_argument('forward', nargs=argparse.REMAINDER) # forward args passed to actual workflow creation
    args = parser.parse_args()

    # split id should not be larger than production id
    assert(args.split_id <= args.prod_split)

    # make a CCDB accessor object
    ccdbreader = CCDBAccessor(args.ccdb_url)
    # fetch the EOR/SOR
    rct_sor_eor = retrieve_sor_eor(ccdbreader, args.run_number) # <-- from RCT/Info
    GLOparams = retrieve_params_fromGRPECS(ccdbreader, args.run_number, rct=rct_sor_eor)
    if not GLOparams:
       print ("No time info found")
       sys.exit(1)

    ctp_scalers = retrieve_CTPScalers(ccdbreader, args.run_number)
    if ctp_scalers is None:
      print(f"ERROR: Cannot retrive scalers for run number {args.run_number}")
      exit (1)

    first_orbit = ctp_scalers.getOrbitLimit().first
    # SOR and EOR values in milliseconds
    sor = ctp_scalers.getTimeLimit().first
    eor = ctp_scalers.getTimeLimit().second

    if args.use_rct_info:
      first_orbit = GLOparams["FirstOrbit"]
      # SOR and EOR values in milliseconds
      sor = GLOparams["SOR"]
      eor = GLOparams["EOR"]

    # determine timestamp, and production offset for the final MC job to run
    timestamp, prod_offset = determine_timestamp(sor, eor, [args.split_id - 1, args.prod_split], args.cycle, args.tf, GLOparams["OrbitsPerTF"])

    # this is anchored to
    print ("Determined start-of-run to be: ", sor)
    print ("Determined end-of-run to be: ", eor)
    print ("Determined timestamp to be : ", timestamp)
    print ("Determined offset to be : ", prod_offset)

    # retrieve the GRPHCIF object
    grplhcif = retrieve_GRPLHCIF(ccdbreader, int(timestamp))
    eCM = grplhcif.getSqrtS()
    A1 = grplhcif.getAtomicNumberB1()
    A2 = grplhcif.getAtomicNumberB2()

    # determine collision system and energy
    print ("Determined eMC ", eCM)
    print ("Determined atomic number A1 ", A1)
    print ("Determined atomic number A2 ", A2)
    ColSystem = ""
    if A1 == 82 and A2 == 82:
      ColSystem = "PbPb"
    elif A1 == 1 and A2 == 1:
      ColSystem = "pp"
    else:
      print ("Unknown collision system ... exiting")
      exit (1)

    print ("Collision system ", ColSystem)

    forwardargs = " ".join([ a for a in args.forward if a != '--' ])
    # retrieve interaction rate
    rate = None

    if args.ccdb_IRate == True:
       effTrigger = args.trig_eff
       if effTrigger < 0:
         if ColSystem == "pp":
           if eCM < 1000:
             effTrigger = 0.68
           elif eCM < 6000:
             effTrigger = 0.737
           else:
             effTrigger = 0.759
         elif ColSystem == "PbPb":
           effTrigger = 28.0 # this is ZDC
         else:
           effTrigger = 0.759

       # time needs to be converted to seconds ==> timestamp / 1000
       rate = retrieve_MinBias_CTPScaler_Rate(ctp_scalers, timestamp/1000., effTrigger, grplhcif.getBunchFilling().getNBunches(), ColSystem)

       if rate != None:
         # if the rate calculation was successful we will use it, otherwise we fall back to some rate given as part
         # of args.forward
         # Regular expression pattern to match "interactioRate" followed by an integer
         pattern = r"-interactionRate\s+\d+"
         # Use re.sub() to replace the pattern with an empty string
         forwardargs = re.sub(pattern, " ", forwardargs)
         forwardargs += ' -interactionRate ' + str(int(rate))

    # we finally pass forward to the unanchored MC workflow creation
    # TODO: this needs to be done in a pythonic way clearly
    # NOTE: forwardargs can - in principle - contain some of the arguments that are appended here. However, the last passed argument wins, so they would be overwritten.
    forwardargs += " -tf " + str(args.tf) + " --sor " + str(sor) + " --timestamp " + str(timestamp) + " --production-offset " + str(prod_offset) + " -run " + str(args.run_number) + " --run-anchored --first-orbit "       \
                   + str(first_orbit) + " -field ccdb -bcPatternFile ccdb" + " --orbitsPerTF " + str(GLOparams["OrbitsPerTF"]) + " -col " + str(ColSystem) + " -eCM " + str(eCM) + ' --readoutDets ' + GLOparams['detList']
    print ("forward args ", forwardargs)
    cmd = "${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py " + forwardargs
    print ("Creating time-anchored workflow...")
    os.system(cmd)

if __name__ == "__main__":
  sys.exit(main())
