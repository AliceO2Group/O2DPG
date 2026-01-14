int Hybrid()
{
  std::string path{"o2sim_Kine.root"};

  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  auto tree = (TTree*)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }

  std::vector<o2::MCTrack>* tracks{};
  o2::MCEventHeader* header{};

  tree->SetBranchAddress("MCTrack", &tracks);
  tree->SetBranchAddress("MCEventHeader.", &header);

  int nEvents = tree->GetEntries();

  int nMB = 0;
  int nHard = 0;

  long long multMB = 0;
  long long multHard = 0;

  for (int i = 0; i < nEvents; ++i) {
    tree->GetEntry(i);

    int genId = header->getGeneratorId();
    int mult = tracks->size();

    if (genId == 0) {
      nMB++;
      multMB += mult;
    } else if (genId == 1) {
      nHard++;
      multHard += mult;
    }
  }

  std::cout << "--------------------------------\n";
  std::cout << "# Events total: " << nEvents << "\n";
  std::cout << "# MB events   : " << nMB << "\n";
  std::cout << "# Hard events : " << nHard << "\n";

  if (nHard == 0 || nMB == 0) {
    std::cerr << "One of the generators was never used\n";
    return 1;
  }

  std::cout << "Avg multiplicity MB   : "
            << double(multMB) / nMB << "\n";
  std::cout << "Avg multiplicity Hard : "
            << double(multHard) / nHard << "\n";

  if (multHard <= multMB) {
    std::cerr << "Hard events not harder than MB ones\n";
    return 1;
  }

  return 0;
}
