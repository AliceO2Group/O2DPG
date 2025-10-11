import sys
#import shutil
#import os
#from pathlib import Path
import ROOT

"""
python $O2DPG/UTILS/AO2DQuery/AO2Dquery_utils.py  AO2D_Derived_Merged.root $(find /lustre/alice/users/rverma/NOTESData/alice-tpc-notes/Downsampled -iname AO2D_Derived.root| head -n 10 )
"""

def merge_root_directories_with_suffix(output_file, input_files):
    fout = ROOT.TFile(output_file, "RECREATE")

    for i, fname in enumerate(input_files):
        fin = ROOT.TFile.Open(fname)
        if not fin or fin.IsZombie():
            print(f"Warning: Could not open {fname}")
            continue

        for key in fin.GetListOfKeys():
            dname = key.GetName()
            if not dname.startswith("DF"):
                continue

            src_dir = fin.Get(dname)
            new_dname = f"{dname}__{i}"  # Add suffix

            fout.cd()
            fout.mkdir(new_dname)
            fout.cd(new_dname)

            for subkey in src_dir.GetListOfKeys():
                obj_name = subkey.GetName()
                obj = src_dir.Get(obj_name)

                # Clone tree properly
                if obj.InheritsFrom("TTree"):
                    cloned = obj.CloneTree(-1)  # deep copy all entries
                    cloned.SetName(obj_name)
                    cloned.Write()
                else:
                    obj.Write()

        fin.Close()
    fout.Close()

if __name__ == "__main__":
    output = sys.argv[1]
    inputs = sys.argv[2:]
    merge_root_directories_with_suffix(output, inputs)
