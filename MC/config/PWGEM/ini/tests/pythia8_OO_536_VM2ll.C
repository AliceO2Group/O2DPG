int External() {
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
  // check if each event has at least two oxygen ions
  for (int i = 0; i < nEvents; i++)
  {
    auto check = tree->GetEntry(i);
    int count = 0;
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      if (track.GetPdgCode() == 1000080160)
      {
        count++;
      }
    }
    if (count < 2)
    {
      std::cerr << "Event " << i << " has less than 2 oxygen ions\n";
      return 1;
    }
  }

  return 0;
}

//int Pythia8()  
//{  
//    return External();
//}
