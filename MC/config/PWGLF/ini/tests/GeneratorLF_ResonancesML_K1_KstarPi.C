// Test of the single-channel ML signal samples GeneratorLF_ResonancesML_*.ini (all collision systems) that redirect here.
// Every event carries exactly one injected parent (no gap); the parent and the intermediate resonances decayed by the
// generator must follow the forced chain (charge conjugated for the negative-PDG parent). Parents with a mother come
// from the underlying Pythia event, decay with the default table, and are only counted.
int External()
{
  const std::string path{"o2sim_Kine.root"};
  const int parentPDG{10323};
  const std::vector<int> daughtersOfPositive{313, 211};
  const std::map<int, std::vector<int>> intermediateDecaysOfPositive{{313, {321, -211}}};
  const std::set<int> selfConjugate{111, 113, 310};
  auto conjugate = [&](int pdg, int sign) { return (sign > 0 || selfConjugate.count(pdg)) ? pdg : -pdg; };
  auto sorted = [](std::vector<int> v) { std::sort(v.begin(), v.end()); return v; };

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

  int nEventsWrongParentCount{0}, nFromUnderlyingEvent{0}, nParents{0}, nNotDecayed{0}, nWrongDecay{0}, nIntermediates{0}, nWrongIntermediate{0};
  std::map<int, int> nParentsBySign;
  for (Long64_t i = 0; i < tree->GetEntries(); ++i) {
    tree->GetEntry(i);
    int nParentsInEvent{0};
    for (const auto& track : *tracks) {
      const int pdg = track.GetPdgCode();
      if (std::abs(pdg) != parentPDG) {
        continue;
      }
      if (track.getMotherTrackId() >= 0) {
        ++nFromUnderlyingEvent;
        continue;
      }
      ++nParentsInEvent;
      ++nParents;
      const int sign = pdg > 0 ? 1 : -1;
      ++nParentsBySign[sign];
      if (track.getFirstDaughterTrackId() < 0) {
        ++nNotDecayed;
        continue;
      }
      std::vector<int> expected, found;
      for (int d : daughtersOfPositive) {
        expected.push_back(conjugate(d, sign));
      }
      for (int j = track.getFirstDaughterTrackId(); j <= track.getLastDaughterTrackId(); ++j) {
        const auto& daughter = tracks->at(j);
        found.push_back(daughter.GetPdgCode());
        const auto it = intermediateDecaysOfPositive.find(sign > 0 ? daughter.GetPdgCode() : conjugate(daughter.GetPdgCode(), -1));
        if (it == intermediateDecaysOfPositive.end()) {
          continue;
        }
        ++nIntermediates;
        std::vector<int> expectedGrand, foundGrand;
        for (int g : it->second) {
          expectedGrand.push_back(conjugate(g, sign));
        }
        for (int k = daughter.getFirstDaughterTrackId(); k >= 0 && k <= daughter.getLastDaughterTrackId(); ++k) {
          foundGrand.push_back(tracks->at(k).GetPdgCode());
        }
        if (sorted(expectedGrand) != sorted(foundGrand)) {
          ++nWrongIntermediate;
        }
      }
      if (sorted(expected) != sorted(found)) {
        ++nWrongDecay;
      }
    }
    if (nParentsInEvent != 1) {
      ++nEventsWrongParentCount;
    }
  }

  std::cout << "--------------------------------\n";
  std::cout << "# Events: " << tree->GetEntries() << "\n";
  std::cout << "# Parents " << parentPDG << ": " << nParentsBySign[1] << ", anti: " << nParentsBySign[-1] << "\n";
  std::cout << "# Parents from the underlying event (not checked): " << nFromUnderlyingEvent << "\n";
  std::cout << "# Events without exactly one parent: " << nEventsWrongParentCount << "\n";
  std::cout << "# Parents not decayed: " << nNotDecayed << ", with wrong daughters: " << nWrongDecay << "\n";
  std::cout << "# Intermediate resonances: " << nIntermediates << ", with wrong daughters: " << nWrongIntermediate << "\n";
  std::cout << "--------------------------------\n";
  if (tree->GetEntries() == 0 || nEventsWrongParentCount || nNotDecayed || nWrongDecay || nWrongIntermediate ||
      (!intermediateDecaysOfPositive.empty() && nIntermediates != nParents)) {
    std::cerr << "Forced decay chain not reproduced\n";
    return 1;
  }
  return 0;
}
