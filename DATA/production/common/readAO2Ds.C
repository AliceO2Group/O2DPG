int readAO2Ds(const char* filename = "AO2D.root") {

  int retCode = 0;
  
  TFile* f = new TFile(filename);
  int nkeysfile = f->GetNkeys();
  TList* lkeysfile = f->GetListOfKeys();
  std::vector<int> vectNEntriesPerDF;
  for (int ik = 0; ik < nkeysfile; ++ik) {
    TKey* k = (TKey*)lkeysfile->At(ik);
    TString cnameKeyInFile = k->GetClassName();
    TString onameKeyInFile = k->GetName();
    if (cnameKeyInFile != "TDirectoryFile" && !onameKeyInFile.BeginsWith("DF_")) {
      continue;
    }
    TDirectoryFile* d = (TDirectoryFile*)f->Get(onameKeyInFile.Data());
    int nkeysdir = d->GetNkeys();
    vectNEntriesPerDF.push_back(nkeysdir);
    std::cout << "\nDirectory = " << onameKeyInFile.Data() << " has " << nkeysdir << " tables:" << std::endl;
    TList* lkeysdir = d->GetListOfKeys();
    std::vector<std::pair<std::string, int>> vectNEntriesPerTree;
    for (int ikdir = 0; ikdir < nkeysdir; ++ikdir) {
      TKey* kdir = (TKey*)lkeysdir->At(ikdir);
      TString cnameKeyInDir = kdir->GetClassName();
      TString onameKeyInDir = kdir->GetName();
      if (cnameKeyInDir != "TTree") {
	continue;
      }
      if (ikdir < nkeysdir - 1) {
	std::cout << onameKeyInDir.Data() << " ";
      }
      else {
	std::cout << onameKeyInDir.Data() << std::endl;
      }
      TTree* t = (TTree*)d->Get(onameKeyInDir.Data());
      if (onameKeyInDir.BeginsWith("O2track")) {
	vectNEntriesPerTree.push_back({onameKeyInDir.Data(), t->GetEntries()});
      }
    }
    if (all_of(vectNEntriesPerTree.begin(), vectNEntriesPerTree.end(), [&] (std::pair<std::string, int> i) {return i.second == vectNEntriesPerTree[0].second;})){
      std::cout << "In current DF (" << onameKeyInFile.Data() << "), all tracks tables (starting with O2track) have the same number of entries!" << std::endl;
    }
    else {
      std::cout << "In current DF (" << onameKeyInFile.Data() << "), NOT all tracks tables (starting with O2track) have the same number of entries!" << std::endl;
      retCode = 1;
    }
    for (auto& item : vectNEntriesPerTree) {
      std::cout << "table " << item.first << " has " << item.second << " entries" << std::endl;
    }    
  }
  if (std::equal(vectNEntriesPerDF.begin() + 1, vectNEntriesPerDF.end(), vectNEntriesPerDF.begin())) {
    std::cout << "All DFs have the same number of tables" << std::endl;
  }
  else {
    std::cout << "NOT all DFs have the same number of tables" << std::endl;
    retCode = retCode + 2;
  }      
  return retCode;
}

    
