int External()
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
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }
  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);
  
  bool goodEvent = kFALSE;
  auto nEvents = tree->GetEntries();
  for (int i = 0; i < nEvents; i++)
  {
	goodEvent = kFALSE;
    auto check = tree->GetEntry(i);
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      if (track.GetPdgCode() == 443 && track.getMotherTrackId() == -1){ //Primary J/psi
		auto daugh1 = tracks->at(track.getFirstDaughterTrackId());
		auto daugh2 = tracks->at(track.getLastDaughterTrackId());	
		if(TMath::Abs(daugh1.GetPdgCode()) == 13 && TMath::Abs(daugh2.GetPdgCode()) == 13) goodEvent = kTRUE;
	  }		
    }
    if(!goodEvent) return 1;
  }  
  return 0;
}
