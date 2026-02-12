int External() 
{
  std::string path{"o2sim_Kine.root"};

  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  auto tree = (TTree *)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }

  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);
  auto nEvents = tree->GetEntries();
  int nTracks = 0;
  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    nTracks += tracks->size();
  }

  const int meanNTracksPerEvent = nTracks / nEvents;

  // Expecting only events with a 0-10% centrality
  // 0-100%  gives a mean of ~1350

  if (meanNTracksPerEvent < 1300) {
    return 1;
  }

  return 0;
}