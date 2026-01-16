int Hybrid()
{
  std::string path{"o2sim_Kine.root"};
  TFile file(path.c_str(), "READ");
  if (file.IsZombie())
  {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }
  auto tree = (TTree *)file.Get("o2sim");
  if (!tree)
  {
    std::cerr << "Cannot find tree 'o2sim' in file " << path << "\n";
    return 1;
  }
  // Get the MCTrack branch
  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);
  // Check if processes with ID 42 are available
  const int processID = 42; // Performance test particle custom process ID
  int nEvents = tree->GetEntries();
  short int count_perf = 0;
  bool flag = false;
  for (int i = 0; i < nEvents; i++)
  {
    tree->GetEntry(i);
    int nTracks = tracks->size();
    count_perf = 0;
    for (auto &track : *tracks)
    {
      const auto &process = track.getProcess();
      if (process == processID)
      {
        flag = true;
        // No need to continue checking other tracks in the event
        break;
      }
    }
    if (flag == true)
    {
      count_perf++;
      flag = false;
    }
  }
  if (count_perf == 0)
  {
    std::cerr << "No performance test particles found in the events\n";
    return 1;
  } else if (count_perf > nEvents) {
    std::cerr << "More performance test flagged events than generated events\n";
    return 1;
  }
  file.Close();
  return 0;
}