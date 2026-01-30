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
  // Heavy-ion collisions with hydro and hadronic cascade are very slow to simulate
  if (nEvents != 1)
  {
    std::cerr << "Expected 1 event, got " << nEvents << "\n";
    return 1;
  }

  // ---- Oxygen-Oxygen parameters ----
  constexpr int kOxygenPDG = 1000080160;   // O-16 ion
  constexpr double kEnucleon = 5360.;      // GeV per nucleon
  constexpr int kA = 16;                   // Oxygen mass number
  constexpr double kOxygenEnergy = kA * kEnucleon / 2.0; // 85760 / 2 GeV

  // Check if each event has two oxygen ions at expected energy
  for (int i = 0; i < nEvents; i++)
  {
    tree->GetEntry(i);
    int count = 0;

    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      double energy = track.GetEnergy();

      // 50 MeV tolerance (floating point safety)
      if (std::abs(energy - kOxygenEnergy) < 5e-2 &&
          track.GetPdgCode() == kOxygenPDG)
      {
        count++;
      }
    }

    if (count < 2)
    {
      std::cerr << "Event " << i
                << " has less than 2 oxygen ions at "
                << kOxygenEnergy << " GeV\n";
      return 1;
    }
  }

  return 0;
}
