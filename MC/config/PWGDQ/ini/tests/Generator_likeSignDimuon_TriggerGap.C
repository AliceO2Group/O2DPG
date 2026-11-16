int External()
{
  std::string path{"o2sim_Kine.root"};
  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  auto tree = (TTree*)file.Get("o2sim");
  std::vector<o2::MCTrack>* tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  int nMuons{};
  int nMuonsInAcc{};
  int nMuonsToBeDone{};
  int nLikeSignPairs{};
  int nLikeSignPairsInAcc{};
  int nLikeSignPairsToBeDone{};
  int nEvents = tree->GetEntries();

  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    int nPos = 0, nNeg = 0;
    int nPosAcc = 0, nNegAcc = 0;
    int nPosToBeDone = 0, nNegToBeDone = 0;

    for (auto& track : *tracks) {
      int pdg = track.GetPdgCode();
      if (std::abs(pdg) != 13) continue;
      double y = track.GetRapidity();
      bool inAcc = (y > -4.3 && y < -2.2);
      bool toBeDone = track.getToBeDone();

      if (pdg == -13) { // mu+
        nPos++;
        if (inAcc) nPosAcc++;
        if (toBeDone) nPosToBeDone++;
      } else { // mu-
        nNeg++;
        if (inAcc) nNegAcc++;
        if (toBeDone) nNegToBeDone++;
      }
    }
    nMuons += nPos + nNeg;
    nMuonsInAcc += nPosAcc + nNegAcc;
    nMuonsToBeDone += nPosToBeDone + nNegToBeDone;

    nLikeSignPairs += nPos * (nPos - 1) / 2 + nNeg * (nNeg - 1) / 2;
    nLikeSignPairsInAcc += nPosAcc * (nPosAcc - 1) / 2 + nNegAcc * (nNegAcc - 1) / 2;
    nLikeSignPairsToBeDone += nPosToBeDone * (nPosToBeDone - 1) / 2 + nNegToBeDone * (nNegToBeDone - 1) / 2;
  }

  std::cout << "#events: " << nEvents << "\n"
            << "#muons: " << nMuons << "\n"
            << "#muons in acceptance: " << nMuonsInAcc << "\n"
            << "#muons to be done: " << nMuonsToBeDone << "\n"
            << "#like-sign muon pairs: " << nLikeSignPairs << "\n"
            << "#like-sign muon pairs in acceptance: " << nLikeSignPairsInAcc << "\n"
            << "#like-sign muon pairs to be done: " << nLikeSignPairsToBeDone << "\n";

  if (nLikeSignPairs == 0) {
    std::cerr << "Number of like-sign muon pairs should be greater than 0.\n";
    return 1;
  }
  if (nLikeSignPairs != nLikeSignPairsToBeDone) {
    std::cerr << "The number of muon pairs should be the same as the number of muon pairs which should be transported.\n";
    return 1;
  }

  return 0;
}
