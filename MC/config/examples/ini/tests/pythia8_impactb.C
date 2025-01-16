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

  o2::dataformats::MCEventHeader *mcheader = nullptr;
  tree->SetBranchAddress("MCEventHeader.", &mcheader);

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
  // Check if there are 100 events, as simulated in the o2dpg-test
  if (nEvents != 100)
  {
    std::cerr << "Expected 100 events, got " << nEvents << "\n";
    return 1;
  }
  // check if each event has two lead ions with the correct energy (based on Pythia simulation)
  // exits if the particle is not lead 208
  bool isvalid;
  for (int i = 0; i < nEvents; i++)
  {
    auto check = tree->GetEntry(i);
    int count = 0;
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      double energy = track.GetEnergy();
      // Check if track energy is right for the lead ions (a tolerance of 100 MeV is considered, straight equality does not work due to floating point precision)
      if (std::abs(energy - 547158) < 1e-1) // Lead ion energy is 547158 MeV
      {
        if (track.GetPdgCode() != 1000822080)
        {
          std::cerr << "Found 547158 GeV particle with pdgID " << track.GetPdgCode() << "\n";
          return 1;
        }
        count++;  
      }
    }
    if (count < 2)
    {
      std::cerr << "Event " << i << " has less than 2 lead ions at 547158 GeV\n";
      return 1;
    }
    // Check if event impact parameter is < 15 fm
    double impactParameter = mcheader->getInfo<double>(o2::dataformats::MCInfoKeys::impactParameter, isvalid);
    if (impactParameter > 15)
    {
      std::cerr << "Event " << i << " has impact parameter " << impactParameter << " fm outside range\n";
      return 1;
    }
  }
  return 0;
}