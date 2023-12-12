#!/usr/bin/env python3
import ROOT
import argparse

parser = argparse.ArgumentParser(description='Check if 2 ROOT files are binary compatible',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-f1','--file1', help='First ROOT TFile', required=True)
parser.add_argument('-f2','--file2', help='Second ROOT TFile', required=True)
args = parser.parse_args()

def get_total_branch_list(tree):
    branches = []

    # Function to recursively get branches
    def get_branches_recursive(branch):
        branches.append(branch)
        sub_branches = branch.GetListOfBranches()

        if sub_branches:
            for sub_branch in sub_branches:
                get_branches_recursive(sub_branch)

    # Get top-level branches of the tree
    top_level_branches = tree.GetListOfBranches()

    # Traverse recursively through branches
    for branch in top_level_branches:
        get_branches_recursive(branch)

    return branches


def compare_branches(obj1, obj2):
    # Check if the object classes match
    if obj1.IsA() != obj2.IsA():
      print("Type doesn't match")
      return False

    # Check if the byte content is the same
    if obj1.GetTitle() != obj2.GetTitle():
      print ("Title doesn't match")
      return False

        # Convert objects to TBuffer to compare their byte content
        #buffer1 = ROOT.TBuffer(ROOT.TBuffer.EMode.kWrite, 10000)
        #buffer2 = ROOT.TBuffer(ROOT.TBuffer.EMode.kWrite, 10000)

        #obj1.Streamer(buffer1)
        #obj2.Streamer(buffer2)
    # checking branch
    print ("Checking branch " + obj1.GetTitle())
    if obj1.GetTotBytes() != obj2.GetTotBytes():
      print ("Bytecount different")
      return False


# compare 2 TTree objects
def compare_trees(tree1, tree2):
    branches1 = get_total_branch_list(tree1)
    branches2 = get_total_branch_list(tree2)

    # branch count needs to be same
    if len(branches1) != len(branches2):
      return False

    # we do not impose same branch order so we build 2 hashsets containing tuples
    # of (branchname, totalsize)

    set1 = set()
    for br in branches1:
      # Print key name and class name
      #print("Key: ", br.GetName())
      #print("Class: ", br.ClassName())
      #print("BC: ", str(br.GetTotalSize()))
      #print("---------------")
      
      totals = 0
      for entry in range(br.GetEntries()):
        totals = totals + br.GetEntry(entry)
      set1.add((br.GetName(), totals, br.GetEntries()))

    set2 = set()
    for br in branches2:
      totals = 0
      for entry in range(br.GetEntries()):
        totals = totals + br.GetEntry(entry)
      set2.add((br.GetName(), totals, br.GetEntries()))

    inters = set1.intersection(set2)
    #print (inters)
    symdiff = (set1.symmetric_difference(set2))
    if (len(symdiff) > 0):
      print (symdiff)
    return len(symdiff) == 0
 
def compare_root_files(file1, file2):
    # Open the ROOT files
    tfile1 = ROOT.TFile.Open(file1)
    tfile2 = ROOT.TFile.Open(file2)

    # Get the list of keys (TKeys) in the ROOT files
    keys1 = tfile1.GetListOfKeys()
    keys2 = tfile2.GetListOfKeys()

    # Check if the number of keys is the same
    if keys1.GetEntries() != keys2.GetEntries():
        return False

    # Iterate through the keys and compare byte content
    # check keys
    success = True
    for key1, key2 in zip(keys1, keys2):
        obj1 = key1.ReadObj()
        obj2 = key2.ReadObj()
        
        isTree1 = isinstance(obj1, ROOT.TTree)
        isTree2 = isinstance(obj2, ROOT.TTree)
        if isTree1 != isTree2:
          success = False

        elif isTree1 and isTree2:
          success = success and compare_trees(obj1, obj2)

    # Close the files
    tfile1.Close()
    tfile2.Close()

    return success

result = compare_root_files(args.file1, args.file2)
if result:
    print("Byte content of the two ROOT files is the same.", args.file1, args.file2)
else:
    print("Byte content of the two ROOT files is different.", args.file1, args.file2)
