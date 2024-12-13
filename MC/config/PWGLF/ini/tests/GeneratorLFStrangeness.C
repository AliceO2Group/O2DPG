int External()
{
  std::string path{"o2sim_Kine.root"};
  // std::string path{"bkg_Kine.root"};
  std::vector<int> numberOfInjectedSignalsPerEvent = {};
  std::vector<int> injectedPDGs = {};
  std::string particleList = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/strangeparticlelist.gun";
  particleList = gSystem->ExpandPathName(particleList.c_str());

  std::ifstream inputFile(particleList.c_str(), ios::in);
  if (inputFile.is_open()) {
    std::string l;
    int n = 0;
    while (getline(inputFile, l)) {
      TString line = l;
      line.Strip(TString::kBoth, ' ');
      std::cout << n++ << " '" << line << "'" << std::endl;
      if (line.IsNull() || line.IsWhitespace()) {
        continue;
      }

      if (line.BeginsWith("#")) {
        std::cout << "Skipping\n";
        continue;
      }
      auto* arr = line.Tokenize(" ");
      injectedPDGs.push_back(atoi(arr->At(0)->GetName()));
      numberOfInjectedSignalsPerEvent.push_back(atoi(arr->At(1)->GetName()));
    }
  } else {
    std::cout << "Cannot open file " << particleList << "\n";
    return 1;
  }

  auto nInjection = injectedPDGs.size();

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
  tree->SetBranchAddress("MCTrack", &tracks);

  std::vector<int> nSignal;
  for (int i = 0; i < nInjection; i++) {
    nSignal.push_back(0);
  }

  auto nEvents = tree->GetEntries();
  for (int i = 0; i < nEvents; i++) {
    auto check = tree->GetEntry(i);
    std::cout << "Event " << i << "/" << tree->GetEntries() << std::endl;
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack) {
      auto track = tracks->at(idxMCTrack);
      auto pdg = track.GetPdgCode();
      auto it = std::find(injectedPDGs.begin(), injectedPDGs.end(), pdg);
      std::cout << "  particle " << idxMCTrack << " pdg: " << pdg << " getHepMCStatusCode " << getHepMCStatusCode(track.getStatusCode()) << " getGenStatusCode " << getGenStatusCode(track.getStatusCode()) << std::endl;
      std::cout << "           getMotherTrackId " << track.getMotherTrackId() << " getSecondMotherTrackId " << track.getSecondMotherTrackId() << " " << std::endl;
      int index = std::distance(injectedPDGs.begin(), it); // index of injected PDG
      if (!getHepMCStatusCode(track.getStatusCode())) {
        continue;
      }
      if (it != injectedPDGs.end()) // found
      {
        // count signal PDG
        nSignal[index]++;
      }
    }
  }
  std::cout << "--------------------------------\n";
  std::cout << "# Events: " << nEvents << "\n";
  for (int i = 0; i < nInjection; i++) {
    std::cout << "# Injected particle \n";
    std::cout << injectedPDGs[i] << ": " << nSignal[i] << "\n";
    if (nSignal[i] == 0) {
      std::cerr << "No generated: " << injectedPDGs[i] << "\n";
      // return 1; // At least one of the injected particles should be generated
    }
  }
  return 0;
}

void GeneratorLFStrangeness() { External(); }