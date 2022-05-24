void PWGMMMDnDeta(const char* inputFiles, const char* outDir)
{
  // filenames are given as one string where the file names are separated by ","
  std::stringstream toSplit(inputFiles);
  std::string token;
  std::vector<std::string> tokenList;
  std::string thisFile;

  while (std::getline(toSplit, token, ',')) {
    if (token.find("AnalysisResults.root") != std::string::npos) {
      thisFile = token;
      break;
    }
  }

  if (thisFile.empty()) {
    // nothing to post-process
    return;
  }
  TFile f(thisFile.c_str(), "UPDATE");
  if (f.IsZombie()) {
    std::cout << "Cannot open file " << thisFile << " for post-processing\n";
    return;
  }
  auto hPT = (TH1*)f.Get("pseudorapidity-density/Tracks/Control/PtEfficiency");
  auto hPTGen = (TH1*)f.Get("pseudorapidity-density/Tracks/Control/PtGen");
  hPT->SetDirectory(nullptr);
  hPTGen->SetDirectory(nullptr);
  auto hPTTrackingEff = (TH1*)hPT->Clone("trackingEfficiency");
  hPTTrackingEff->SetDirectory(nullptr);

  hPTTrackingEff->Divide(hPTTrackingEff, hPTGen, 1, 1, "b");
  hPTTrackingEff->SetTitle("tracking efficiency");

  auto d = f.mkdir("O2DPG-post-processing");
  d->WriteTObject(hPTTrackingEff);
  f.Write();
  f.Close();
}
