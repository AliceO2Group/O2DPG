#include <fstream>
#include <iostream>
#include <string>
#include <vector>
using namespace std;

TFile* fileSummaryOutput = nullptr;
TFile* fileTestSummary = nullptr;

TString prefix = "";
int correlationCase = 0; // at the moment I assume no error correlation ..

struct results {
  bool passed;
  double value;
  double critical;
  bool comparable;
  TString testname;
};

// define the possible available tests
enum options {
  CHI2 = 0x01,
  BINCONTNORM = 0x02,
  NENTRIES = 0x04,
  // ...
};

void ExtractAndFlattenDirectory(TDirectory* inDir, TDirectory* outDir, std::string const& currentPrefix = "");
void ExtractFromMonitorObjectCollection(o2::quality_control::core::MonitorObjectCollection* o2MonObjColl, TDirectory* outDir, std::string const& currentPrefix = "");
void ProcessDirCollection(TDirectoryFile* dirCollect);
void WriteHisto(TH1* obj, TDirectory* outDir, std::string const& currentPrefix = "");
void WriteProfile(TProfile* obj, TDirectory* outDir, std::string const& currentPrefix = "");
void WriteTEfficiency(TEfficiency* obj, TDirectory* outDir, std::string const& currentPrefix = "");
void WriteToDirectory(TH1* histo, TDirectory* dir, std::string const& prefix = "");
void CompareHistos(TH1* hA, TH1* hB, int whichTest, double valChi2, double valMeanDiff, double valEntriesDiff,
                   bool firstComparison, bool finalComparison, TH2F* hSum, TH2F* hTests);
bool PotentiallySameHistograms(TH1*, TH1*);
struct results CompareChiSquare(TH1* hA, TH1* hB, double varChi2);
struct results CompareBinContent(TH1* hA, TH1* hB, double valMeanDiff);
struct results CompareNentr(TH1* hA, TH1* hB, double valEntriesDiff);
void DrawRatio(TH1* hR);
void DrawRelativeDifference(TH1* hR);
void SelectCriticalHistos();
void createTestsSummaryPlot(TFile* file, TString const& obj);
bool WriteObject(TObject* o, TDirectory* outDir, std::string const& currentPrefix = "");
void SetZLabels(TAxis* axis);
void WriteToJson(TH2F* hSum);

bool checkFileOpen(TFile* file)
{
  return (file && !file->IsZombie());
}

template <typename T>
bool areSufficientlyEqualNumbers(T a, T b, T epsilon = T(0.00001))
{
  // return std::abs(a - b) / std::abs(a) <= epsilon && std::abs(a - b) / std::abs(b) <= epsilon;
  return std::abs(a - b) <= epsilon;
}

// what to give as input:
// 1) name and path of first file,
// 2) name and path of second file,
// 3) object to analyse (it can be a MonitorObject or a TDirectory); when left  empty, loop on all objects; 4) which test to perform: 1->Chi-square; 2--> BinContDiff; 3 --> Chi-square + BinContDiff; 4-> EntriesDiff; 5--> EntriesDiff + Chi2; 6 -->  EntriesDiff + BinContDiff; 7 --> EntriesDiff + Chi2 + BinContDiff;
// 4), 5) and 6) threshold values for chi2, bin cont and N entries checks;
// 6) select if files have to be taken from the grid or not
// 7) choose if specific critic plots have to be saved in a second .pdf file

void ReleaseValidation(const TString filename1, const TString filename2,
                       int whichTest = 1, double valueChi2 = 1.5, double valueMeanDiff = 1.5, double valueEntriesDiff = 0.01,
                       bool selectCritical = false)
{
  if (whichTest < 1 || whichTest > 7) {
    std::cerr << "ERROR: Please select which test you want to perform:\n"
              << "1->Chi-square; 2--> ContBinDiff; 3 --> Chi-square+MeanDiff; 4->EntriesDiff; 5--> EntriesDiff + Chi2; 6 -->  EntriesDiff + MeanDiff; 7 --> EntriesDiff + Chi2 + MeanDiff\n";
    return;
  }

  if (filename1.BeginsWith("alien") || filename2.BeginsWith("alien")) {
    // assume that this is on the GRID
    TGrid::Connect("alien://");
  }

  // attempt to open input files and make sure they are open
  TFile inFile1(filename1, "READ");
  TFile inFile2(filename2, "READ");

  if (!checkFileOpen(&inFile1)) {
    std::cerr << "File " << filename1.Data() << " could not be opened\n";
    return;
  }
  if (!checkFileOpen(&inFile2)) {
    std::cerr << "File " << filename2.Data() << " could not be opened\n";
    return;
  }

  // extract all histograms from input files and output them into a new file with a flat structure
  TFile extractedFile1("newfile1.root", "RECREATE");
  ExtractAndFlattenDirectory(&inFile1, &extractedFile1);

  TFile extractedFile2("newfile2.root", "RECREATE");
  ExtractAndFlattenDirectory(&inFile2, &extractedFile2);

  // prepare summary plots
  int nkeys = extractedFile1.GetNkeys();
  TH2F* hSummaryCheck = new TH2F("hSummaryCheck", "", 1, 0, 1, nkeys, 0, 2);
  hSummaryCheck->SetStats(000);
  hSummaryCheck->SetMinimum(-1E-6);

  int nTests = 0;
  if ((whichTest & CHI2) == CHI2) {
    nTests++;
  }
  if ((whichTest & BINCONTNORM) == BINCONTNORM) {
    nTests++;
  }
  if ((whichTest & NENTRIES) == NENTRIES) {
    nTests++;
  }
  TH2F* hSummaryTests = new TH2F("hSummaryTests", "", nTests, 0, 1, nkeys, 0, 2);
  hSummaryTests->SetStats(000);
  hSummaryTests->SetMinimum(-1E-6);

  // open the two files (just created), look at the histograms and make statistical tests
  bool isLastComparison = false; // It is true only when the last histogram of the file is considered,
  // in order to properly close the pdf
  bool isFirstComparison = true; // to properly open the pdf file

  TString objNameOfInterest("");

  TIter next(extractedFile1.GetListOfKeys());
  TKey* key = nullptr;
  int nSimilarHistos{};
  int nComparisons{};
  int nNotFound{};
  int comparison = 0;
  std::vector<std::string> collectSimilarHistos;
  while ((key = static_cast<TKey*>(next()))) {
    // At this point we expect objects deriving from TH1 only since that is what we extracted
    auto hA = static_cast<TH1*>(key->ReadObj());
    auto oname = key->GetName();
    auto hB = static_cast<TH1*>(extractedFile2.Get(oname));

    if (nComparisons + nNotFound == nkeys - 1)
      isLastComparison = true;

    if (!hB) {
      // That could still happen in case we compare either comletely different file by accident or something has been changed/added/removed
      std::cerr << "ERROR: Histogram " << oname << " not found in " << filename2 << ", continue with next\n";
      nNotFound++;
      continue;
    }
    if (PotentiallySameHistograms(hA, hB)) {
      collectSimilarHistos.push_back(hA->GetName());
      std::cerr << "WARNING: Found potentially same histogram " << oname << "\n";
      nSimilarHistos++;
    }

    std::cout << "Comparing " << hA->GetName() << " and " << hB->GetName() << "\n";
    CompareHistos(hA, hB, whichTest, valueChi2, valueMeanDiff, valueEntriesDiff, isFirstComparison, isLastComparison, hSummaryCheck, hSummaryTests);

    nComparisons++;
    if (nComparisons == 1)
      isFirstComparison = false;
  }
  std::cout << "\n##### Summary #####\nNumber of histograms compared: " << nComparisons
            << "\nNumber of potentially same histograms: " << nSimilarHistos << "\n";
  for (auto& csh : collectSimilarHistos) {
    std::cout << " -> " << csh << "\n";
  }
  std::cout << "\nNumber of histograms only found in first but NOT second file: " << nNotFound << "\n";

  // Create a summary plot with the result of the choosen test for all histograms
  TCanvas summaryCheck("summaryCheck", "summaryCheck");
  Int_t MyPalette[5];
  MyPalette[0] = kBlue;
  MyPalette[1] = kBlue - 10;
  MyPalette[2] = kRed;
  MyPalette[3] = kOrange;
  MyPalette[4] = kGreen;
  gStyle->SetPalette(5, MyPalette);
  gStyle->SetGridStyle(3);
  gStyle->SetGridWidth(3);
  summaryCheck.SetGrid();
  summaryCheck.SetRightMargin(0.22);
  hSummaryCheck->LabelsDeflate("Y");
  SetZLabels(hSummaryCheck->GetZaxis());
  hSummaryCheck->Draw("colz");
  summaryCheck.SaveAs(Form("SummaryCheck%d.png", whichTest));

  // Create a summary plot with the result of each of the three basic tests for each histogram
  TCanvas summaryTests("summaryTests", "summaryTests");

  gStyle->SetGridStyle(3);
  summaryTests.SetGrid();
  summaryTests.SetRightMargin(0.22);
  hSummaryTests->LabelsDeflate("Y");
  SetZLabels(hSummaryTests->GetZaxis());
  hSummaryTests->Draw("colz");
  summaryTests.SaveAs("SummaryTests.png");

  fileSummaryOutput = new TFile("Summary.root", "update");
  hSummaryCheck->Write(Form("hSummaryCheck%d", whichTest));
  hSummaryTests->Write("hSummaryTests");
  if (selectCritical) {
    // selected critical plots are saved in a separated pdf
    SelectCriticalHistos();
  }
  fileSummaryOutput->Close();

  WriteToJson(hSummaryCheck);
}

// setting the labels of the Z axis for the colz plot
void SetZLabels(TAxis* axis)
{
  axis->SetRangeUser(-0.7, 1.01);
  axis->SetNdivisions(10, kFALSE);
  axis->SetTickLength(0.);
  axis->ChangeLabel(1, -1, 0, -1, -1, -1, "");
  axis->ChangeLabel(2, -1, -1, -1, -1, -1, "N.C. (crit.)");
  axis->ChangeLabel(3, -1, 0, -1, -1, -1, "");
  axis->ChangeLabel(4, -1, -1, -1, -1, -1, "N.C. (non-crit.)");
  axis->ChangeLabel(5, -1, 0, -1, -1, -1, "");
  axis->ChangeLabel(6, -1, -1, -1, -1, -1, "BAD");
  axis->ChangeLabel(7, -1, 0, -1, -1, -1, "");
  axis->ChangeLabel(8, -1, -1, -1, -1, -1, "WARNING");
  axis->ChangeLabel(9, -1, 0, -1, -1, -1, "");
  axis->ChangeLabel(10, -1, -1, -1, -1, -1, "GOOD");
  axis->ChangeLabel(11, -1, 0, -1, -1, -1, "");
}

///////////////////////////////////////////////
// reading and pre-processing of input files //
///////////////////////////////////////////////

bool PotentiallySameRange(TAxis* axisA, TAxis* axisB)
{
  auto binsA = axisA->GetNbins();
  auto binsB = axisB->GetNbins();

  return (areSufficientlyEqualNumbers(axisA->GetBinLowEdge(1), axisB->GetBinLowEdge(1)) && areSufficientlyEqualNumbers(axisA->GetBinUpEdge(binsA), axisB->GetBinUpEdge(binsB)));
}

bool PotentiallySameRange(TH1* hA, TH1* hB)
{

  if (!PotentiallySameRange(hA->GetXaxis(), hB->GetXaxis()) ||
      (dynamic_cast<TH2*>(hA) && !PotentiallySameRange(hA->GetYaxis(), hB->GetYaxis())) ||
      (dynamic_cast<TH3*>(hA) && !PotentiallySameRange(hA->GetZaxis(), hB->GetZaxis()))) {
    // something is different
    return false;
  }
  return true;
}

bool PotentiallySameAxes(TAxis* axisA, TAxis* axisB)
{
  auto binsA = axisA->GetNbins();
  auto binsB = axisB->GetNbins();

  if (binsA != binsB) {
    // different number of bins --> obvious
    return false;
  }
  for (int i = 1; i <= binsA; i++) {
    if (!areSufficientlyEqualNumbers(axisA->GetBinLowEdge(i), axisB->GetBinLowEdge(i))) {
      return false;
    }
  }
  return areSufficientlyEqualNumbers(axisA->GetBinUpEdge(binsA), axisB->GetBinUpEdge(binsA));
}

bool PotentiallySameAxes(TH1* hA, TH1* hB)
{

  if (!PotentiallySameAxes(hA->GetXaxis(), hB->GetXaxis()) ||
      (dynamic_cast<TH2*>(hA) && !PotentiallySameAxes(hA->GetYaxis(), hB->GetYaxis())) ||
      (dynamic_cast<TH3*>(hA) && !PotentiallySameAxes(hA->GetZaxis(), hB->GetZaxis()))) {
    // some axes are different
    return false;
  }
  return true;
}

bool PotentiallySameHistograms(TH1* hA, TH1* hB)
{
  if (hA->GetEntries() != hB->GetEntries()) {
    // different number of entries --> obvious
    return false;
  }

  if (!PotentiallySameAxes(hA, hB)) {
    // some axes are different
    return false;
  }

  // if still in the game, check bin contents of all bins
  for (int ix = 1; ix <= hA->GetNbinsX(); ix++) {
    for (int iy = 1; iy <= hA->GetNbinsY(); iy++) {
      for (int iz = 1; iz <= hA->GetNbinsZ(); iz++) {
        if (!areSufficientlyEqualNumbers(hA->GetBinContent(ix, iy, iz), hB->GetBinContent(ix, iy, iz))) {
          return false;
        }
      }
    }
  }

  // appear to be the same
  return true;
}

// writing a TObject to a TDirectory
void WriteToDirectory(TH1* histo, TDirectory* dir, std::string const& prefix)
{
  std::string name = prefix + histo->GetName();
  histo->SetName(name.c_str());
  dir->WriteTObject(histo);
}

// Read from a given input directory and write everything found there (including sub directories) to a flat output directory
void ExtractAndFlattenDirectory(TDirectory* inDir, TDirectory* outDir, std::string const& currentPrefix)
{
  TIter next(inDir->GetListOfKeys());
  TKey* key = nullptr;
  while ((key = static_cast<TKey*>(next()))) {
    auto obj = key->ReadObj();
    if (auto nextInDir = dynamic_cast<TDirectory*>(obj)) {
      // recursively scan TDirectory
      ExtractAndFlattenDirectory(nextInDir, outDir, currentPrefix + nextInDir->GetName() + "_");
    } else if (auto qcMonitorCollection = dynamic_cast<o2::quality_control::core::MonitorObjectCollection*>(obj)) {
      ExtractFromMonitorObjectCollection(qcMonitorCollection, outDir, currentPrefix);
    } else {
      if (!WriteObject(obj, outDir, currentPrefix)) {
        std::cerr << "Cannot handle object " << obj->GetName() << " which is of class " << key->GetClassName() << "\n";
      }
    }
  }
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

// decide which concrete function to call to write the given object
bool WriteObject(TObject* o, TDirectory* outDir, std::string const& currentPrefix)
{
  if (auto monObj = dynamic_cast<o2::quality_control::core::MonitorObject*>(o)) {
    return WriteObject(monObj->getObject(), outDir, currentPrefix);
  }
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
  return false;
}

// Implementation to write a TH1
void WriteHisto(TH1* hA, TDirectory* outDir, std::string const& currentPrefix)
{
  TString hAcln = hA->ClassName();

  TCanvas cc(Form("%s_%s", outDir->GetName(), hA->GetName()), Form("%s_%s", outDir->GetName(), hA->GetName()));
  if (hAcln.Contains("TH2")) {
    hA->Draw("colz");
  } else {
    hA->DrawNormalized();
  }
  cc.SaveAs(Form("%s_%s.png", outDir->GetName(), hA->GetName()));
  WriteToDirectory(hA, outDir, currentPrefix);
}

// Implementation to extract TH1 from TEfficieny and write them
void WriteTEfficiency(TEfficiency* hEff, TDirectory* outDir, std::string const& currentPrefix)
{ // should I further develop that?
  // separate numerator and denominator of the efficiency
  auto hEffNomin = (TH1*)hEff->GetPassedHistogram(); // eff nominator
  auto hEffDenom = (TH1*)hEff->GetTotalHistogram();  // eff denominator
  hEffNomin->SetName(Form("%s_effnominator", hEffNomin->GetName()));
  hEffDenom->SetName(Form("%s_effdenominator", hEffDenom->GetName()));

  // recreate the efficiency dividing numerator for denominator:
  auto heff = (TH1*)(hEffNomin->Clone("heff"));
  heff->SetTitle(Form("%s", hEff->GetTitle()));
  heff->SetName(Form("%s", hEff->GetName()));
  heff->Divide(hEffNomin, hEffDenom, 1.0, 1.0, "B");

  // save nominator and denominator of the efficiency, to compare these plots from the two input files

  TCanvas cc("Efficiency", Form("%s_%s", outDir->GetName(), hEff->GetName()));
  hEff->Draw("AP");
  cc.SaveAs(Form("%s_%s.png", outDir->GetName(), hEff->GetName()));

  TCanvas cnom("eff numerator", Form("%s_%s_effnominator", outDir->GetName(), hEffNomin->GetName()));
  hEffNomin->Draw();
  cnom.SaveAs(Form("%s_%s_effnominator.png", outDir->GetName(), hEffNomin->GetName()));

  TCanvas cden("eff denominator", Form("%s_%s_effdenominator", outDir->GetName(), hEffDenom->GetName()));
  hEffDenom->Draw();
  cden.SaveAs(Form("%s_%s_effdenominator.png", outDir->GetName(), hEffDenom->GetName()));

  TCanvas cEff("reconstructed efficiency", Form("%s_%s_effrec", outDir->GetName(), hEff->GetName()));
  heff->Draw();
  cEff.SaveAs(Form("%s_%s_effrec.png", outDir->GetName(), hEff->GetName()));

  WriteToDirectory(hEffNomin, outDir, currentPrefix);
  WriteToDirectory(hEffDenom, outDir, currentPrefix);

  WriteToDirectory(heff, outDir, currentPrefix);
}

// Implementation to write TProfile
void WriteProfile(TProfile* hProf, TDirectory* outDir, std::string const& currentPrefix)
{ // should I further develop that?

  auto hprofx = (TH1D*)hProf->ProjectionX();

  TCanvas cc("profile histo", Form("%s_%s", outDir->GetName(), hProf->GetName()));
  hProf->Draw("");
  cc.SaveAs(Form("%s_%s.png", outDir->GetName(), hProf->GetName()));

  // save the x-projection of the TProfile
  TCanvas cprofx("profile histo proj", Form("%s_%s", outDir->GetName(), hprofx->GetName()));
  hprofx->Draw();
  cprofx.SaveAs(Form("%s_%s.png", outDir->GetName(), hprofx->GetName()));

  WriteToDirectory(hProf, outDir, currentPrefix);
  WriteToDirectory(hprofx, outDir, currentPrefix);
}

////////////////////////////////////////////
// functionality for histogram comparison //
////////////////////////////////////////////

// fills the result of a single test into the histogram displaying all test results
void FillhTests(TH2F* hTests, const char* histName, results testResult)
{
  if (testResult.comparable) {
    if (testResult.passed == false) {
      if (testResult.critical == true) {                                               // if the BAD test is critical (true), then we have BAD, otherwise just a WARNING
        hTests->Fill(Form("%s", testResult.testname.Data()), Form("%s", histName), 0); // BAD--> histo bin cont = 0
      } else {
        hTests->Fill(Form("%s", testResult.testname.Data()), Form("%s", histName), 0.5); // WARNING--> histo bin cont = 0.5
      }
    } else {
      hTests->Fill(Form("%s", testResult.testname.Data()), Form("%s", histName), 1); // GOOD--> histo bin cont = 1
    }
  } else {
    if (testResult.critical == true) {
      hTests->Fill(Form("%s", testResult.testname.Data()), Form("%s", histName), -0.5); // critical test N.C = -0.5
    } else {
      hTests->Fill(Form("%s", testResult.testname.Data()), Form("%s", histName), -0.25); // non-critical test N.C = -0.25
    }
  }
}

// keeps track if there was at least one failed/critical failed/non-comparable/... test
void SetTestResults(results testResult, bool& test_failed, bool& criticaltest_failed, bool& test_nc, bool& criticaltest_nc)
{
  if (!testResult.passed) {
    test_failed = true;
    if (testResult.critical)
      criticaltest_failed = true;
  }
  if (!testResult.comparable) {
    test_nc = true;
    if (testResult.critical)
      criticaltest_nc = true;
  }
}

void CompareHistos(TH1* hA, TH1* hB, int whichTest, double valChi2, double valMeanDiff, double valEntriesDiff,
                   bool firstComparison, bool finalComparison, TH2F* hSum, TH2F* hTests)
{
  // method to evaluate and draw the result of the comparison between plots
  hSum->SetStats(000);
  hSum->SetMinimum(-1E-6);
  hTests->SetStats(000);
  hTests->SetMinimum(-1E-6);

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  TH1* hACl = (TH1*)hA->Clone("hACl"); // I will use these two clones of hA and
                                       // hB to perform other checks later..
  TH1* hBCl = (TH1*)hB->Clone("hBCl");

  TString outc = "";
  int colt = 1;

  // Bit Mask
  // my 3 possible tests are: 1) chi2;  2) meandiff; 3) entriesdiff.  These tests can be combined in 7 different ways
  // std::vector<std::string> tests;

  bool test_failed = false;
  bool test_nc = false;
  bool criticaltest_failed = false;
  bool criticaltest_nc = false;

  struct results testResult;

  TLegend* more = new TLegend(0.6, 0.6, .9, .8);
  more->SetBorderSize(1);

  // test if each of the 3 bits is turned on in subset ‘i = whichTest’?
  // if yes, process the bit

  if ((whichTest & CHI2) == CHI2) {
    testResult = CompareChiSquare(hA, hB, valChi2);
    SetTestResults(testResult, test_failed, criticaltest_failed, test_nc, criticaltest_nc);
    if (testResult.comparable)
      more->AddEntry((TObject*)nullptr, Form("#chi^{2} / Nbins = %f", testResult.value), "");
    FillhTests(hTests, hA->GetName(), testResult);
  }

  if ((whichTest & BINCONTNORM) == BINCONTNORM) {
    testResult = CompareBinContent(hA, hB, valMeanDiff);
    SetTestResults(testResult, test_failed, criticaltest_failed, test_nc, criticaltest_nc);
    if (testResult.comparable)
      more->AddEntry((TObject*)nullptr, Form("meandiff = %f", testResult.value), "");
    FillhTests(hTests, hA->GetName(), testResult);
  }

  if ((whichTest & NENTRIES) == NENTRIES) {
    testResult = CompareNentr(hA, hB, valEntriesDiff);
    SetTestResults(testResult, test_failed, criticaltest_failed, test_nc, criticaltest_nc);
    if (testResult.comparable)
      more->AddEntry((TObject*)nullptr, Form("entriesdiff = %f", testResult.value), "");
    FillhTests(hTests, hA->GetName(), testResult);
  }

  //}
  // if all tests (subsets of the check) are GOOD, then the result is GOOD, otherwise it is BAD or WARNING or N.C.
  // It is BAD if at least one of the BAD tests is a critical test
  //}
  if (criticaltest_failed) { // BAD
    outc = Form("Check %d: BAD", whichTest);
    hSum->Fill(Form("Check%d", whichTest), Form("%s", hA->GetName()), 0);
    colt = kRed + 1;
  } else if (criticaltest_nc) { // critical N.C.
    outc = Form("Check %d: NOT COMPARABLE", whichTest);
    hSum->Fill(Form("Check%d", whichTest), Form("%s", hA->GetName()), -0.5);
    colt = kBlue + 1;
  } else if (test_nc) { // non-critical N.C
    outc = Form("Check %d: NOT COMPARABLE (non-crit.)", whichTest);
    hSum->Fill(Form("Check%d", whichTest), Form("%s", hA->GetName()), -0.25);
    colt = kBlue - 10;
  } else if (test_failed) { // WARNING
    outc = Form("Check %d: WARNING", whichTest);
    colt = kOrange + 1;
    hSum->Fill(Form("Check%d", whichTest), Form("%s", hA->GetName()), 0.5);
  } else { // GOOD
    outc = Form("Check %d: COMPATIBLE", whichTest);
    colt = kGreen + 1;
    hSum->Fill(Form("Check%d", whichTest), Form("%s", hA->GetName()), 1);
  }

  TCanvas* c = new TCanvas(hA->GetName(), hA->GetName(), 1200, 600);
  if (firstComparison)
    c->Print("plots.pdf[");
  c->Divide(2, 1);
  c->cd(1);
  gPad->SetTitle(hA->GetName());
  TString hcln = hA->ClassName();
  TString optD = "";
  if (hcln.Contains("TH2"))
    optD = "box";
  hA->SetLineColor(1);
  hA->SetMarkerColor(1);
  hA->Scale(1. / hA->GetEntries()); // normalize to the number of entries
  TH1* hAc = (TH1*)hA->DrawClone(optD.Data());
  hAc->SetTitle(hA->GetName());
  hAc->SetStats(0);
  hB->SetLineColor(2);
  hB->SetMarkerColor(2);
  hB->Scale(1. / hB->GetEntries()); // normalize to the number of entries
  TH1* hBc = (TH1*)hB->DrawClone(Form("%ssames", optD.Data()));
  hBc->SetStats(0);
  // c->Update();
  TPaveStats* stA =
    (TPaveStats*)hAc->GetListOfFunctions()->FindObject("stats");
  if (stA) {
    stA->SetLineColor(1);
    stA->SetTextColor(1);
    stA->SetY1NDC(0.68);
    stA->SetY2NDC(0.88);
  }
  TPaveStats* stB =
    (TPaveStats*)hBc->GetListOfFunctions()->FindObject("stats");
  if (stB) {
    stB->SetLineColor(2);
    stB->SetTextColor(2);
    stB->SetY1NDC(0.45);
    stB->SetY2NDC(0.65);
  }

  c->cd(2);
  // Implement the plotting of the ratio between the two histograms
  if (hcln.Contains("TH3")) {
    TH1D* hXa = ((TH3*)hA)->ProjectionX(Form("%s_xA", hA->GetName()));
    TH1D* hXb = ((TH3*)hB)->ProjectionX(Form("%s_xB", hB->GetName()));
    TH1D* hYa = ((TH3*)hA)->ProjectionY(Form("%s_yA", hA->GetName()));
    TH1D* hYb = ((TH3*)hB)->ProjectionY(Form("%s_yB", hB->GetName()));
    TH1D* hZa = ((TH3*)hA)->ProjectionZ(Form("%s_zA", hA->GetName()));
    TH1D* hZb = ((TH3*)hB)->ProjectionZ(Form("%s_zB", hB->GetName()));
    hXa->Divide(hXb);
    hYa->Divide(hYb);
    hZa->Divide(hZb);
    TPad* rpad = (TPad*)gPad;
    rpad->Divide(1, 3);
    rpad->cd(1);
    DrawRatio(hXa);
    rpad->cd(2);
    DrawRatio(hYa);
    rpad->cd(3);
    DrawRatio(hZa);

  } else {
    TH1* hArat = (TH1*)hA->Clone("hArat");
    hArat->Divide(hB);
    hArat->SetTitle(Form("%s_ratio", hA->GetName()));
    for (int k = 1; k <= hArat->GetNbinsX(); k++)
      hArat->SetBinError(k, 0.000000001);
    hArat->SetMinimum(
      TMath::Max(0.98, 0.95 * hArat->GetBinContent(hArat->GetMinimumBin()) -
                         hArat->GetBinError(hArat->GetMinimumBin())));
    hArat->SetMaximum(
      TMath::Min(1.02, 1.05 * hArat->GetBinContent(hArat->GetMaximumBin()) +
                         hArat->GetBinError(hArat->GetMaximumBin())));
    hArat->SetStats(0);
    if (hcln.Contains("TH2"))
      hArat->Draw("colz");
    else if (hcln.Contains("TH1"))
      DrawRatio(hArat);
    else
      hArat->Draw();
  }
  c->cd(1);

  TLatex* toutc = new TLatex(0.2, 0.85, outc.Data());
  toutc->SetNDC();
  toutc->SetTextColor(colt);
  toutc->SetTextFont(62);
  toutc->Draw();
  // draw text
  more->Draw("same");

  c->SaveAs(Form("%s_Ratio.png", hA->GetName()));
  fileSummaryOutput = new TFile("Summary.root", "update");
  c->Write(Form("%s%s_Ratio", prefix.Data(), hA->GetName()));
  // fileSummaryOutput->ls();
  fileSummaryOutput->Close();
  c->Print("plots.pdf");

  // Implement the plotting of the difference between the two histograms, and
  // the relative difference
  TCanvas* c1 = new TCanvas(Form("%s_diff", hA->GetName()), Form("%s_diff", hA->GetName()), 1200, 600);
  c1->Divide(2, 1);
  c1->cd(1);

  TString hAClcln = hACl->ClassName();
  TString noptD = "";
  if (hAClcln.Contains("TH2"))
    noptD = "colz"; // box
  hACl->SetLineColor(1);
  hACl->SetMarkerColor(1);
  hACl->Scale(1. / hACl->GetEntries());
  hBCl->Scale(1. / hBCl->GetEntries());

  // Subtraction
  TH1* hDiff = (TH1*)hACl->Clone("hDiff");
  hDiff->SetStats(0);
  hDiff->Add(hBCl, -1);
  hDiff->SetTitle(Form("%s_diff", hA->GetName()));
  hDiff->DrawClone(noptD.Data());

  TPaveStats* stACl =
    (TPaveStats*)hACl->GetListOfFunctions()->FindObject("stats");
  if (stACl) {
    stACl->SetLineColor(1);
    stACl->SetTextColor(1);
    stACl->SetY1NDC(0.68);
    stACl->SetY2NDC(0.88);
  }

  c1->cd(2);
  if (hcln.Contains("TH3")) {
    TH1D* hXaCl = ((TH3*)hDiff)->ProjectionX(Form("%s_xA", hACl->GetName()));
    TH1D* hXbCl = ((TH3*)hBCl)->ProjectionX(Form("%s_xB", hBCl->GetName()));
    TH1D* hYaCl = ((TH3*)hDiff)->ProjectionY(Form("%s_yA", hACl->GetName()));
    TH1D* hYbCl = ((TH3*)hBCl)->ProjectionY(Form("%s_yB", hBCl->GetName()));
    TH1D* hZaCl = ((TH3*)hDiff)->ProjectionZ(Form("%s_zA", hACl->GetName()));
    TH1D* hZbCl = ((TH3*)hBCl)->ProjectionZ(Form("%s_zB", hBCl->GetName()));
    hXaCl->Divide(hXbCl);
    hYaCl->Divide(hYbCl);
    hZaCl->Divide(hZbCl);
    TPad* rrpad = (TPad*)gPad;
    rrpad->Divide(1, 3);
    rrpad->cd(1);
    DrawRelativeDifference(hXaCl);
    rrpad->cd(2);
    DrawRelativeDifference(hYaCl);
    rrpad->cd(3);
    DrawRelativeDifference(hZaCl);

  } else {
    TH1* hDiffRel = (TH1*)hDiff->Clone("hDiffRel");
    hDiffRel->Divide(hBCl);
    hDiffRel->SetTitle(Form("%s_diffrel", hA->GetName()));
    for (int k = 1; k <= hDiffRel->GetNbinsX(); k++)
      hDiffRel->SetBinError(k, 0.000000001);
    /*
    hDiffRel->SetMinimum(TMath::Max(
      0.98, 0.95 * hDiffRel->GetBinContent(hDiffRel->GetMinimumBin()) -
              hDiffRel->GetBinError(hDiffRel->GetMinimumBin())));
    hDiffRel->SetMaximum(TMath::Min(
      1.02, 1.05 * hDiffRel->GetBinContent(hDiffRel->GetMaximumBin()) +
              hDiffRel->GetBinError(hDiffRel->GetMaximumBin())));
    */
    hDiffRel->SetStats(0);
    TString hDiffRelcln = hDiffRel->ClassName();
    if (hDiffRelcln.Contains("TH2"))
      hDiffRel->Draw("colz");
    else if (hDiffRelcln.Contains("TH1"))
      DrawRelativeDifference(hDiffRel);
    else
      hDiffRel->Draw();
  }

  c1->cd(1);
  toutc->Draw();
  more->Draw("same");
  c1->SaveAs(Form("%s_Difference.png", hA->GetName()));
  fileSummaryOutput = new TFile("Summary.root", "update");
  c1->Write(Form("%s%s_Difference", prefix.Data(), hA->GetName()));
  // fileSummaryOutput->ls();
  fileSummaryOutput->Close();
  if (finalComparison) {
    c1->Print("plots.pdf");
    c1->Print("plots.pdf]");
  } else
    c1->Print("plots.pdf");
}

void DrawRatio(TH1* hR)
{
  hR->SetMarkerStyle(20);
  hR->SetMarkerSize(0.5);
  hR->SetMinimum(
    TMath::Max(0.98, 0.95 * hR->GetBinContent(hR->GetMinimumBin()) -
                       hR->GetBinError(hR->GetMinimumBin())));
  hR->SetMaximum(
    TMath::Min(1.02, 1.05 * hR->GetBinContent(hR->GetMaximumBin()) +
                       hR->GetBinError(hR->GetMaximumBin())));
  hR->SetStats(0);
  hR->GetYaxis()->SetTitle("Ratio");
  hR->Draw("P");
  return;
}

void DrawRelativeDifference(TH1* hR)
{
  hR->SetMarkerStyle(20);
  hR->SetMarkerSize(0.5);
  hR->SetMinimum(
    TMath::Max(-0.02, 1.05 * hR->GetBinContent(hR->GetMinimumBin()) -
                        hR->GetBinError(hR->GetMinimumBin())));
  hR->SetMaximum(
    TMath::Min(0.02, 1.05 * hR->GetBinContent(hR->GetMaximumBin()) +
                       hR->GetBinError(hR->GetMaximumBin())));
  hR->SetStats(0);
  hR->GetYaxis()->SetTitle("RelativeDifference");
  hR->Draw("P");
  return;
}

void SelectCriticalHistos()
{
  printf("Select all critical plots..... \n");

  vector<string> NamesFromTheList;
  fileSummaryOutput = new TFile("Summary.root", "READ");
  fileSummaryOutput->ls();

  ifstream InputFile;
  InputFile.open("CriticalPlots.txt");
  string string;
  while (!InputFile.eof()) // To get all the lines
  {
    std::getline(InputFile, string); // Save the names in a string
    NamesFromTheList.push_back(
      string); // Save the histo names in the string vector
    cout << string << endl;
  }
  InputFile.close();

  // access the string vector elements
  std::cout << "Access the elements of the list of critical..." << std::endl;
  for (int i = 0; i < NamesFromTheList.size(); i++) {
    cout << NamesFromTheList[i] << endl;
  }
  TCanvas* critic_pdf = new TCanvas("critic_pdf", "critic_pdf");
  critic_pdf->Print("critical.pdf[");

  int Nkeys = fileSummaryOutput->GetNkeys();
  std::cout << "In the summary file there are " << Nkeys << " plots. \n "
            << std::endl;
  TList* Lkeys = fileSummaryOutput->GetListOfKeys();
  for (int j = 0; j < Nkeys; j++) {
    std::cout << "case " << j << std::endl;
    TKey* k = (TKey*)Lkeys->At(j);
    TString Cname = k->GetClassName();
    TString Oname = k->GetName();
    std::cout << Oname << " " << Cname << std::endl;
    for (int i = 0; i < NamesFromTheList.size(); i++) {
      std::cout << NamesFromTheList[i] << std::endl;
      if (Oname.Contains(NamesFromTheList[i]) && NamesFromTheList[i] != "") {
        std::cout << " name file and name from the list: " << Oname << " e "
                  << NamesFromTheList[i] << std::endl;
        TCanvas* ccc =
          static_cast<TCanvas*>(fileSummaryOutput->Get(Oname.Data()));
        // ccc->Draw();
        ccc->Print("critical.pdf");
      }
    }
  }
  critic_pdf->Print("critical.pdf]");
  return;
}

// chi2. critical test
struct results CompareChiSquare(TH1* hA, TH1* hB, double val)
{
  struct results res;
  res.testname = "Chi2 test";
  res.critical = true;

  res.passed = true;

  // not comparable if some difference in the bins is detected
  if (!PotentiallySameAxes(hA, hB)) {
    res.comparable = false;
    printf("%s: %s can not be performed\n", hA->GetName(), res.testname.Data());
    return res;
  } else {
    res.comparable = true;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  if ((integralA == 0) || (integralB == 0)) {
    printf("At least one of the histograms %s is empty \n", hA->GetName());
    res.passed = false;
    return res;
  }

  double chi2 = 0;

  int nBins = 0;
  for (int ix = 1; ix <= hA->GetNbinsX(); ix++) {
    for (int iy = 1; iy <= hA->GetNbinsY(); iy++) {
      for (int iz = 1; iz <= hA->GetNbinsZ(); iz++) {
        double cA = hA->GetBinContent(ix, iy, iz);
        double eA = 0;
        if (cA < 0) {
          printf("Negative counts!!! cA=%f in bin %d %d %d\n", cA, ix, iy, iz);
          res.passed = false;
          return res;
        } else
          eA = TMath::Sqrt(cA);
        double cB = hB->GetBinContent(ix, iy, iz);
        double eB = 0;
        if (cB < 0) {
          printf("Negative counts!!! cB=%f in bin %d %d %d\n", cB, ix, iy, iz);
          res.passed = false;
          return res;
        } else
          eB = TMath::Sqrt(cB);
        double diff = cA * TMath::Sqrt(integralB / integralA) - cB * TMath::Sqrt(integralA / integralB);
        double correl = 0.;
        if (correlationCase == 1) {
          // estimate degree of correlation from number of events in histogram
          // assume that the histogram with less events is a subsample of that
          // with more events
          if ((cB > cA) && (cB > 0))
            correl = TMath::Sqrt(cA / cB);
          if ((cA > cB) && (cA > 0))
            correl = TMath::Sqrt(cB / cA);
        }
        double sigma2 = eA * eA + eB * eB - 2 * correl * eA * eB; // maybe to be improved
        if (sigma2 > 0)
          chi2 += diff * diff / sigma2;
        nBins++;
      }
    }
  }
  if (nBins > 0) {
    res.value = chi2 / nBins;
    printf("%s: %s performed: chi2/nBins=%f \n", hA->GetName(), res.testname.Data(), res.value);
    if (res.value < val) {
      printf("       ---> COMPATIBLE\n");
      res.passed = true;
    } else {
      printf("       ---> BAD\n");
      res.passed = false;
    }

    return res;
  }

  res.passed = false;
  printf(" Histograms with empty bins");
  return res;
}

//(normalized) difference of bin content. critical test
struct results CompareBinContent(TH1* hA, TH1* hB, double val)
{
  struct results res;
  res.testname = "Bin cont test";

  res.critical = true;

  res.passed = true;

  // not comparable if some difference in the bins is detected
  if (!PotentiallySameAxes(hA, hB)) {
    res.comparable = false;
    printf("%s: %s can not be performed\n", hA->GetName(), res.testname.Data());
    return res;
  } else {
    res.comparable = true;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  if ((integralA == 0) || (integralB == 0)) {
    printf("At least one histogram is empty \n");
    res.passed = false;
    return res;
  }

  double meandiff = 0;

  int nBins = 0;
  for (int ix = 1; ix <= hA->GetNbinsX(); ix++) {
    for (int iy = 1; iy <= hA->GetNbinsY(); iy++) {
      for (int iz = 1; iz <= hA->GetNbinsZ(); iz++) {
        double cA = hA->GetBinContent(ix, iy, iz);
        if (cA < 0) {
          printf("Negative counts!!! cA=%f in bin %d %d %d\n", cA, ix, iy, iz);
          res.passed = false;
          return res;
        }
        double cB = hB->GetBinContent(ix, iy, iz);
        if (cB < 0) {
          printf("Negative counts!!! cB=%f in bin %d %d %d\n", cB, ix, iy, iz);
          res.passed = false;
          return res;
        }
        if ((cA > 0) || (cB > 0)) {
          meandiff += TMath::Abs(cA / integralA - cB / integralB);
          nBins++;
        }
      }
    }
  }
  meandiff = meandiff * TMath::Sqrt((integralA + integralB) / (2 * nBins));
  if (nBins > 0) {
    res.value = meandiff;
    printf("%s: %s performed: meandiff=%f \n", hA->GetName(), res.testname.Data(), res.value);
    if (res.value < val) {
      printf("       ---> COMPATIBLE\n");
      res.passed = true;
    } else {
      printf("       ---> BAD\n");
      res.passed = false;
    }

    return res;
  }

  res.passed = false;
  printf(" Histograms with empty bins");
  return res;
}

// compare number of entries. non-critical
struct results CompareNentr(TH1* hA, TH1* hB, double val)
{
  struct results res;
  res.testname = "Num entries test";

  res.critical = false;

  res.passed = true;

  // check only if the range of the histogram is the same, do no care about bins
  if (!PotentiallySameRange(hA, hB)) {
    res.comparable = false;
    printf("%s: %s can not be performed\n", hA->GetName(), res.testname.Data());
    return res;
  } else {
    res.comparable = true;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  double entriesdiff = TMath::Abs(integralA - integralB) / ((integralA + integralB) / 2);

  res.value = entriesdiff;
  printf("%s: %s performed: entriesdiff=%f \n", hA->GetName(), res.testname.Data(), res.value);
  if (res.value < val) {
    printf("       ---> COMPATIBLE\n");
    res.passed = true;
  } else {
    printf("       ---> BAD\n");
    res.passed = false;
  }

  return res;
}

void WriteSingleJSONKeyVal(std::ofstream& os, std::vector<std::string> const& labels, std::string const& key, std::string const& last = ",")
{
  os << "  \"" << key << "\": [";
  for (auto& l : labels) {
    os << "\"" << l << "\"";
    if (l != labels.back())
      os << ",";
  }
  os << "]" << last << "\n";
}

// write the result of the check into a .json file. One list for each possible outcome
void WriteToJson(TH2F* hSum)
{
  std::vector<std::string> good, warning, bad, nc, critical_nc;
  int nhists = hSum->GetYaxis()->GetNbins();

  for (int i = 1; i <= nhists; i++) {
    double res = hSum->GetBinContent(1, i);
    const char* label = hSum->GetYaxis()->GetBinLabel(i);
    if (res == 0)
      bad.push_back(label);
    if (res == 0.5)
      warning.push_back(label);
    if (res == 1)
      good.push_back(label);
    if (res == -0.25)
      nc.push_back(label);
    if (res == -0.5)
      critical_nc.push_back(label);
  }

  std::ofstream jsonout("Summary.json");
  jsonout << "{\n";
  WriteSingleJSONKeyVal(jsonout, good, "GOOD");
  WriteSingleJSONKeyVal(jsonout, warning, "WARNING");
  WriteSingleJSONKeyVal(jsonout, bad, "BAD");
  WriteSingleJSONKeyVal(jsonout, critical_nc, "CRIT_NC");
  WriteSingleJSONKeyVal(jsonout, nc, "NONCRIT_NC", "");
  jsonout << "}";

  jsonout.close();
}
