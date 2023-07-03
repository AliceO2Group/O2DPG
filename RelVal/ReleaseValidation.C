#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include "PlotOverlays.C"

struct TestResult {
  double value = 0.0;
  bool comparable = true;
  std::string testname;
};

// define the possible available tests
struct TestFlag {
  static constexpr int CHI2 = 0;
  static constexpr int KOLMOGOROV = 1;
  static constexpr int NENTRIES = 2;
  static constexpr int LAST = NENTRIES;
  // ...
};

bool shouldRunTest(int userTests, int flag)
{
  return (userTests & (1 << flag)) > 0;
}

int maxUserTests()
{
  int maxTestNumber = 0;
  for (int i = 0; i <= TestFlag::LAST; i++) {
    maxTestNumber += (1 << i);
  }
  return maxTestNumber;
}

// define a global epsilon
double EPSILON = 0.00001;

void CompareHistos(TH1* hA, TH1* hB, int whichTests, std::unordered_map<std::string, std::vector<TestResult>>& allTests, std::string const& labelA, std::string const& labelB);
bool PotentiallySameHistograms(TH1*, TH1*);
TestResult CompareChiSquare(TH1* hA, TH1* hB, bool areComparable);
TestResult CompareKolmogorov(TH1* hA, TH1* hB, bool areComparable);
TestResult CompareNentr(TH1* hA, TH1* hB, bool areComparable);
void DrawRatio(TH1* hR);
void SelectCriticalHistos();
const char* MapResultToLabel(TestResult const& testResult);
void WriteTestResultsToJson(std::ofstream& json, std::string const& key, std::vector<TestResult> const& testResults);
void WriteToJsonFromMap(std::unordered_map<std::string, std::vector<TestResult>> const& allTestsMap);

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

// what to give as input:
// 1) name and path of first file,
// 2) name and path of second file,
// 3) object to analyse (it can be a MonitorObject or a TDirectory); when left  empty, loop on all objects; 4) which test to perform: 1->Chi-square; 2--> BinContDiff; 3 --> Chi-square + BinContDiff; 4-> EntriesDiff; 5--> EntriesDiff + Chi2; 6 -->  EntriesDiff + BinContDiff; 7 --> EntriesDiff + Chi2 + BinContDiff;
// 4), 5) and 6) threshold values for chi2, bin cont and N entries checks;
// 6) select if files have to be taken from the grid or not
// 7) choose if specific critic plots have to be saved in a second .pdf file

void ReleaseValidation(std::string const& filename1, std::string const& filename2, int whichTests, std::string const& labelA="batch_i", std::string const& labelB="batch_j")
{
  gROOT->SetBatch();

  auto maxTestNumber = maxUserTests();
  if (whichTests < 1 || whichTests > maxTestNumber) {
    std::cerr << "ERROR: Max test number is " << maxTestNumber << " to perform all tests. Otherwise please enable bits where the last possible bit is " << TestFlag::LAST << "\n";
    return;
  }

  TFile extractedFile1(filename1.c_str());
  TFile extractedFile2(filename2.c_str());

  // prepare summary plots
  int nkeys = extractedFile1.GetNkeys();

  // collect test results to store them as JSON later
  std::unordered_map<std::string, std::vector<TestResult>> allTestsMap;

  TIter next(extractedFile1.GetListOfKeys());
  TKey* key{};
  int nSimilarHistos{};
  int nComparisons{};
  int nNotFound{};
  std::vector<std::string> collectSimilarHistos;

  while ((key = static_cast<TKey*>(next()))) {
    // At this point we expect objects deriving from TH1 only since that is what we extracted
    auto hA = static_cast<TH1*>(key->ReadObj());
    auto oname = key->GetName();
    auto hB = static_cast<TH1*>(extractedFile2.Get(oname));

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

    CompareHistos(hA, hB, whichTests, allTestsMap, labelA, labelB);

    nComparisons++;
  }
  std::cout << "\n##### Summary #####\nNumber of histograms compared: " << nComparisons
            << "\nNumber of potentially same histograms: " << nSimilarHistos << "\n";
  for (auto& csh : collectSimilarHistos) {
    std::cout << " -> " << csh << "\n";
  }
  std::cout << "\nNumber of histograms only found in first but NOT second file: " << nNotFound << "\n";

  WriteToJsonFromMap(allTestsMap);
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
    std::cerr << "At least one of the histograms " << hA->GetName() << " is empty\n";
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

void CompareHistos(TH1* hA, TH1* hB, int whichTests, std::unordered_map<std::string, std::vector<TestResult>>& allTests, std::string const& labelA, std::string const& labelB)
{

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  // Bit Mask
  // my 3 possible tests are: 1) chi2;  2) meandiff; 3) entriesdiff.  These tests can be combined in 7 different ways
  // std::vector<std::string> tests;

  auto areComparable = CheckComparable(hA, hB);

  TLegend* legendMetricsOverlayPlot = new TLegend(0.65, 0.6, 0.9, 0.8);
  legendMetricsOverlayPlot->SetBorderSize(1);
  legendMetricsOverlayPlot->SetFillStyle(0);

  // test if each of the 3 bits is turned on in subset ‘i = whichTests’?
  // if yes, process the bit

  if (shouldRunTest(whichTests, TestFlag::CHI2)) {
    auto testResult = CompareChiSquare(hA, hB, areComparable);
    RegisterTestResult(allTests, hA->GetName(), testResult);
    if (testResult.comparable) {
      legendMetricsOverlayPlot->AddEntry((TObject*)nullptr, Form("#chi^{2} / N_{bins} = %f", testResult.value), "");
    }
  }

  if (shouldRunTest(whichTests, TestFlag::KOLMOGOROV)) {
    auto testResult = CompareKolmogorov(hA, hB, areComparable);
    RegisterTestResult(allTests, hA->GetName(), testResult);
    if (testResult.comparable) {
      legendMetricsOverlayPlot->AddEntry((TObject*)nullptr, Form("Kolmogorov prob. = %f", testResult.value), "");
    }
  }

  if (shouldRunTest(whichTests, TestFlag::NENTRIES)) {
    auto testResult = CompareNentr(hA, hB, areComparable);
    RegisterTestResult(allTests, hA->GetName(), testResult);
    if (testResult.comparable) {
      legendMetricsOverlayPlot->AddEntry((TObject*)nullptr, Form("entriesdiff = %f", testResult.value), "");
    }
  }

  if (isEmptyHisto(hA) == 2 || isEmptyHisto(hB) == 2) {
    std::cerr << "WARNING: Cannot draw histograms due to the fact that all entries are in under- or overflow bins\n";
    return;
  }

  std::vector<TH1*> hVec{hA,hB};
  std::vector<std::string> labelVec{labelA,labelB};
  PlotOverlayAndRatio(hVec, labelVec, "overlayPlots", legendMetricsOverlayPlot);
}

// chi2
TestResult CompareChiSquare(TH1* hA, TH1* hB, bool areComparable)
{
  TestResult res;
  res.testname = "chi2";
  if (!areComparable) {
    res.comparable = false;
    return res;
  }

  res.value = hA->Chi2Test(hB, "CHI2/NDF");

  return res;
}

// Kolmogorov
TestResult CompareKolmogorov(TH1* hA, TH1* hB, bool areComparable)
{
  TestResult res;
  res.testname = "kolmogorov";
  if (!areComparable) {
    res.comparable = false;
    return res;
  }

  res.value = hA->KolmogorovTest(hB);

  return res;

}

// compare number of entries. non-critical
TestResult CompareNentr(TH1* hA, TH1* hB, bool areComparable)
{
  TestResult res;
  res.testname = "num_entries";
  if (!areComparable) {
    res.comparable = false;
    return res;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();
  double entriesdiff = TMath::Abs(integralA - integralB) / ((integralA + integralB) / 2);
  /*
  // alternative
  double errorA;
  double errorB;
  double integralA = hA->IntegralAndError(0,-1,errorA);
  double integralB = hB->IntegralAndError(0,-1,errorB);
  double error = TMath::Sqrt(errorA*errorA+errorB*errorB);
  double entriesdiff = TMath::Abs(integralA - integralB) / error;
  */
  res.value = entriesdiff;

  return res;
}

void WriteTestResultsToJson(std::ofstream& json, std::string const& key, std::vector<TestResult> const& testResults)
{
  json << "  \"" << key << "\": [\n";
  for (int i = 0; i < testResults.size(); i++) {
    auto& result = testResults[i];

    json << "    {\n";
    json << "      \"test_name\": \"" << result.testname << "\",\n";
    if (isnan(result.value)) {
      json << "      \"value\": null,\n";
    } else {
      json << "      \"value\": " << result.value << ",\n";
    }
    auto comparable = result.comparable ? "true" : "false";
    json << "      \"comparable\": " << comparable << "\n    }";
    if (i != testResults.size() - 1) {
      json << ",\n";
    }
  }
  json << "\n  ]";
}

void WriteToJsonFromMap(std::unordered_map<std::string, std::vector<TestResult>> const& allTestsMap)
{
  std::ofstream jsonout("RelVal.json");
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
