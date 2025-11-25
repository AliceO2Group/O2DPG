int External() {
  std::string path{"o2sim_Kine.root"};
  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }
  auto tree = (TTree *)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree 'o2sim' in file " << path << "\n";
    return 1;
  }
  // Get the MCTrack branch
  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);
  // Check if processes with ID 42 are available
  // And are 100 per event
  const int processID = 42; // Performance test particle custom process ID
  int nEvents = tree->GetEntries();
  short int count_perf = 0;
  unsigned short int expSig = 100; // set by default in the ini file
  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    int nTracks = tracks->size();
    count_perf = 0;
    for (auto &track : *tracks)
    {
      const auto& process = track.getProcess();
      if (process == 42)
      {
        count_perf++;
      }
    }
    if (count_perf != expSig)
    {
      std::cerr << "Event " << i << ": Expected " << expSig << " performance test particles, found " << count_perf << "\n";
      return 1;
    }
  }

  file.Close();
  return 0;
}