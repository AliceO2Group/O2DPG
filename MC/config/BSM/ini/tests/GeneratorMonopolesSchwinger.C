#include "SimulationDataFormat/MonopoleParticles.h"

int External()
{
  // the species codes come from O2 itself, so this test cannot drift from the simulation
  const int pdgMonopole = o2::sim::MonopolePdgSymm;
  const double momentumTolerance = 1e-6; // relative, on the momentum sum of the pairs

  // Note on the mass: it is deliberately not checked here. MCTrack stores only the momentum,
  // and MCTrack::GetEnergy() rebuilds the energy as sqrt(m^2 + p^2) with m taken from the PDG
  // table of *this* process, so any mass derived from the tracks is the table value and not
  // what the generator used - the check would always pass. The mass is enforced on the
  // generator side instead: GeneratorMonopoles refuses to start when its configured mass
  // disagrees with G4.monopoleMass, which the ini file sets.

  std::string path{"o2sim_Kine.root"};
  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }
  auto tree = (TTree*)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree 'o2sim' in file " << path << "\n";
    return 1;
  }
  std::vector<o2::MCTrack>* tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  const auto nEvents = tree->GetEntries();
  if (nEvents == 0) {
    std::cerr << "No events found\n";
    return 1;
  }

  for (Long64_t i = 0; i < nEvents; ++i) {
    tree->GetEntry(i);
    int nMonopoles = 0;
    int nAntiMonopoles = 0;
    double sumPx = 0., sumPy = 0., sumPz = 0., sumP = 0.;
    for (const auto& track : *tracks) {
      const auto pdg = track.GetPdgCode();
      if (!o2::sim::isMonopole(pdg) || std::abs(pdg) != pdgMonopole) {
        std::cerr << "Found unexpected PDG code " << pdg << " in event " << i << "\n";
        return 1;
      }
      (pdg > 0 ? nMonopoles : nAntiMonopoles)++;
      const double px = track.Px(), py = track.Py(), pz = track.Pz();
      const double p2 = px * px + py * py + pz * pz;
      sumPx += px;
      sumPy += py;
      sumPz += pz;
      sumP += std::sqrt(p2);
    }
    if (nMonopoles < 1 || nAntiMonopoles < 1) {
      std::cerr << "Event " << i << " has no monopole pair: " << nMonopoles << " monopole(s) and "
                << nAntiMonopoles << " antimonopole(s)\n";
      return 1;
    }
    if (nMonopoles != nAntiMonopoles) {
      std::cerr << "Event " << i << " is not made of pairs: " << nMonopoles << " monopole(s) and "
                << nAntiMonopoles << " antimonopole(s)\n";
      return 1;
    }
    // the Schwinger configuration has no pair recoil, so each pair, and hence the event, has
    // vanishing total momentum
    const double imbalance = std::sqrt(sumPx * sumPx + sumPy * sumPy + sumPz * sumPz);
    if (sumP <= 0. || imbalance > momentumTolerance * sumP) {
      std::cerr << "Monopoles in event " << i << " are not back-to-back: momentum imbalance "
                << imbalance << " GeV/c for a total momentum of " << sumP << " GeV/c\n";
      return 1;
    }
  }

  file.Close();
  return 0;
}
