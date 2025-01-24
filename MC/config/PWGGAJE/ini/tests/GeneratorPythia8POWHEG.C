int External() {
  std::string path{"o2sim_Kine.root"};
  std::ifstream powhegconf("powheg.input");
  if (!powhegconf) {
    std::cerr << "POWHEG configuration file not found\n";
    return 1;
  }
  std::ifstream powhegout("pwgevents.lhe");
  if (!powhegout) {
    std::cerr << "POWHEG output file not found\n";
    return 1;
  }
  powhegout.close();

  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  auto tree = (TTree *)file.Get("o2sim");
  auto nEvents = tree->GetEntries();
  std::string line;
  int nevpowheg = -1;
  while (std::getline(powhegconf, line)) {
    if (line.find("numevts") != std::string::npos) {
      // Read the number right after numevts
      auto pos = line.find("numevts");
      nevpowheg = std::stoi(line.substr(pos + 7));
      if (nevpowheg != nEvents) {
        std::cerr << "Number of events in POWHEG configuration file " << nevpowheg
                  << " does not match the simulated number of events "
                  << nEvents << "\n";
        return 1;
      }
    }
  }
  if (nevpowheg == -1) {
    std::cerr << "Number of events not found in POWHEG configuration file\n";
    return 1;
  }
  powhegconf.close();
  file.Close();

  return 0;
}