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

  // Check if there are 2 events, as customly set in the ini file (NEV_TEST)
  if (nEvents != 2)
  {
    std::cerr << "Expected 2 events, got " << nEvents << "\n";
    return 1;
  }

  // ---- proton-Oxygen parameters ----
  // The .optns file boosts the output from the symmetric NN CM frame (where
  // each nucleon carries ecms/2) to the real asymmetric p/O beam frame via
  // "hepmc_rapcms <kRapcms>", so E_p = (ecms/2)*exp(+kRapcms) and
  // E_O-nucleon = (ecms/2)*exp(-kRapcms). Keep kRapcms in sync with the value
  // set in pO_962TeV_EPOS4.optns / pO_962TeV_EPOS4_hydro.optns.
  constexpr int kProtonPDG = 2212;
  constexpr int kOxygenPDG = 1000080160; // O-16 ion
  constexpr double kEcms = 9620.;        // GeV, sqrt(s_NN) as set in the .optns file
  constexpr double kRapcms = 0.346225;   // rapidity boost set via hepmc_rapcms
  constexpr int kA = 16;                 // Oxygen mass number
  const double kProtonEnergy = (kEcms / 2.0) * std::exp(kRapcms);            // boosted proton energy
  const double kOxygenEnergy = kA * (kEcms / 2.0) * std::exp(-kRapcms);      // total energy of the O-16 ion

  // Check if each event has one proton and one oxygen ion at expected energies
  for (int i = 0; i < nEvents; i++)
  {
    tree->GetEntry(i);
    int countProton = 0;
    int countOxygen = 0;

    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      double energy = track.GetEnergy();

      // 1 GeV tolerance (the rapcms boost is applied in single precision in EPOS4)
      if (std::abs(energy - kProtonEnergy) < 1. &&
          track.GetPdgCode() == kProtonPDG)
      {
        countProton++;
      }
      else if (std::abs(energy - kOxygenEnergy) < 1. &&
               track.GetPdgCode() == kOxygenPDG)
      {
        countOxygen++;
      }
    }

    if (countProton < 1)
    {
      std::cerr << "Event " << i
                << " has no proton beam particle at "
                << kProtonEnergy << " GeV\n";
      return 1;
    }

    if (countOxygen < 1)
    {
      std::cerr << "Event " << i
                << " has no oxygen ion at "
                << kOxygenEnergy << " GeV\n";
      return 1;
    }
  }

  return 0;
}
