# Set of python modules/util functions for the MC-to-DATA embedding
# Mostly concerning extraction of MC collision context from existing data AO2D.root

import ROOT
import uproot
import pandas as pd
import re
from ROOT import o2 # for CCDB
import argparse
import sys

class lhc_constants:
    LHCMaxBunches = 3564                            # max N bunches
    LHCRFFreq = 400.789e6                           # LHC RF frequency in Hz
    LHCBunchSpacingNS = 10 * 1.e9 / LHCRFFreq       # bunch spacing in ns (10 RFbuckets)
    LHCOrbitNS = LHCMaxBunches * LHCBunchSpacingNS  # orbit duration in ns
    LHCRevFreq = 1.e9 / LHCOrbitNS                  # revolution frequency
    LHCBunchSpacingMUS = LHCBunchSpacingNS * 1e-3   # bunch spacing in \mus (10 RFbuckets)
    LHCOrbitMUS = LHCOrbitNS * 1e-3

def thin_AO2D_file(input_file):
    """
    A function to thin an existing AO2D file by just keeping a single DF_ folder
    """

    # Open the input ROOT file
    infile = ROOT.TFile.Open(input_file, "READ")

    # Find the first TDirectory starting with "DF_"
    df_dir = None
    dir_name = ""
    for key in infile.GetListOfKeys():
        name = key.GetName()
        if name.startswith("DF_"):
           # Access the TDirectory
           df_dir = infile.Get(name)
           dir_name = name
           break

    if not df_dir:
        raise RuntimeError("No TDirectory starting with 'DF_' found.")

    # Open the output file (create if not exist)
    output_file = "AO2D_reduced_" + str(dir_name) + ".root"
    outfile = ROOT.TFile.Open(output_file, "RECREATE")

    # Create the same directory structure in the output file
    df_dir_copy = outfile.mkdir(dir_name)

    # Move to the newly created directory
    df_dir_copy.cd()

    # Loop over the keys (trees) inside the "DF_" directory and copy them
    for key in df_dir.GetListOfKeys():
        obj = df_dir.Get(key.GetName())
        if isinstance(obj, ROOT.TTree):  # Check if it's a TTree
            # Clone the tree and write it to the corresponding directory in the output file
            obj.CloneTree(-1).Write(key.GetName(), ROOT.TObject.kOverwrite)  # Copy the tree

    # Now handle the metaData;1 key (TMap) in the top-level directory
    meta_data = infile.Get("metaData")
    if meta_data:
        if isinstance(meta_data, ROOT.TMap):
            copied_meta_data = meta_data.Clone()
            outfile.cd()  # Make sure we're at the top-level in the output file
            outfile.WriteObject(meta_data, "metaData")

            # Iterate over the map
            iter = meta_data.MakeIterator()
            entry = iter.Next()
            while entry:
                key = entry
                value = meta_data.GetValue(key)

                # Convert TObjString to Python string
                key_str = key.GetName()
                value_str = value.GetName() if value else "None"
                print(f"{key_str}: {value_str}")
                entry = iter.Next()

    # Close the files
    outfile.Close()
    infile.Close()

    print(f"Copied all trees from TDirectory '{dir_name}' to '{output_file}'.")


def retrieve_Aggregated_RunInfos(run_number):
    """
    Retrieves the aggregated runinfo object ... augmented with the number of timeframes
    """
    runInfo = o2.parameters.AggregatedRunInfo.buildAggregatedRunInfo(o2.ccdb.BasicCCDBManager.instance(), run_number)
    detList = o2.detectors.DetID.getNames(runInfo.grpECS.getDetsReadOut())
    assert (run_number == runInfo.runNumber)
    assert (run_number == runInfo.grpECS.getRun())
    
    run_info = {"SOR" : runInfo.sor,
            "EOR" : runInfo.eor,
            "FirstOrbit" : runInfo.orbitSOR,
            "LastOrbit" : runInfo.orbitEOR,
            "OrbitReset" : runInfo.orbitReset,
            "OrbitsPerTF" : int(runInfo.orbitsPerTF),
            "detList" : detList}

    # update num of timeframes
    # figure out how many timeframes fit into this run range
    # take the number of orbits per timeframe and multiply by orbit duration to calculate how many timeframes fit into this run
    time_length_inmus = 1000 * (run_info["EOR"] - run_info["SOR"])
    ntimeframes = time_length_inmus / (run_info["OrbitsPerTF"] * lhc_constants.LHCOrbitMUS)
    run_info["ntimeframes"] = ntimeframes

    return run_info


def get_bc_with_timestamps(bc_data, run_info):
    """
    bc_data is a pandas df containing the AO2D basic bunch crossing data.
    Returns the bc table with additional information on timeframeID etc.
    """
    
    # add a new column to the bc table dynamically
    # this is the time in mu s
    bc_data["timestamp"] = run_info["OrbitReset"] + (bc_data["fGlobalBC"] * lhc_constants.LHCBunchSpacingMUS).astype("int64")
    bc_data["timeframeID"] = ((bc_data["fGlobalBC"] - (run_info["FirstOrbit"] * lhc_constants.LHCMaxBunches)) / (lhc_constants.LHCMaxBunches * run_info["OrbitsPerTF"])).astype("int64")
    bc_data["orbit"] = (bc_data["fGlobalBC"] // lhc_constants.LHCMaxBunches).astype("int64")
    bc_data["bc_within_orbit"] = (bc_data["fGlobalBC"] % lhc_constants.LHCMaxBunches).astype("int64")
    return bc_data


def get_timeframe_structure(filepath, run_info, max_folders=1, include_dataframe = False, folder_filter=None):
    """
    run_info: The aggregated run_info object for this run
    """
    def find_tree_key(keys, pattern):
        for key in keys:
            key_clean = key
            if re.search(pattern, key_clean, re.IGNORECASE):
                return key_clean
        return None

    file = uproot.open(filepath)
    raw_keys = file.keys()
        
    folders = { k.split("/")[0] : 1 for k in raw_keys if "O2bc_001" in k }
    folders = [ k for k in folders.keys() ] 
    folders = folders[:max_folders]  

    print ("have ", len(raw_keys), f" in file {filepath}")

    merged = {} # data containers per file
    for folder in folders:
        if folder_filter != None and folder != folder_filter:
            continue
        #print (f"Looking into {folder}")
        
        # Find correct table names using regex
        bc_key = find_tree_key(raw_keys, f"^{folder}/O2bc_001")
        bc_data = file[bc_key].arrays(library="pd")

        # collision data
        coll_key = find_tree_key(raw_keys, f"^{folder}/O2coll.*_001")
        coll_data = file[coll_key].arrays(library="pd")
        
        # extend the data
        bc_data = get_bc_with_timestamps(bc_data, run_info)
        
        # do the splice with collision data
        bc_data_coll = bc_data.iloc[coll_data["fIndexBCs"]].reset_index(drop=True)
        # this is the combined table containing collision data associated to bc and time information
        combined = pd.concat([bc_data_coll, coll_data], axis = 1)
        
        # do the actual timeframe structure calculation; we only take collisions with a trigger decision attached
        triggered = combined[combined["fTriggerMask"] != 0]
        timeframe_structure = triggered.groupby('timeframeID').apply(
        lambda g: list(zip(g['fGlobalBC'], g['fPosX'], g['fPosY'], g['fPosZ'], g['orbit'], g['bc_within_orbit'], g['fCollisionTime']))
        ).reset_index(name='position_vectors')
        
        folderkey = folder + '@' + filepath
        merged[folderkey] = timeframe_structure # data per folder
        if include_dataframe:
            merged["data"] = combined
    
    # annotate which timeframes are available here and from which file
    return merged


def fetch_bccoll_to_localFile(alien_file, local_filename):
  """
  A function to remotely talk to a ROOT file ... and fetching only
  BC and collision tables for minimal network transfer. Creates a ROOT file locally
  of name local_filename.

  Returns True if success, otherwise False
  """

  # make sure we have a TGrid connection
  # Connect to AliEn grid
  if not ROOT.gGrid:
    ROOT.TGrid.Connect("alien://")

  if not ROOT.gGrid:
    print (f"Not TGrid object found ... aborting")
    return False

  # Open the remote file via AliEn
  infile = ROOT.TFile.Open(alien_file, "READ")
  if not infile or infile.IsZombie():
    raise RuntimeError(f"Failed to open {alien_file}")
    return False

  # Output local file
  outfile = ROOT.TFile.Open(local_filename, "RECREATE")

  # List of trees to copy
  trees_to_copy = ["O2bc_001", "O2collision_001"]

  # Loop over top-level keys to find DF_ folders
  for key in infile.GetListOfKeys():
    obj = key.ReadObj()
    if obj.InheritsFrom("TDirectory") and key.GetName().startswith("DF_"):
        df_name = key.GetName()
        df_dir = infile.Get(df_name)
        
        # Create corresponding folder in output file
        out_df_dir = outfile.mkdir(df_name)
        out_df_dir.cd()

        # Copy only specified trees if they exist
        for tree_name in trees_to_copy:
            if df_dir.GetListOfKeys().FindObject(tree_name):
                tree = df_dir.Get(tree_name)
                cloned_tree = tree.CloneTree(-1)  # copy all entries
                cloned_tree.Write(tree_name)

        outfile.cd()  # go back to top-level for next DF_

  # Close files
  outfile.Close()
  infile.Close()
  return True


def convert_to_digicontext(aod_timeframe=None, timeframeID=-1):
    """
    converts AOD collision information from AO2D to collision context
    which can be used for MC
    """
    # we create the digitization context object
    digicontext=o2.steer.DigitizationContext()
    
    # we can fill this container
    parts = digicontext.getEventParts()
    # we can fill this container
    records = digicontext.getEventRecords()
    # copy over information
    maxParts = 1
    
    entry = 0
    vertices = ROOT.std.vector("o2::math_utils::Point3D<float>")()
    vertices.resize(len(aod_timeframe))
    
    colindex = 0
    for colindex, col in enumerate(aod_timeframe):
        # we make an event interaction record
        pvector = ROOT.std.vector("o2::steer::EventPart")()
        pvector.push_back(o2.steer.EventPart(0, colindex))
        parts.push_back(pvector)
        
        orbit = col[4]
        bc_within_orbit = col[5]
        interaction_rec = o2.InteractionRecord(bc_within_orbit, orbit)
        col_time_relative_to_bc = col[6] # in NS
        time_interaction_rec = o2.InteractionTimeRecord(interaction_rec, col_time_relative_to_bc)
        records.push_back(time_interaction_rec)
        vertices[colindex].SetX(col[1])
        vertices[colindex].SetY(col[2])
        vertices[colindex].SetZ(col[3])
        
    digicontext.setInteractionVertices(vertices)
    digicontext.setNCollisions(vertices.size())
    digicontext.setMaxNumberParts(maxParts)
    
    # set the bunch filling ---> NEED to fetch it from CCDB
    # digicontext.setBunchFilling(bunchFillings[0]);
    
    prefixes = ROOT.std.vector("std::string")();
    prefixes.push_back("sgn")
    
    digicontext.setSimPrefixes(prefixes);
    digicontext.printCollisionSummary();
    digicontext.saveToFile(f"collission_context_{timeframeID}.root")


def process_data_AO2D(file_name, run_number, upper_limit = -1):
    """
    Creates all the collision contexts 
    """
    timeframe_data = []

    local_filename = "local.root"
    fetch_bccoll_to_localFile(file_name, local_filename)

    # fetch run_info object
    run_info = retrieve_Aggregated_RunInfos(run_number)
    merged = get_timeframe_structure(local_filename, run_info, max_folders=1000)
    print ("Got " + str(len(merged)) + " datasets")
    timeframe_data.append(merged)

    counter = 0
    for d in timeframe_data:
        for key in d:
            result = d[key]
            for index, row in result.iterrows():
                if upper_limit >= 0 and counter >= upper_limit:
                    break
                tf = row['timeframeID']
                cols = row['position_vectors']
                convert_to_digicontext(cols, tf)
                counter = counter + 1


def main():
    parser = argparse.ArgumentParser(description='Extracts collision contexts from reconstructed AO2D')

    parser.add_argument("--run-number", type=int, help="Run number to anchor to", required=True)
    parser.add_argument("--aod-file", type=str, help="Data AO2D file (can be on AliEn)", required=True)
    parser.add_argument("--limit", type=int, default=-1, help="Upper limit of timeframes to be extracted")
    args = parser.parse_args()

    process_data_AO2D(args.aod_file, args.run_number, args.limit)

if __name__ == "__main__":
  sys.exit(main())
