#!/usr/bin/env python3

#
# A script producing a consistent MC->RECO->AOD workflow
# It aims to handle the different MC possible configurations
# It just creates a workflow.json txt file, to execute the workflow one must execute right after
#   ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
#
# Execution examples:
#  - pp PYTHIA jets, 2 events, triggered on high pT decay photons on all barrel calorimeters acceptance, eCMS 13 TeV
#     ./o2dpg_sim_workflow.py -e TGeant3 -ns 2 -j 8 -tf 1 -mod "--skipModules ZDC" -col pp -eCM 13000 \
#                             -proc "jets" -ptHatBin 3 \
#                             -trigger "external" -ini "\$O2DPG_ROOT/MC/config/PWGGAJE/ini/trigger_decay_gamma_allcalo_TrigPt3_5.ini"
#
#  - pp PYTHIA ccbar events embedded into heavy-ion environment, 2 PYTHIA events into 1 bkg event, beams energy 2.510
#     ./o2dpg_sim_workflow.py -e TGeant3 -nb 1 -ns 2 -j 8 -tf 1 -mod "--skipModules ZDC"  \
#                             -col pp -eA 2.510 -proc "ccbar"  --embedding
#

import sys
import time
import argparse
from os import environ, makedirs
from os.path import join, expanduser, exists, dirname
from os.path import split as ossplit
from copy import deepcopy
import json
import array as arr

REQUIRED_ENV = ["O2_ROOT", "O2DPG_ROOT"]
for r in REQUIRED_ENV:
  if not environ.get(r, None):
    print(f"ERROR: Environment {r} required")
    sys.exit(1)

from ROOT import o2, TFile, TString, std


def dump_json(to_dump, path):
    path = expanduser(path)
    dirname, filename = ossplit(path)
    if exists(dirname) and not isdir(dirname):
        print(f"Path {dirname} exists but is not a directory. Not attempting to write there...")
        return False
    if dirname and not exists(dirname):
        makedirs(dirname)
    with open(path, "w") as f:
        json.dump(to_dump, f, indent=2)
    print(f"Dumped JSON to {path}")
    return True

def load_json(path):
    path = expanduser(path)
    if not exists(path):
        print(f"ERROR: Path {path} does not exist")
        return None
    with open(path, "r") as f:
        return json.load(f)


class CCDBAccessor:
    def __init__(self, url):
        # This is used for some special operations
        self.api = o2.ccdb.CcdbApi()
        self.api.init(url)

        # this is used for the actual fetching for now
        self.mgr = o2.ccdb.BasicCCDBManager.instance()
        self.mgr.setURL(url)

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
        """TODO We could use CcdbApi::snapshot at some point, needs revision
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

    def push(self, path, obj, obj_type, meta_info=None, **kwargs):
        """Write an object to CCDB

        This method is likely to only be a dummy and write to CCDB
        for test/demo purposes

        """

        # this is our test path. Make a top dir so we don't mess
        # around in the whole test CCDB
        if not meta_info:
            # construct dummy meta info
            meta_info = std.map["std::string", "std::string"]()

        val_start = kwargs.pop("validity_start", -1)
        val_end = kwargs.pop("validity_end", -1)

        self.api.storeAsTFileAny[obj_type](obj, path, meta_info)
        print(f"Pushed to CCDB({self.mgr.getURL()}) {path}")


def retrieve_sor_eor(url, run_numbers):

    reader = CCDBAccessor(url)
    path_run_info = "RCT/RunInformation"

    # Remove duplicates
    run_numbers = list(set(run_numbers))
    runs = []
    for r in run_numbers:
        header = reader.fetch_header(path_run_info, r)
        if not header:
            print(f"WARNING: Cannot find run information for run number {r}")
            continue
        runs.append({"run_number": r, "SOR": int(header["SOR"]), "EOR": int(header["EOR"])})

    return runs


def sample(runs, samples):
    if samples == 1:
        print(f"WARNING: No sampling requested. Are you sure? If not, just run again with --samples <n_samples>")

    for r in runs:
        time_sampling_step = (r["EOR"] - r["SOR"]) / samples
        if time_sampling_step <= 0:
            print(f"Invalid, SOR ({r['SOR']}) >= EOR ({r['EOR']})")
            return 1
        r["timestamps"] = [int(r["SOR"] + i * time_sampling_step) for i in range(samples)]


def mc_prod(args):
    """Assemble the dictionary of run conditions for given run numbers
    """

    if not 0 < args.lumi_fraction <= 1:
        print(f"Invalid luminosity fraction {args.lumi_fraction}. Must be in [0, 1].")
        return 1

    anchored_config = {"tag": args.tag, "lumi_fraction": args.lumi_fraction, "samples": args.samples, "runs": None}
    anchored_config["runs"] = retrieve_sor_eor(args.ccdb_url, args.run_numbers)
    sample(anchored_config["runs"], args.samples)
    dump_json(anchored_config, args.output)
    print("Configuration for anchored simulation run written")

    wf_info = f"# Run the o2dpg_sim_workflow.py --anchored-config {args.output} #"
    print("#" * len(wf_info) + "\n" + wf_info + "\n" + "#" * len(wf_info))


    return 0


def main():

    parser = argparse.ArgumentParser(description='Prepare configuration for anchored simulation run')
    parser.add_argument("--output", "-o", help="where to write the JSON with SOR and EOR mapped to run numbers", default="config_anchored_mc.json")
    parser.add_argument("--run-numbers", dest="run_numbers", nargs="+", type=int, help="run numbers to anchor to", required=True)
    parser.add_argument("--samples", type=int, help="requested sampling", default=1)
    parser.add_argument("--lumi-fraction", dest="lumi_fraction", type=float, help="luminosity fraction to simulate, in [0, 1]", default=1)
    parser.add_argument("--tag", help="tag for this production", required=True)
    parser.add_argument("--ccdb-url", dest="ccdb_url", help="CCDB access RUL", default="http://alice-ccdb.cern.ch:8080")

    args = parser.parse_args()
    return mc_prod(args)

if __name__ == "__main__":
  sys.exit(main())
