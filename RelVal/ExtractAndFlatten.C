#include <iostream>
#include <string>
#include <vector>

void ExtractAndFlattenDirectory(TDirectory* inDir, TDirectory* outDir, std::string const& basedOnTree = "", std::string const& currentPrefix = "", std::vector<std::string>* includeDirs = nullptr);
void ExtractTree(TTree* tree, TDirectory* outDir, std::string const& basedOnTree = "", std::string const& currentPrefix = "");
void ExtractFromMonitorObjectCollection(o2::quality_control::core::MonitorObjectCollection* o2MonObjColl, TDirectory* outDir, std::string const& currentPrefix = "");
void WriteHisto(TH1* obj, TDirectory* outDir, std::string const& currentPrefix = "");
void WriteProfile(TProfile* obj, TDirectory* outDir, std::string const& currentPrefix = "");
void WriteTEfficiency(TEfficiency* obj, TDirectory* outDir, std::string const& currentPrefix = "");
void WriteToDirectory(TH1* histo, TDirectory* dir, std::string const& prefix = "");
bool WriteObject(TObject* o, TDirectory* outDir, std::string const& currentPrefix = "");

// use this potentially to write histograms from TTree::Draw to
TDirectory* BUFFER_DIR = nullptr;

bool checkFileOpen(TFile* file)
{
  return (file && !file->IsZombie());
}

// Arguments
// filename: Path to filename to be extracted
// outputFilename: Where to store histograms of flattened output
// basedOnTree: This is in principle only needed for TTrees to determine the x-axis range and binning

void ExtractAndFlatten(std::string const& filename, std::string const& outputFilename, std::string const& basedOnTree = "", std::string const& includeDirsString = "")
{
  gROOT->SetBatch();

  std::vector<std::string>* includeDirs{};
  if (!includeDirsString.empty()) {
    includeDirs = new std::vector<std::string>();
    std::stringstream ss(includeDirsString);
    std::string token;
    while (std::getline(ss, token, ',')) {
      // normalise paths to always start with "/" and end without "/"
      if (token.back() == '/') {
        token.pop_back();
      }
      if (token.front() != '/') {
        token.insert(0, "/");
      }
      includeDirs->push_back(token);
    }
  }

  // That is used to not pollute any other directory
  BUFFER_DIR = new TDirectory("BUFFER_DIR", "BUFFER_DIR");
  if (filename.find("alien") == 0) {
    // assume that this is on the GRID
    TGrid::Connect("alien://");
  }
  TFile inFile(filename.c_str(), "READ");
  if (!checkFileOpen(&inFile)) {
    std::cerr << "File " << filename << " could not be opened\n";
    return;
  }
  TFile extractedFile(outputFilename.c_str(), "UPDATE");
  ExtractAndFlattenDirectory(&inFile, &extractedFile, basedOnTree, "", includeDirs);
  inFile.Close();
  extractedFile.Close();
}

// writing a TObject to a TDirectory
void WriteToDirectory(TH1* histo, TDirectory* dir, std::string const& prefix)
{
  std::string name = prefix + histo->GetName();

  histo->SetName(name.c_str());
  auto hasObject = (TH1*)dir->Get(name.c_str());
  if (hasObject) {
    hasObject->Add(histo);
    dir->WriteTObject(hasObject, name.c_str(), "Overwrite");
    return;
  }
  dir->WriteTObject(histo);
}

bool checkIncludePath(std::string thisPath, std::vector<std::string>*& includeDirs)
{
  if (!includeDirs) {
    return true;
  }
  auto pos = thisPath.find(":/");
  if (pos != std::string::npos) {
    // remove the file: to keep only /path/to/dir
    thisPath.erase(0, pos + 2);
    // thisPath = thisPath.substr(pos + 2);
  }
  if (thisPath.empty() || thisPath.compare("/") == 0) {
    // if we are in top dir, do nothing
    return true;
  }
  bool extractThis(false);
  for (auto& incDir : *includeDirs) {
    if (incDir.find(thisPath) != std::string::npos) {
      // A pattern given by the user was found in the current path.
      // So everything below must be extracted and we don't need to check again.
      includeDirs = nullptr;
      return true;
    }
    if (thisPath.find(incDir) != std::string::npos) {
      // Here, the current path was found in the user pattern. The user pattern is deeper so we need to keep looking.
      return true;
    }
  }
  return false;
}

// Read from a given input directory and write everything found there (including sub directories) to a flat output directory
void ExtractAndFlattenDirectory(TDirectory* inDir, TDirectory* outDir, std::string const& basedOnTree, std::string const& currentPrefix, std::vector<std::string>* includeDirs)
{

  if (!checkIncludePath(inDir->GetPath(), includeDirs)) {
    return;
  }
  TIter next(inDir->GetListOfKeys());
  TKey* key = nullptr;
  while ((key = static_cast<TKey*>(next()))) {
    auto obj = key->ReadObj();
    if (auto nextInDir = dynamic_cast<TDirectory*>(obj)) {
      // recursively scan TDirectory
      ExtractAndFlattenDirectory(nextInDir, outDir, basedOnTree, currentPrefix + nextInDir->GetName() + "_", includeDirs);
    } else if (auto qcMonitorCollection = dynamic_cast<o2::quality_control::core::MonitorObjectCollection*>(obj)) {
      auto qcMonPath = std::string(inDir->GetPath()) + "/" + qcMonitorCollection->GetName();
      auto includeDirsCache = includeDirs;
      if (!checkIncludePath(qcMonPath, includeDirsCache)) {
        continue;
      }
      ExtractFromMonitorObjectCollection(qcMonitorCollection, outDir, currentPrefix);
    } else if (auto tree = dynamic_cast<TTree*>(obj)) {
      ExtractTree(tree, outDir, basedOnTree, currentPrefix);
    } else {
      if (!WriteObject(obj, outDir, currentPrefix)) {
        std::cerr << "Cannot handle object " << obj->GetName() << " which is of class " << key->GetClassName() << "\n";
      }
    }
  }
}

void ExtractTree(TTree* tree, TDirectory* outDir, std::string const& basedOnTree, std::string const& currentPrefix)
{
  const std::vector<std::string> acceptedLeafTypes{"char", "int", "float", "double"};
  TIter next(tree->GetListOfLeaves());
  std::vector<std::string> leafNames;
  TLeaf* obj = nullptr;
  TFile* basedOnTreeFile = nullptr;
  auto prefix = !currentPrefix.empty() ? currentPrefix + "_" + tree->GetName() : tree->GetName();
  if (prefix.rfind("DF_", 0) == 0) {
    prefix = std::string("DF_merged_") + tree->GetName();
  }
  if (!basedOnTree.empty()) {
    basedOnTreeFile = new TFile(basedOnTree.c_str(), "READ");
  }
  while ((obj = (TLeaf*)next())) {
    bool accept(false);
    TString typeName(obj->GetTypeName());
    typeName.ToLower();
    for (auto& alt : acceptedLeafTypes) {
      if (typeName.Contains(alt.c_str())) {
        accept = true;
        break;
      }
    }
    if (!accept) {
      continue;
    }
    auto fullName = obj->GetFullName();
    if (fullName.EndsWith("_")) {
      continue;
    }
    leafNames.push_back(fullName.Data());
  }
  for (auto& ln : leafNames) {
    gDirectory->cd();
    std::string histName = prefix + "_" + ln;
    size_t pos;
    while ((pos = histName.find(".")) != std::string::npos) {
      histName.replace(pos, 1, "_");
    }
    while ((pos = histName.find("/")) != std::string::npos) {
      histName.replace(pos, 1, "_");
    }
    auto drawString = ln + ">>" + histName;
    TH1* currentHist = nullptr;
    if (basedOnTreeFile) {
      currentHist = (TH1*)basedOnTreeFile->Get(histName.c_str());
    }
    if (!currentHist) {
      currentHist = (TH1*)outDir->Get(histName.c_str());
    }
    if (currentHist) {
      currentHist->SetDirectory(BUFFER_DIR);
      currentHist->Reset("ICEMS");
      drawString = ln + ">>+" + histName;
    }

    BUFFER_DIR->cd();
    auto success = tree->Draw(drawString.c_str(), "", "goff", TTree::kMaxEntries, 0);
    currentHist = (TH1*)gDirectory->Get(histName.c_str());
    if (!success || !currentHist) {
      std::cerr << "WARNING: Cannot draw TLeaf " << ln << "\n";
      continue;
    }
    WriteObject(currentHist, outDir);
  }
  BUFFER_DIR->Clear();
}

// extract everything from a o2::quality_control::core::MonitorObjectCollection object
void ExtractFromMonitorObjectCollection(o2::quality_control::core::MonitorObjectCollection* o2MonObjColl, TDirectory* outDir, std::string const& currentPrefix)
{
  std::cout << "--- Process o2 Monitor Object Collection " << o2MonObjColl->GetName() << " ---\n";
  int nProcessed{};
  for (int j = 0; j < o2MonObjColl->GetEntries(); j++) {
    if (WriteObject(o2MonObjColl->At(j), outDir, currentPrefix + o2MonObjColl->GetName() + "_")) {
      nProcessed++;
    }
  }
  std::cout << "Objects processed in MonitorObjectCollection:" << nProcessed << "\n";
}

// make sure we don't have any special characters in the names, such as "/"
void adjustName(TObject* o)
{
  if (auto oNamed = dynamic_cast<TNamed*>(o)) {
    std::string name(oNamed->GetName());
    std::replace(name.begin(), name.end(), '/', '_');
    oNamed->SetName(name.c_str());
  }
}

// decide which concrete function to call to write the given object
bool WriteObject(TObject* o, TDirectory* outDir, std::string const& currentPrefix)
{
  if (auto monObj = dynamic_cast<o2::quality_control::core::MonitorObject*>(o)) {
    return WriteObject(monObj->getObject(), outDir, currentPrefix);
  }
  adjustName(o);
  if (auto eff = dynamic_cast<TEfficiency*>(o)) {
    WriteTEfficiency(eff, outDir, currentPrefix);
    return true;
  }
  if (auto prof = dynamic_cast<TProfile*>(o)) {
    WriteProfile(prof, outDir, currentPrefix);
    return true;
  }
  if (auto hist = dynamic_cast<TH1*>(o)) {
    WriteHisto(hist, outDir, currentPrefix);
    return true;
  }
  std::cerr << "WARNING: Cannot process object " << o->GetName() << "\n";
  return false;
}

// Implementation to write a TH1
void WriteHisto(TH1* hA, TDirectory* outDir, std::string const& currentPrefix)
{
  WriteToDirectory(hA, outDir, currentPrefix);
}

// Implementation to extract TH1 from TEfficieny and write them
void WriteTEfficiency(TEfficiency* hEff, TDirectory* outDir, std::string const& currentPrefix)
{ // should I further develop that?
  // separate numerator and denominator of the efficiency
  auto hEffNomin = (TH1*)hEff->GetPassedHistogram(); // eff nominator
  auto hEffDenom = (TH1*)hEff->GetTotalHistogram();  // eff denominator
  hEffNomin->SetName(Form("%s_numeratorFromTEfficiency", hEffNomin->GetName()));
  hEffDenom->SetName(Form("%s_denominatorFromTEfficiency", hEffDenom->GetName()));

  // recreate the efficiency dividing numerator for denominator:
  auto heff = (TH1*)(hEffNomin->Clone("heff"));
  heff->SetTitle(Form("%s", hEff->GetTitle()));
  heff->SetName(Form("%s_ratioFromTEfficiency", hEff->GetName()));
  heff->Divide(hEffNomin, hEffDenom, 1.0, 1.0, "B");

  WriteToDirectory(hEffNomin, outDir, currentPrefix);
  WriteToDirectory(hEffDenom, outDir, currentPrefix);
  WriteToDirectory(heff, outDir, currentPrefix);
}

// Implementation to write TProfile
void WriteProfile(TProfile* hProf, TDirectory* outDir, std::string const& currentPrefix)
{ // should I further develop that?

  auto hprofx = (TH1D*)hProf->ProjectionX();

  WriteToDirectory(hProf, outDir, currentPrefix);
  WriteToDirectory(hprofx, outDir, currentPrefix);
}