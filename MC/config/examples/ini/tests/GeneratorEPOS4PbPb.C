int External()
{
  std::string path{"o2sim_Kine.root"};
  // Check that file exists, can be opened and has the correct tree
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

  // Check if all events are filled
  auto nEvents = tree->GetEntries();
  for (Long64_t i = 0; i < nEvents; ++i)
  {
    tree->GetEntry(i);
    if (tracks->empty())
    {
      std::cerr << "Empty entry found at event " << i << "\n";
      return 1;
    }
  }
  // Check if there is 1 event, as customly set in the ini file
  // Lead-Lead collisions with hydro and hadronic cascade are very slow to simulate
  if (nEvents != 1)
  {
    std::cerr << "Expected 1 event, got " << nEvents << "\n";
    return 1;
  }
  // check if each event has two lead ions with 557440 (208*5360) GeV of energy
  for (int i = 0; i < nEvents; i++)
  {
    auto check = tree->GetEntry(i);
    int count = 0;
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      double energy = track.GetEnergy();
      // Check if lead ion track energy is approximately equal to 557440 GeV (a tolerance of 50 MeV is considered, straight equality does not work due to floating point precision)
      if (std::abs(energy - 557440) < 5e-2 && track.GetPdgCode() == 1000822080)
      {
        count++;
      }
    }
    if (count < 2)
    {
      std::cerr << "Event " << i << " has less than 2 lead ions at 557440 GeV\n";
      return 1;
    }
  }
  return 0;
}