#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>

using namespace std;

TFile* fileSummaryOutput = nullptr;
TFile* fileTestSummary = nullptr;

TString prefix = "";
int correlationCase = 0; // at the moment I assume no error correlation ..

struct TestResult {
  bool passed;
  double value;
  double threshold;
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

// define a global epsilon
double EPSILON = 0.00001;

void CompareHistos(TH1* hA, TH1* hB, int whichTest, double valChi2, double valMeanDiff, double valEntriesDiff,
                   bool firstComparison, bool finalComparison, std::unordered_map<std::string, std::vector<TestResult>>& allTests);
void PlotOverlayAndRatio(TH1* hA, TH1* hB, TLegend& legend, TString& compLabel, int color);
bool PotentiallySameHistograms(TH1*, TH1*);
TestResult CompareChiSquare(TH1* hA, TH1* hB, double varChi2, bool areComparable);
TestResult CompareBinContent(TH1* hA, TH1* hB, double valMeanDiff, bool areComparable);
TestResult CompareNentr(TH1* hA, TH1* hB, double valEntriesDiff, bool areComparable);
void DrawRatio(TH1* hR);
void SelectCriticalHistos();
const char* MapResultToLabel(TestResult const& testResult);
void WriteTestResultsToJson(std::ofstream& json, std::string const& key, std::vector<TestResult> const& testResults);
void WriteToJsonFromMap(std::unordered_map<std::string, std::vector<TestResult>> const& allTestsMap);
void fillThresholdsFromFile(std::string const& inFilepath, std::unordered_map<std::string, std::vector<TestResult>>& allThresholds);

template <typename T>
T getThreshold(std::string const& histoName, std::string const& testName, std::unordered_map<std::string, std::vector<TestResult>> const& allThresholds, T defaultValue)
{
  std::cerr << "Extract threshold from value for histogram " << histoName << " and test " << testName << ", with default " << defaultValue << "\n";
  auto const& it = allThresholds.find(histoName);
  if (it == allThresholds.end()) {
    return defaultValue;
  }
  for (auto& test : it->second) {
    if (testName.compare(test.testname.Data()) == 0) {
      if (test.value == 0) {
        std::cerr << "The threshold was chosen to be 0, hence use deault value " << defaultValue << "\n";
        return defaultValue;
      }
      return test.value;
    }
  }
  std::cerr << "Could not extract threshold from value for histogram " << histoName << " and test " << testName << ", returning default " << defaultValue << "\n";
  return defaultValue;
}

void fillThresholdsFromFile(std::string const& inFilepath, std::unordered_map<std::string, std::vector<TestResult>>& allThresholds)
{
  if (inFilepath.empty()) {
    return;
  }
  std::ifstream inFile;
  inFile.open(inFilepath);
  std::string line;
  if (inFile.is_open()) {
    while (std::getline(inFile, line)) {
      std::istringstream ss(line);
      std::string token;
      // expect histoName,testName,value
      std::string tokens[3] = {"NULL", "NULL", "NULL"};
      int counter{0};
      while (counter < 3 && std::getline(ss, token, ',')) {
        tokens[counter] = token;
        std::cout << token << std::endl;
        counter++;
      }
      TestResult result;

      result.testname = tokens[1];
      if (tokens[2].compare("null") == 0 || tokens[2].compare("None") == 0) {
        continue;
      } else {
        result.value = std::stod(tokens[2]);
      }
      allThresholds[tokens[0]].push_back(result);
      std::cout << "Add test " << result.testname << " with value " << result.value << " for histogram " << tokens[0] << " to map" << std::endl;
    }
  }
}

void AddSummaryTest(std::unordered_map<std::string, std::vector<TestResult>>& allTests)
{
  // derive the summary from the single tests that were conducted
  for (auto& tests : allTests) {
    // summary test
    TestResult result;
    result.value = 0.;
    result.threshold = 0.;
    result.testname = "test_summary";
    result.passed = true;
    result.critical = true;
    result.comparable = true;
    bool sawAtLeastOneCritical = false;
    for (auto& test : tests.second) {
      if (test.critical) {
        if (!test.comparable || !test.passed) {
          result.passed = false;
          result.comparable = test.comparable;
          // a critical test failed --> break immediately cause that's the worst we can get
          break;
        }
        sawAtLeastOneCritical = true;
      }
      if (sawAtLeastOneCritical) {
        // only fill from non-critical if there has not yet been a critical to fill from
        continue;
      }
      result.passed = test.passed;
      result.comparable = test.comparable;
    }
    tests.second.push_back(result);
  }
}

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

int isEmptyHisto(TH1* h)
{
  // this tells us if and in which way a histogram is empty

  auto entries = h->GetEntries();
  if (!entries) {
    // no entries, definitely empty
    return 1;
  }

  if (entries && !h->Integral()) {
    // everything must have landed in the over- or underflow bins
    return 2;
  }
  return 0;
}

// overlay 2 1D histograms
void overlay1D(TH1* hA, TH1* hB, TLegend& legend, TString& compLabel, int color, std::string const& outputDir)
{
  TCanvas c("overlay", "", 800, 800);
  c.cd();
  hA->SetLineColor(kRed + 2);
  hA->SetLineStyle(1);
  hA->SetLineWidth(1);
  hA->SetStats(0);
  hB->SetLineColor(kBlue + 1);
  hB->SetLineStyle(10);
  hB->SetLineWidth(1);
  hB->SetStats(0);

  TRatioPlot rp(hA, hB);
  rp.Draw("same");
  rp.GetUpperPad()->cd();
  TLatex toutc(0.2, 0.85, compLabel.Data());
  toutc.SetNDC();
  toutc.SetTextColor(color);
  toutc.SetTextFont(62);
  toutc.Draw();
  legend.Draw();
  rp.GetLowerRefGraph()->SetMinimum(0.);
  rp.GetLowerRefGraph()->SetMaximum(10.);

  auto graph = rp.GetLowerRefGraph();
  auto xLow = hA->GetBinCenter(std::min(hA->FindFirstBinAbove(), hB->FindFirstBinAbove()));
  auto xUp = hA->GetBinCenter(std::min(hA->FindLastBinAbove(), hB->FindLastBinAbove()));
  TF1 func("func", "[0] * x + [1]", xLow, xUp);
  func.SetParameter(0, 0.);
  func.SetParameter(1, 1.);
  // find first and last bin above 0

  graph->Fit(&func, "EMR");
  rp.GetLowerPad()->cd();
  func.Draw("same");

  auto savePath = outputDir + "/" + hA->GetName() + ".png";
  c.SaveAs(savePath.c_str());
  c.Close();
}

// overlay 2 1D histograms
void overlay2D(TH2* hA, TH2* hB, TLegend& legend, TString& compLabel, int color, std::string const& outputDir)
{
  TCanvas c("overlay", "", 2400, 800);
  c.Divide(3, 1);
  c.cd(1);
  hA->SetStats(0);
  hA->Draw("colz");
  c.cd(2);
  hB->SetStats(0);
  hB->Draw("colz");
  auto hDiv = (TH2*)hA->Clone(Form("%s_ratio", hA->GetName()));
  hDiv->Divide(hB);
  c.cd(3);
  hDiv->Draw("colz");
  TLatex toutc(0.2, 0.85, compLabel.Data());
  toutc.SetNDC();
  toutc.SetTextColor(color);
  toutc.SetTextFont(62);
  toutc.Draw();
  legend.Draw();

  auto savePath = outputDir + "/" + hA->GetName() + ".png";
  c.SaveAs(savePath.c_str());
  c.Close();
}

// entry point for overlay plots
void PlotOverlayAndRatio(TH1* hA, TH1* hB, TLegend& legend, TString& compLabel, int color)
{
  std::string outputDir("overlayPlots");
  if (!std::filesystem::exists(outputDir)) {
    std::filesystem::create_directory(outputDir);
  }
  auto hA3D = dynamic_cast<TH3*>(hA);
  auto hB3D = dynamic_cast<TH3*>(hB);
  if (hA3D || hB3D) {
    std::cerr << "Cannot yet overlay 3D histograms\nSkipping " << hA->GetName() << "\n";
    return;
  }

  auto hA2D = dynamic_cast<TH2*>(hA);
  auto hB2D = dynamic_cast<TH2*>(hB);

  if (hA2D && hB2D) {
    // could be casted to 2D, so plot that
    // overlay2D(hA2D, hB2D, outputDir);
    overlay2D(hA2D, hB2D, legend, compLabel, color, outputDir);
    return;
  }

  overlay1D(hA, hB, legend, compLabel, color, outputDir);
}

// what to give as input:
// 1) name and path of first file,
// 2) name and path of second file,
// 3) object to analyse (it can be a MonitorObject or a TDirectory); when left  empty, loop on all objects; 4) which test to perform: 1->Chi-square; 2--> BinContDiff; 3 --> Chi-square + BinContDiff; 4-> EntriesDiff; 5--> EntriesDiff + Chi2; 6 -->  EntriesDiff + BinContDiff; 7 --> EntriesDiff + Chi2 + BinContDiff;
// 4), 5) and 6) threshold values for chi2, bin cont and N entries checks;
// 6) select if files have to be taken from the grid or not
// 7) choose if specific critic plots have to be saved in a second .pdf file

void ReleaseValidation(std::string const& filename1, std::string const& filename2,
                       int whichTest = 1, double valueChi2 = 1.5, double valueMeanDiff = 1.5, double valueEntriesDiff = 0.01,
                       bool selectCritical = false, const char* inFilepathThreshold = "")
{
  gROOT->SetBatch();

  if (whichTest < 1 || whichTest > 7) {
    std::cerr << "ERROR: Please select which test you want to perform:\n"
              << "1->Chi-square; 2--> ContBinDiff; 3 --> Chi-square+MeanDiff; 4->EntriesDiff; 5--> EntriesDiff + Chi2; 6 -->  EntriesDiff + MeanDiff; 7 --> EntriesDiff + Chi2 + MeanDiff\n";
    return;
  }

  TFile extractedFile1(filename1.c_str());
  TFile extractedFile2(filename2.c_str());

  // prepare summary plots
  int nkeys = extractedFile1.GetNkeys();
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

  // collect test results to store them as JSON later
  std::unordered_map<std::string, std::vector<TestResult>> allTestsMap;

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
  std::unordered_map<std::string, std::vector<TestResult>> inThresholds;
  fillThresholdsFromFile(inFilepathThreshold, inThresholds);
  while ((key = static_cast<TKey*>(next()))) {
    // At this point we expect objects deriving from TH1 only since that is what we extracted
    auto hA = static_cast<TH1*>(key->ReadObj());
    auto oname = key->GetName();
    auto hB = static_cast<TH1*>(extractedFile2.Get(oname));

    if (nComparisons + nNotFound == nkeys - 1)
      isLastComparison = true;

    if (!hB) {
      // That could still happen in case we compare either comletely different file by accident or something has been changed/added/removed
      std::cerr << "ERROR: Histogram " << oname << " not found in second batch continue with next\n";
      nNotFound++;
      continue;
    }
    if (PotentiallySameHistograms(hA, hB)) {
      collectSimilarHistos.push_back(hA->GetName());
      std::cerr << "WARNING: Found potentially same histogram " << oname << "\n";
      nSimilarHistos++;
    }

    std::cout << "Comparing " << hA->GetName() << " and " << hB->GetName() << "\n";

    auto valueChi2Use = getThreshold(hA->GetName(), "test_chi2", inThresholds, valueChi2);
    auto valueMeanDiffUse = getThreshold(hA->GetName(), "test_bin_cont", inThresholds, valueMeanDiff);
    auto valueEntriesDiffUse = getThreshold(hA->GetName(), "test_num_entries", inThresholds, valueEntriesDiff);
    std::cout << valueChi2Use << " " << valueMeanDiffUse << " " << valueEntriesDiffUse << "\n";

    CompareHistos(hA, hB, whichTest, valueChi2Use, valueMeanDiffUse, valueEntriesDiffUse, isFirstComparison, isLastComparison, allTestsMap);

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

  AddSummaryTest(allTestsMap);
  WriteToJsonFromMap(allTestsMap);
}

// setting the labels of the Z axis for the colz plot
void SetZLabels(TAxis* axis)
{
  axis->SetRangeUser(-0.7, 1.01);
  axis->SetNdivisions(10, kFALSE);
  axis->SetTickLength(0.);
  axis->ChangeLabel(1, -1, 0, -1, -1, -1, "");
  axis->ChangeLabel(2, -1, -1, -1, -1, -1, "#splitline{NOT COMPARABLE}{(critical)}");
  axis->ChangeLabel(3, -1, 0, -1, -1, -1, "");
  axis->ChangeLabel(4, -1, -1, -1, -1, -1, "#splitline{NOT COMPARABLE}{(non-critical)}");
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

////////////////////////////////////////////
// functionality for histogram comparison //
////////////////////////////////////////////

// keeps track if there was at least one failed/critical failed/non-comparable/... test
void SetTestResults(TestResult testResult, bool& test_failed, bool& criticaltest_failed, bool& test_nc, bool& criticaltest_nc, bool update = false)
{
  if (update && !testResult.critical) {
    return;
  }

  if (update) {
    test_failed = test_failed || !testResult.passed;
    criticaltest_nc = criticaltest_nc || !testResult.comparable;
    criticaltest_failed = criticaltest_failed || !testResult.passed;
    return;
  }

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

bool CheckComparable(TH1* hA, TH1* hB)
{
  if (!PotentiallySameAxes(hA, hB)) {
    std::cerr << "WARNING: Axes of histogram " << hA->GetName() << " appear to be different\n";
    return false;
  }

  auto isEmptyA = isEmptyHisto(hA);
  auto isEmptyB = isEmptyHisto(hB);

  if (isEmptyA == 2 || isEmptyB == 2) {
    std::cerr << "WARNING: All entries in histogram " << hA->GetName() << " appear to be in under- or overflow bins\n";
  }

  if (isEmptyA || isEmptyB) {
    printf("At least one of the histograms %s is empty \n", hA->GetName());
    return false;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  if (!isfinite(integralA) || !isfinite(integralB) || isnan(integralA) || isnan(integralB)) {
    std::cerr << "WARNING: Found NaN or non-finite integral for histogram " << hA->GetName() << "\n";
    return false;
  }
  return true;
}

void RegisterTestResult(std::unordered_map<std::string, std::vector<TestResult>>& allTests, std::string const& histogramName, TestResult const& testResult)
{
  allTests[histogramName].push_back(testResult);
}

void CompareHistos(TH1* hA, TH1* hB, int whichTest, double valChi2, double valMeanDiff, double valEntriesDiff,
                   bool firstComparison, bool finalComparison, std::unordered_map<std::string, std::vector<TestResult>>& allTests)
{

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  TString outc = "";
  int colt = 1;

  // Bit Mask
  // my 3 possible tests are: 1) chi2;  2) meandiff; 3) entriesdiff.  These tests can be combined in 7 different ways
  // std::vector<std::string> tests;

  bool test_failed = false;
  bool test_nc = false;
  bool criticaltest_failed = false;
  bool criticaltest_nc = false;

  TestResult testResult;
  auto areComparable = CheckComparable(hA, hB);

  TLegend more(0.6, 0.6, 0.9, 0.8);
  more.SetBorderSize(1);

  // test if each of the 3 bits is turned on in subset ‘i = whichTest’?
  // if yes, process the bit

  if ((whichTest & CHI2) == CHI2) {
    testResult = CompareChiSquare(hA, hB, valChi2, areComparable);
    SetTestResults(testResult, test_failed, criticaltest_failed, test_nc, criticaltest_nc);
    if (testResult.comparable)
      more.AddEntry((TObject*)nullptr, Form("#chi^{2} / Nbins = %f", testResult.value), "");
    RegisterTestResult(allTests, hA->GetName(), testResult);
  }

  if ((whichTest & BINCONTNORM) == BINCONTNORM) {
    testResult = CompareBinContent(hA, hB, valMeanDiff, areComparable);
    SetTestResults(testResult, test_failed, criticaltest_failed, test_nc, criticaltest_nc, true);
    if (testResult.comparable)
      more.AddEntry((TObject*)nullptr, Form("meandiff = %f", testResult.value), "");
    RegisterTestResult(allTests, hA->GetName(), testResult);
  }

  if ((whichTest & NENTRIES) == NENTRIES) {
    testResult = CompareNentr(hA, hB, valEntriesDiff, areComparable);
    SetTestResults(testResult, test_failed, criticaltest_failed, test_nc, criticaltest_nc, true);
    if (testResult.comparable)
      more.AddEntry((TObject*)nullptr, Form("entriesdiff = %f", testResult.value), "");
    RegisterTestResult(allTests, hA->GetName(), testResult);
  }

  if (isEmptyHisto(hA) == 2 || isEmptyHisto(hB) == 2) {
    std::cerr << "WARNING: Cannot draw histograms due to the fact that all entries are in under- or overflow bins\n";
    return;
  }
  PlotOverlayAndRatio(hA, hB, more, outc, colt);
}

void SelectCriticalHistos()
{
  printf("Select all critical plots..... \n");
  std::cerr << "Currently not supported\n";
  return;

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
}

// chi2. critical test
TestResult CompareChiSquare(TH1* hA, TH1* hB, double val, bool areComparable)
{
  TestResult res;
  res.threshold = val;
  res.testname = "test_chi2";
  res.critical = true;

  res.passed = false;
  res.comparable = areComparable;

  if (!areComparable) {
    return res;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();
  double chi2 = 0;

  int nBins = 0;
  for (int ix = 1; ix <= hA->GetNbinsX(); ix++) {
    for (int iy = 1; iy <= hA->GetNbinsY(); iy++) {
      for (int iz = 1; iz <= hA->GetNbinsZ(); iz++) {
        double cA = hA->GetBinContent(ix, iy, iz);
        double eA = 0;
        if (cA < 0) {
          printf("Negative counts!!! cA=%f in bin %d %d %d\n", cA, ix, iy, iz);
          res.comparable = false;
          return res;
        } else
          eA = TMath::Sqrt(cA);
        double cB = hB->GetBinContent(ix, iy, iz);
        double eB = 0;
        if (cB < 0) {
          printf("Negative counts!!! cB=%f in bin %d %d %d\n", cB, ix, iy, iz);
          res.comparable = false;
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
        if (cA > 0 || cB > 0) {
          nBins++;
        }
      }
    }
  }
  if (nBins > 0) {
    res.value = chi2 / nBins;
    printf("%s: %s performed: chi2/nBins=%f \n", hA->GetName(), res.testname.Data(), res.value);
    if (res.value <= val) {
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
TestResult CompareBinContent(TH1* hA, TH1* hB, double val, bool areComparable)
{
  TestResult res;
  res.threshold = val;
  res.testname = "test_bin_cont";

  res.critical = true;

  res.passed = false;
  res.comparable = areComparable;

  if (!areComparable) {
    return res;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();
  double meandiff = 0;

  int nBins = 0;
  for (int ix = 1; ix <= hA->GetNbinsX(); ix++) {
    for (int iy = 1; iy <= hA->GetNbinsY(); iy++) {
      for (int iz = 1; iz <= hA->GetNbinsZ(); iz++) {
        double cA = hA->GetBinContent(ix, iy, iz);
        if (cA < 0) {
          printf("Negative counts!!! cA=%f in bin %d %d %d\n", cA, ix, iy, iz);
          res.comparable = false;
          return res;
        }
        double cB = hB->GetBinContent(ix, iy, iz);
        if (cB < 0) {
          printf("Negative counts!!! cB=%f in bin %d %d %d\n", cB, ix, iy, iz);
          res.comparable = false;
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
    if (res.value <= val) {
      printf("       ---> COMPATIBLE\n");
      res.passed = true;
    } else {
      printf("       ---> BAD\n");
      res.passed = false;
    }
  }

  return res;
}

// compare number of entries. non-critical
TestResult CompareNentr(TH1* hA, TH1* hB, double val, bool areComparable)
{
  TestResult res;
  res.threshold = val;
  res.testname = "test_num_entries";

  if(TString(hA->GetName()).EndsWith("_ratioFromTEfficiency")){ //make NEntries-test critical when dealing with efficiencies
    res.critical = true;
  }
  else{
    res.critical = false;
  }
  

  res.passed = false;
  res.comparable = areComparable;

  if (!areComparable) {
    return res;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();
  double entriesdiff = TMath::Abs(integralA - integralB) / ((integralA + integralB) / 2);

  res.value = entriesdiff;
  printf("%s: %s performed: entriesdiff=%f \n", hA->GetName(), res.testname.Data(), res.value);
  if (res.value <= val) {
    printf("       ---> COMPATIBLE\n");
    res.passed = true;
  } else {
    printf("       ---> BAD\n");
    res.passed = false;
  }

  return res;
}

const char* MapResultToLabel(TestResult const& testResult)
{
  if (!testResult.passed) {
    if (testResult.critical) {
      if (!testResult.comparable) {
        return "CRIT_NC";
      }
      return "BAD";
    }
    if (!testResult.comparable) {
      return "NONCRIT_NC";
    }
    return "WARNING";
  }
  return "GOOD";
}

void WriteTestResultsToJson(std::ofstream& json, std::string const& key, std::vector<TestResult> const& testResults)
{
  json << "  \"" << key << "\": [\n";
  for (int i = 0; i < testResults.size(); i++) {
    auto& result = testResults[i];

    json << "    {\n";
    json << "      \"test_name\": \"" << result.testname.Data() << "\",\n";
    if (isnan(result.value)) {
      json << "      \"value\": null,\n";
    } else {
      json << "      \"value\": " << result.value << ",\n";
    }
    json << "      \"threshold\": " << result.threshold << ",\n";
    auto comparable = result.comparable ? "true" : "false";
    json << "      \"comparable\": " << comparable << ",\n";
    json << "      \"result\": \"" << MapResultToLabel(result) << "\"\n    }";
    if (i != testResults.size() - 1) {
      json << ",\n";
    }
  }
  json << "\n  ]";
}

void WriteToJsonFromMap(std::unordered_map<std::string, std::vector<TestResult>> const& allTestsMap)
{
  std::ofstream jsonout("Summary.json");
  jsonout << "{\n";
  int mapIndex = 0;
  int mapSize = allTestsMap.size();
  for (auto& testResult : allTestsMap) {
    WriteTestResultsToJson(jsonout, testResult.first, testResult.second);
    if (++mapIndex < mapSize) {
      jsonout << ",\n";
    }
  }
  jsonout << "\n}";
  jsonout.close();
}
