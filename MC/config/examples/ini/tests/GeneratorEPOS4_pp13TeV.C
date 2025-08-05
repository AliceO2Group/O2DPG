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
  // Check if there are 100 events, as simulated in the o2dpg-test
  if (nEvents != 100)
  {
    std::cerr << "Expected 100 events, got " << nEvents << "\n";
    return 1;
  }
  // check if each event has two protons with 6500 GeV of energy
  // exits if the particle is not a proton
  for (int i = 0; i < nEvents; i++)
  {
    auto check = tree->GetEntry(i);
    int count = 0;
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      double energy = track.GetEnergy();
      // Check if track energy is approximately equal to 6500 GeV (a tolerance of 65 keV is considered, straight equality does not work due to floating point precision)
      if (std::abs(energy - 6500) < 1e-4)
      {
        if (track.GetPdgCode() != 2212){
          std::cerr << "Found 6500 GeV particle with pdgID " << track.GetPdgCode() << "\n";
          return 1;
        }         
        count++;  
      }
    }
    if (count < 2)
    {
      std::cerr << "Event " << i << " has less than 2 protons at 6500 GeV\n";
      return 1;
    }
  }
  return 0;
}
