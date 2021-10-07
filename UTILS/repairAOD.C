int repairAOD(const char* name, const char* newname) {
  // This repairs a corrupted O2mccollisionlabel table
  // We copy all trees but "O2mccollisionlabel" to new file
  // The O2mccollisionlabel is copied manually
  auto outputFile = TFile::Open(newname,"RECREATE");
  TDirectory* outputDir = nullptr;
  
  TFile inputFile(name,"READ");

  auto l = inputFile.GetListOfKeys();
  auto TFID=((TNamed*)l->At(0))->GetName();
  std::map<std::string,TTree*> trees;

  auto folder = (TDirectoryFile*)inputFile.Get(TFID);
  auto treeList = folder->GetListOfKeys();
  for (auto key2 : *treeList) {
    auto treeName = ((TObjString*)key2)->GetString().Data();
    auto inputTree = (TTree*)folder->Get(Form("%s", treeName));
    if (std::strcmp(treeName, "O2mccollisionlabel")!=0) {
      printf("Processing tree %s\n", treeName);
      // clone tree
      if (!outputDir) {
        outputDir = outputFile->mkdir(TFID);
      }
      outputDir->cd();
      auto outputTree = inputTree->CloneTree(-1, "fast");
      outputTree->SetAutoFlush(0);
      trees[treeName] = outputTree;
    }
    else {
      // fix O2mccollisionlabel which should have same size as O2collision
      int id = -1;
      uint16_t m = -1;
      std::vector<int> ids;
      std::vector<uint16_t> masks;
      inputTree->SetBranchAddress("fIndexMcCollisions", &id);
      inputTree->SetBranchAddress("fMcMask", &m);
      auto outputTree = new TTree("O2mccollisionlabel","O2mccollisionlabel");
      outputTree->Branch("fIndexMcCollisions", &id);
      outputTree->Branch("fMcMask", &m);
      for (int e = 0; e < trees["O2collision"]->GetEntries(); ++e) {
        inputTree->GetEntry(e);
        outputTree->Fill();
      }
    }
  }
  outputFile->Write();
  outputFile->Close();

  return 0;
}
