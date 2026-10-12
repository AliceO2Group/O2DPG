int External()
{
  std::string path{"o2sim_Kine.root"};
  std::vector<int> possiblePDGs = {1000010020, -1000010020};

  int nPossiblePDGs = possiblePDGs.size();

  TFile file(path.c_str(), "READ");
  if (file.IsZombie())
  {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  auto tree = (TTree *)file.Get("o2sim");
  if (!tree)
  {
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }
  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  std::vector<int> injectedPDGs;

  auto nEvents = tree->GetEntries();
  for (int i = 0; i < nEvents; i++)
  {
    auto check = tree->GetEntry(i);
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      auto pdg = track.GetPdgCode();
      auto it = std::find(possiblePDGs.begin(), possiblePDGs.end(), pdg);
      if (it != possiblePDGs.end() && track.isPrimary())  // found
      {
        injectedPDGs.push_back(pdg);
      }
    }
  }
  std::cout << "--------------------------------\n";
  std::cout << "# Events: " << nEvents << "\n";
  if(injectedPDGs.empty()){
    std::cerr << "No injected particles\n";
    return 1; // At least one of the injected particles should be generated
  }
  for (int i = 0; i < nPossiblePDGs; i++)
  {
    std::cout << "# Injected nuclei \n";
    std::cout << possiblePDGs[i] << ": " << std::count(injectedPDGs.begin(), injectedPDGs.end(), possiblePDGs[i]) << "\n";
  }
  return 0;
}
