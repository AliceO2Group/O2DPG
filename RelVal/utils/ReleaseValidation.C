#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include "ReleaseValidationMetrics.C"

// define a global epsilon
constexpr double EPSILON = 0.00001;

NCCodes::CODE CheckComparable(TH1* hA, TH1* hB);
void CompareHistos(TH1* hA, TH1* hB, std::string const& labelA, std::string const& labelB);
bool PotentiallySameHistograms(TH1*, TH1*);
void DrawRatio(TH1* hR);
void WriteMetricResultsToJson(std::ofstream& json, MetricResult const& metricResult);
void WriteToJsonFromMap(MetricRunner const&);

bool checkFileOpen(TFile* file)
{
  return (file && !file->IsZombie());
}

template <typename T>
bool areSufficientlyEqualNumbers(T a, T b, T epsilon = static_cast<T>(EPSILON))
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

int ReleaseValidation(std::string const& filename1, std::string const& filename2, std::string const& withMetrics="", std::string const& withoutMetrics="")
{
  gROOT->SetBatch();

  MetricRunner metricRunner;
  initialiseMetrics(metricRunner);

  // enabled requested metrics
  if (withMetrics.empty()) {
    metricRunner.enable();
  } else {
    std::istringstream iss(withMetrics);
    std::string metricName;
    while (std::getline(iss, metricName, ';')) {
      metricRunner.enable(metricName);
    }
  }
  if (!withoutMetrics.empty()) {
    std::istringstream iss(withoutMetrics);
    std::string metricName;
    while (std::getline(iss, metricName, ';')) {
      metricRunner.disable(metricName);
    }
  }

  if (metricRunner.countEnabled() < 1) {
    std::cerr << "No metrics enabled, returning...\n";
    return 1;
  }

  TFile extractedFile1(filename1.c_str());
  TFile extractedFile2(filename2.c_str());

  int nkeys = extractedFile1.GetNkeys();
  TIter next(extractedFile1.GetListOfKeys());
  TKey* key{};

  int nSimilarHistos{};
  int nComparisons{};
  int nNotFound{};
  int nCannotRead{};
  std::vector<std::string> collectSimilarHistos;

  while ((key = static_cast<TKey*>(next()))) {
    // At this point we expect objects deriving from TH1 only since that is what we extracted
    auto hA = static_cast<TH1*>(key->ReadObj());

    if (!hA) {
      std::cerr << "ERROR: Object " << key->GetName() << " does not seem to derive from TH1, skip\n";
      nCannotRead++;
      continue;
    }
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

    auto ncCode = CheckComparable(hA, hB);
    auto areComparable = NCCodes::isComparable(ncCode);

    metricRunner.evaluate(hA, hB, ncCode);

    nComparisons++;
  }
  std::cout << "\n##### Summary #####\nNumber of objects compared: " << nComparisons
            << "\nNumber of potentially same objects: " << nSimilarHistos << "\n";
  for (auto& csh : collectSimilarHistos) {
    std::cout << " -> " << csh << "\n";
  }
  std::cout << "\nNumber of objects only found in first but NOT second file: " << nNotFound << "\n";
  std::cout << "\nNumber of objects that could not be read from file: " << nCannotRead << "\n";

  WriteToJsonFromMap(metricRunner);

  extractedFile1.Close();
  extractedFile2.Close();

  return 0;
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
NCCodes::CODE CheckComparable(TH1* hA, TH1* hB)
{
  if (!PotentiallySameAxes(hA, hB)) {
    std::cerr << "WARNING: Axes of histogram " << hA->GetName() << " appear to be different\n";
    return NCCodes::OBJECTS_DIFFERENT_AXES;
  }

  auto isEmptyA = isEmptyHisto(hA);
  auto isEmptyB = isEmptyHisto(hB);

  if (isEmptyA == 2 || isEmptyB == 2) {
    std::cerr << "WARNING: All entries in histogram " << hA->GetName() << " appear to be in under- or overflow bins\n";
  }

  if (isEmptyA || isEmptyB) {
    std::cerr << "At least one of the histograms " << hA->GetName() << " is empty\n";
    return NCCodes::OBJECTS_EMPTY;
  }

  double integralA = hA->Integral();
  double integralB = hB->Integral();

  if (!isfinite(integralA) || !isfinite(integralB) || isnan(integralA) || isnan(integralB)) {
    std::cerr << "WARNING: Found NaN or non-finite integral for histogram " << hA->GetName() << "\n";
    return NCCodes::OBJECTS_INTEGRAL_NAN;
  }
  return NCCodes::SANE;
}


void WriteMetricResultsToJson(std::ofstream& json, MetricResult const& metricResult)
{
  json << "    {\n";
  json << "      \"object_name\": \"" << metricResult.objectName << "\",\n";
  json << "      \"metric_name\": \"" << metricResult.name << "\",\n";
  json << "      \"non_comparable_note\": \"" << metricResult.ncCode << "\",\n";
  json << "      \"lower_is_better\": " << metricResult.lowerIsBetter << ",\n";
  json << "      \"proposed_threshold\": " << metricResult.proposedThreshold << ",\n";
  if (!metricResult.comparable) {
    json << "      \"value\": null,\n";
  } else {
    json << "      \"value\": " << metricResult.value << ",\n";
  }
  json << "      \"comparable\": " << metricResult.comparable << "\n    }";
}

void WriteToJsonFromMap(MetricRunner const& metricRunner)
{
  std::ofstream jsonout("RelVal.json");
  jsonout << "{\n" << "  \"objects\": [\n";
  int mapIndex = 0;
  int mapSize = metricRunner.metricResults.size();
  for (auto& metricResult : metricRunner.metricResults) {
    WriteMetricResultsToJson(jsonout, metricResult);
    if (++mapIndex < mapSize) {
      // this puts a comma except for the very last entry
      jsonout << ",\n";
    }
  }
  jsonout << "\n  ]\n}";
  jsonout.close();
}
