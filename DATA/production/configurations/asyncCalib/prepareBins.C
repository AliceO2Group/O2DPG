#include "TGrid.h"
#include "TFile.h"
#include "TTree.h"
#include <iostream>
#include <fstream>



void prepareBins(const char* listFiles, int nInputPerJob) {

  TGrid::Connect("alien");
  std::ifstream inputList(listFiles);
  uint64_t totEntries = 0;
  for (std::string fileName; getline(inputList, fileName);) {  
    TFile* f = TFile::Open(Form("%s", fileName.c_str()));
    if (f != 0x0) {
      TTree* t = (TTree*)f->Get("itpcc");
      totEntries += t->GetEntries();
    }
    else {
      std::cout << "The file " << fileName << " cannot be opened - we will miscount the entries" << std::endl;
    }
  }
  std::cout << "Found " << totEntries << " in total for the current run" << std::endl;
  if (nInputPerJob == -1) {
    std::cout << "Processing everything in one go" << std::endl;
    FILE *fptr = fopen("timeBins.log", "w");
    if (fptr == NULL) {
      printf("ERROR: Could not open file to write timBins!");
      return;
    }
    fprintf(fptr, "0 %lu", totEntries-1);
    fclose(fptr);
    return;
  }
  int ratio = totEntries / nInputPerJob;
  int module = totEntries % nInputPerJob;
  int nSubJobs = ratio;
  if (module != 0) {
    nSubJobs = ratio + 1;
  }
  FILE *fptr = fopen("timeBins.log", "w");
  if (fptr == NULL) {
    printf("ERROR: Could not open file to write timBins!");
    return;
  }
  int start = 0;
  std::cout << "We will have " << nSubJobs << " subjobs" << std::endl;
  for (int i = 0; i < nSubJobs - 1; ++i) {
    fprintf(fptr, "%d %d \n", start, start + nInputPerJob - 1);
    start += nInputPerJob;
  }
  fprintf(fptr, "%d %lu \n", start, totEntries - 1);
  fclose(fptr);
  return;

}
