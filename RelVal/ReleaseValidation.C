#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>

TFile* fileSummaryOutput = nullptr;
TFile* fileTestSummary = nullptr;

TString prefix = "";
int correlationCase = 0; // at the moment I assume no error correlation ..

struct TestResult {
  double value = 0.0;
  bool comparable = true;
  std::string testname;
};

// define the possible available tests
struct TestFlag {
  static constexpr int CHI2 = 0;
  static constexpr int BINCONTNORM = 1;
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

void CompareHistos(TH1* hA, TH1* hB, int whichTests, bool firstComparison, bool finalComparison, std::unordered_map<std::string, std::vector<TestResult>>& allTests);
void PlotOverlayAndRatio(TH1* hA, TH1* hB, TLegend& legend, TString& compLabel, int color);
bool PotentiallySameHistograms(TH1*, TH1*);
TestResult CompareChiSquare(TH1* hA, TH1* hB, bool areComparable);
TestResult CompareChiSquareTH1(TH1* hA, TH1* hB, bool areComparable);
TestResult CompareBinContent(TH1* hA, TH1* hB, bool areComparable);
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

void ReleaseValidation(std::string const& filename1, std::string const& filename2, int whichTests)
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

  // open the two files (just created), look at the histograms and make statistical tests
  bool isLastComparison = false; // It is true only when the last histogram of the file is considered,
  // in order to properly close the pdf
  bool isFirstComparison = true; // to properly open the pdf file

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

    CompareHistos(hA, hB, whichTests, isFirstComparison, isLastComparison, allTestsMap);

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

void CompareHistos(TH1* hA, TH1* hB, int whichTests, bool firstComparison, bool finalComparison, std::unordered_map<std::string, std::vector<TestResult>>& allTests)
{

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  TString outc = "";
  int colt = 1;

  // Bit Mask
  // my 3 possible tests are: 1) chi2;  2) meandiff; 3) entriesdiff.  These tests can be combined in 7 different ways
  // std::vector<std::string> tests;

  auto areComparable = CheckComparable(hA, hB);

  TLegend legendOverlayPlot(0.6, 0.6, 0.9, 0.8);
  legendOverlayPlot.SetBorderSize(1);

  // test if each of the 3 bits is turned on in subset ‘i = whichTests’?
  // if yes, process the bit

  if (shouldRunTest(whichTests, TestFlag::CHI2)) {
    auto testResult = CompareChiSquare(hA, hB, areComparable);
    RegisterTestResult(allTests, hA->GetName(), testResult);
    if (testResult.comparable) {
      legendOverlayPlot.AddEntry((TObject*)nullptr, Form("#chi^{2} / N_{bins} = %f", testResult.value), "");
    }
  }

  if (shouldRunTest(whichTests, TestFlag::BINCONTNORM)) {
    auto testResult = CompareBinContent(hA, hB, areComparable);
    RegisterTestResult(allTests, hA->GetName(), testResult);
    if (testResult.comparable) {
      legendOverlayPlot.AddEntry((TObject*)nullptr, Form("meandiff = %f", testResult.value), "");
    }
  }

  if (shouldRunTest(whichTests, TestFlag::NENTRIES)) {
    auto testResult = CompareNentr(hA, hB, areComparable);
    RegisterTestResult(allTests, hA->GetName(), testResult);
    if (testResult.comparable) {
      legendOverlayPlot.AddEntry((TObject*)nullptr, Form("entriesdiff = %f", testResult.value), "");
    }
  }

  if (isEmptyHisto(hA) == 2 || isEmptyHisto(hB) == 2) {
    std::cerr << "WARNING: Cannot draw histograms due to the fact that all entries are in under- or overflow bins\n";
    return;
  }
  PlotOverlayAndRatio(hA, hB, legendOverlayPlot, outc, colt);
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

// (normalized) difference of bin content
TestResult CompareBinContent(TH1* hA, TH1* hB, bool areComparable)
{
  TestResult res;
  res.testname = "bin_cont";
  if (!areComparable) {
    res.comparable = false;
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
          std::cerr << "Negative counts!!! cA=" << cA << " in bin (" << ix << "," << iy << "," << iz << "\n";
          res.comparable = false;
          return res;
        }
        double cB = hB->GetBinContent(ix, iy, iz);
        if (cB < 0) {
          std::cerr << "Negative counts!!! cB=" << cB << " in bin (" << ix << "," << iy << "," << iz << "\n";
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
    std::cout << hA->GetName() << ": " << res.testname << " performed: meandiff=" << res.value << "\n";
    return res;
  }

  std::cerr << "Histogram with empty bins (" << hA->GetName() << ")\n";
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

  res.value = entriesdiff;
  std::cout << hA->GetName() << ": " << res.testname << " performed: entriesdiff=" << res.value << "\n";

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
