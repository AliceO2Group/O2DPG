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
from ROOT import o2, TFile, TString, std


# these need to go into a module / support layer
class CCDBAccessor:
    def __init__(self, url):
        # This is used for some special operations
        self.api = o2.ccdb.CcdbApi()
        self.api.init(url)

        # this is used for the actual fetching for now
        o2.ccdb.BasicCCDBManager.instance().setURL(url)

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
            timestamp = self.mgr.getTimestamp()
        else:
            self.mgr.setTimestamp(timestamp)

        if not meta_info:
            obj = self.mgr.get[obj_type](path)
        else:
            obj = self.mgr.getSpecific[obj_type](path, meta_info)

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
    """

    path_run_info = "RCT/RunInformation"
    header = ccdbreader.fetch_header(path_run_info, run_number)
    if not header:
       print(f"WARNING: Cannot find run information for run number {r}")
       return None
    # return this a dictionary
    return {"SOR": int(header["SOR"]), "EOR": int(header["EOR"])}


def retrieve_GRP(ccdbreader, timestamp):
    """
    retrieves the GRP for a given time stamp
    """
    grp_path = "GLO/GRP/GRP"
    header = ccdbreader.fetch_header(grp_path, timestamp)
    if not header:
       print(f"WARNING: Could not download GRP object for timestamp {timestamp}")
       return None
    ts, grp = reader.fetch(grp_path, "o2::parameters::GRPObject", timestamp = timestamp)
    return grp


def determine_timestamp(sor, eor, splitinfo, cycle, ntf):
    """
    Determines the timestamp and production offset variable based
    on the global properties of the production (MC split, etc) and the properties
    of the run. ntf is the number of timeframes per MC job
    """
    totaljobs = splitinfo[1]
    thisjobID = splitinfo[0]
    print (f"Start-of-run : {sor}")
    print (f"End-of-run : {eor}")
    time_length_inmus = 1000.*(eor - sor) # time length in micro seconds
    timestamp_delta = time_length_inmus / totaljobs
    HBF_per_timeframe = 256 # 256 orbits per timeframe --> should be taken from GRP or common constant in all O2DPG

    # this should be taken from the C++ code (via PyROOT and library access to these constants)
    LHCMaxBunches = 3564;                           # max N bunches
    LHCRFFreq = 400.789e6;                          # LHC RF frequency in Hz
    LHCBunchSpacingNS = 10 * 1.e9 / LHCRFFreq;      # bunch spacing in ns (10 RFbuckets)
    LHCOrbitNS = LHCMaxBunches * LHCBunchSpacingNS; # orbit duration in ns
    LHCOrbitMUS = LHCOrbitNS * 1e-3;                # orbit duration in \mus

    ntimeframes = time_length_inmus / (HBF_per_timeframe * LHCOrbitMUS)
    norbits = time_length_inmus / LHCOrbitMUS
    print (f"This run has space for {ntimeframes} timeframes")
    print (f"This run has {norbits} orbits")

    # ntimeframes is the total number of timeframes possible
    # if we have totaljobs number of jobs
    timeframesperjob = ntimeframes // totaljobs
    orbitsperjob = norbits // totaljobs
    print (f"Each job can do {timeframesperjob} maximally at a prod split of {totaljobs}")
    print (f"With each job doing {ntf} timeframes, this corresponds to a filling rate of ", ntf/timeframesperjob)
    maxcycles = timeframesperjob // ntf
    print (f"We can do this amount of cycle iterations to achieve 100%: ", maxcycles)
    
    return sor, int(thisjobID * maxcycles) + cycle

def main():
    parser = argparse.ArgumentParser(description='Creates an O2DPG simulation workflow, anchored to a given LHC run. The workflows are time anchored at regular positions within a run as a function of production size, split-id and cycle.')

    parser.add_argument("--run-number", type=int, help="Run number to anchor to", required=True)
    parser.add_argument("--ccdb-url", dest="ccdb_url", help="CCDB access RUL", default="http://alice-ccdb.cern.ch")
    parser.add_argument("--prod-split", type=int, help="The number of MC jobs that sample from the given time range",default=1)
    parser.add_argument("--cycle", type=int, help="MC cycle. Determines the sampling offset", default=0)
    parser.add_argument("--split-id", type=int, help="The split id of this job within the whole production --prod-split)", default=0)
    parser.add_argument("-tf", type=int, help="number of timeframes per job", default=1)
    parser.add_argument('forward', nargs=argparse.REMAINDER) # forward args passed to actual workflow creation
    args = parser.parse_args()

    # make a CCDB accessor object
    ccdbreader = CCDBAccessor(args.ccdb_url)
    # fetch the EOR/SOR
    sor_eor = retrieve_sor_eor(ccdbreader, args.run_number)
    if not sor_eor:
       print ("No time info found")
       sys.exit(1)

    # determine timestamp, and production offset for the final
    # MC job to run
    timestamp, prod_offset = determine_timestamp(sor_eor["SOR"], sor_eor["EOR"], [args.split_id, args.prod_split], args.cycle, args.tf)
    # this is anchored to
    print ("Determined timestamp to be : ", timestamp)
    print ("Determined offset to be : ", prod_offset)

    # we finally pass forward to the unanchored MC workflow creation
    # TODO: this needs to be done in a pythonic way clearly
    forwardargs = " ".join([ a for a in args.forward if a != '--' ]) + " -tf " + str(args.tf) + " --timestamp " + str(timestamp) + " --production-offset " + str(prod_offset) + " -run " + str(args.run_number) + " -field ccdb -bcPatternFile ccdb"
    cmd = "${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py " + forwardargs
    print ("Creating time-anchored workflow...")
    os.system(cmd)
    # TODO:
    # - we can anchor many more things at this level:
    #   * field
    #   * interaction rate
    #   * vertex position
    #   * ...
    # - develop this into swiss-army tool:
    #   * determine prod split based on sampling-fraction (support for production manager etc)

if __name__ == "__main__":
  sys.exit(main())
