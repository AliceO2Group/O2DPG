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

def retrieve_sor_eor_fromGRPECS(ccdbreader, run_number, rct = None):
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

    # orbitReset.get(run_number)
    return {"SOR": SOR, "EOR": EOR, "FirstOrbit" : orbitFirst, "LastOrbit" : orbitLast, "OrbitsPerTF" : int(grp["mNHBFPerTF"])}

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

def retrieve_MinBias_CTPScaler_Rate(ccdbreader, timestamp, run_number, finaltime, ft0_eff):
    """
    retrieves the CTP scalers object for a given timestamp and run_number
    and calculates the interation rate to be applied in Monte Carlo digitizers
    """
    path = "CTP/Calib/Scalers/runNumber=" + str(run_number)
    ts, ctpscaler = ccdbreader.fetch(path, "o2::ctp::CTPRunScalers", timestamp = timestamp)
    if ctpscaler != None:
      ctpscaler.convertRawToO2()
      rate = ctpscaler.getRateGivenT(finaltime,0,0)  # the simple FT0 rate from the counters
      # print("Global rate " + str(rate.first) + " local rate " + str(rate.second))

      # now get the bunch filling object which is part of GRPLHCIF and calculate
      # true rate (input from Chiara Zampolli)
      ts, grplhcif = ccdbreader.fetch("GLO/Config/GRPLHCIF", "o2::parameters::GRPLHCIFData", timestamp = timestamp)
      coll_bunches = grplhcif.getBunchFilling().getNBunches()
      mu = - math.log(1. - rate.first / 11245 / coll_bunches) / ft0_eff
      finalRate = coll_bunches * mu * 11245
      return finalRate

    print (f"[ERROR]: Could not determine interaction rate; Some (external) default used")
    return None

def determine_timestamp(sor, eor, splitinfo, cycle, ntf, HBF_per_timeframe = 256):
    """
    Determines the timestamp and production offset variable based
    on the global properties of the production (MC split, etc) and the properties
    of the run. ntf is the number of timeframes per MC job
    """
    totaljobs = splitinfo[1]
    thisjobID = splitinfo[0]
    print (f"Start-of-run : {sor}")
    print (f"End-of-run : {eor}")
    time_length_inmus = 1000*(eor - sor) # time length in micro seconds
    timestamp_delta = time_length_inmus / totaljobs

    ntimeframes = time_length_inmus / (HBF_per_timeframe * LHCOrbitMUS)
    norbits = time_length_inmus / LHCOrbitMUS
    print (f"This run has space for {ntimeframes} timeframes")
    print (f"This run has {norbits} orbits")

    # ntimeframes is the total number of timeframes possible
    # if we have totaljobs number of jobs
    maxtimeframesperjob = ntimeframes // totaljobs
    orbitsperjob = norbits // totaljobs
    print (f"Each job can do {maxtimeframesperjob} maximally at a prod split of {totaljobs}")
    print (f"With each job doing {ntf} timeframes, this corresponds to a filling rate of ", ntf/maxtimeframesperjob)
    # filling rate should be smaller than 100%
    assert(ntf <= maxtimeframesperjob)

    maxcycles = maxtimeframesperjob // ntf
    print (f"We can do this amount of cycle iterations to achieve 100%: ", maxcycles)
    
    production_offset = int(thisjobID * maxcycles) + cycle
    timestamp_of_production = sor + production_offset * ntf * HBF_per_timeframe * LHCOrbitMUS / 1000
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
    parser.add_argument("--ft0-eff", type=float, dest="ft0_eff", help="FT0 eff needed for IR", default=0.759)
    parser.add_argument('forward', nargs=argparse.REMAINDER) # forward args passed to actual workflow creation
    args = parser.parse_args()

    # split id should not be larger than production id
    assert(args.split_id < args.prod_split)

    # make a CCDB accessor object
    ccdbreader = CCDBAccessor(args.ccdb_url)
    # fetch the EOR/SOR
    rct_sor_eor = retrieve_sor_eor(ccdbreader, args.run_number) # <-- from RCT/Info
    GLOparams = retrieve_sor_eor_fromGRPECS(ccdbreader, args.run_number, rct=rct_sor_eor)
    if not GLOparams:
       print ("No time info found")
       sys.exit(1)

    # determine timestamp, and production offset for the final
    # MC job to run
    timestamp, prod_offset = determine_timestamp(GLOparams["SOR"], GLOparams["EOR"], [args.split_id, args.prod_split], args.cycle, args.tf, GLOparams["OrbitsPerTF"])
    # this is anchored to
    print ("Determined start-of-run to be: ", GLOparams["SOR"])
    print ("Determined timestamp to be : ", timestamp)
    print ("Determined offset to be : ", prod_offset)
    print ("Determined start of run to be : ", GLOparams["SOR"])

    currentorbit = GLOparams["FirstOrbit"] + prod_offset * GLOparams["OrbitsPerTF"] # orbit number at production start
    currenttime = GLOparams["SOR"] + prod_offset * GLOparams["OrbitsPerTF"] * LHCOrbitMUS // 1000 # timestamp in milliseconds
    print ("Production put at time : " + str(currenttime))

    forwardargs = " ".join([ a for a in args.forward if a != '--' ])
    # retrieve interaction rate
    rate = None
    if args.ccdb_IRate == True:
       rate = retrieve_MinBias_CTPScaler_Rate(ccdbreader, timestamp, args.run_number, currenttime/1000., args.ft0_eff)

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
    forwardargs += " -tf " + str(args.tf) + " --sor " + str(GLOparams["SOR"]) + " --timestamp " + str(timestamp) + " --production-offset " + str(prod_offset) + " -run " + str(args.run_number) + " --run-anchored --first-orbit " + str(GLOparams["FirstOrbit"]) + " -field ccdb -bcPatternFile ccdb" + " --orbitsPerTF " + str(GLOparams["OrbitsPerTF"])
    print ("forward args ", forwardargs)
    cmd = "${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py " + forwardargs
    print ("Creating time-anchored workflow...")
    os.system(cmd)

if __name__ == "__main__":
  sys.exit(main())
