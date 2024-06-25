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
  
  int nPions = 0;
  int nElectrons = 0;
  int nPhotons = 0;
  auto nEvents = tree->GetEntries();
  for (int i = 0; i < nEvents; i++)
  {
	nPhotons = 0;
	nPions = 0;
	nElectrons = 0;
    auto check = tree->GetEntry(i);
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
    {
      auto track = tracks->at(idxMCTrack);
      if (track.GetPdgCode() == 100443 && track.getMotherTrackId() == -1){ //Primary psi2s
	    for(int iDaugh = track.getFirstDaughterTrackId(); iDaugh<=track.getLastDaughterTrackId(); iDaugh++){
		auto daughPsi2s = tracks->at(iDaugh);
		if(daughPsi2s.GetPdgCode() == 22) nPhotons++;
		if(TMath::Abs(daughPsi2s.GetPdgCode()) == 211) nPions++;

		if(daughPsi2s.GetPdgCode() == 443 ){
			for(int jDaugh = daughPsi2s.getFirstDaughterTrackId(); jDaugh<=daughPsi2s.getLastDaughterTrackId(); jDaugh++){			
				auto daughJPsi = tracks->at(jDaugh);
				if(daughJPsi.GetPdgCode() == 22) nPhotons++;
				if(TMath::Abs(daughJPsi.GetPdgCode()) == 11) nElectrons++;
				}
			}
		}
	  }
	} 	
	if(nElectrons != 2 || nPions != 2)return 1;
  }  
  return 0;
}
