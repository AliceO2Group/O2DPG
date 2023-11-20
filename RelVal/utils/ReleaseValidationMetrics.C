#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>

// Wrapping the result of a certain metric calculation
struct MetricResult {
  std::string objectName;
  double value{};
  bool comparable = true;
  std::string name;
  bool lowerIsBetter = true;
  float proposedThreshold{};
  std::string ncCode;
};

struct NCCodes
{
  typedef int CODE;
  static constexpr CODE SANE = 0;
  static constexpr CODE OBJECTS_EMPTY = 1;
  static constexpr CODE OBJECTS_DIFFERENT_AXES = 2;
  static constexpr CODE OBJECTS_INTEGRAL_NAN = 3;
  static constexpr CODE METRIC_VALUE_NAN = 4;
  static constexpr CODE OBJECTS_NO_UNCERTAINTIES = 5;
  static constexpr CODE Last = OBJECTS_NO_UNCERTAINTIES;

   static constexpr const char* sCodes[Last + 1] = {"", "objects empty", "different axes", "integral NaN", "metric value NaN", "both objects without uncertainties"};

   static bool isComparable(CODE code)
   {
    return code == SANE;
   }
};

// Wrapping the calculation of a metric, making sure to set and return the MetricResult object
struct Metric
{
  Metric() = delete;
  Metric(std::string const& name, float proposedThreshold, std::function<NCCodes::CODE(TH1*, TH1*, MetricResult&)> evalFunc, bool lowerIsBetter=true) : name(name), proposedThreshold(proposedThreshold), evalFunc(evalFunc), lowerIsBetter(lowerIsBetter) {}

  bool lowerIsBetter = true;
  std::string name;
  std::function<NCCodes::CODE(TH1*, TH1*, MetricResult&)> evalFunc;
  float proposedThreshold{};

  MetricResult evaluate(TH1* hA, TH1* hB, NCCodes::CODE code) const
  {
    MetricResult metricResult;
    metricResult.objectName = hA->GetName();
    metricResult.comparable = NCCodes::isComparable(code);
    metricResult.lowerIsBetter = lowerIsBetter;
    metricResult.name = name;
    metricResult.proposedThreshold = proposedThreshold;
    if (metricResult.comparable) {
      code = evalFunc(hA, hB, metricResult);
    }
    if (isnan(metricResult.value)) {
      metricResult.comparable = false;
      code = NCCodes::METRIC_VALUE_NAN;
    }
    metricResult.ncCode = NCCodes::sCodes[code];
    metricResult.comparable = NCCodes::isComparable(code);
    return metricResult;
  }

  void print() const
  {
    std::cout << "METRIC: " << name << "\n" << "lowerIsBetter: " << lowerIsBetter << "\n";
  }
};

struct MetricRunner
{
  MetricRunner() = default;

  void disable(std::string const& name)
  {
    for (auto& metric : metricsEnabled) {
      if (metric && metric->name.compare(name) == 0) {
        // set to nullptr to not pick it up
        metric = nullptr;
        return;
      }
    }
  }

  void add(Metric metric)
  {
    metrics.push_back(metric);
  }

  void enable(std::string const& name="")
  {
    if (metricsEnabled.size() < metrics.size()) {
      metricsEnabled.resize(metrics.size(), nullptr);
    }

    for (int i = 0; i < metrics.size(); i++) {
      if (metricsEnabled[i]) {
        // update the pointer in case of vector changes
        metricsEnabled[i] = &metrics[i];
      }
      if (name.empty()) {
        // enable everything
        metricsEnabled[i] = &metrics[i];
        continue;
      }
      if (metrics[i].name.compare(name) == 0) {
        if (metricsEnabled[i]) {
          // There is a valid pointer at this position -- enabled
          return;
        }
        metricsEnabled[i] = &metrics[i];
      }
    }
  }

  void print() const
  {
    std::cout << "==> Following metrics are registered <==\n";
    for (int i = 0; i < metrics.size(); i++) {
      metrics[i].print();
      if (metricsEnabled.size() <= i || !metricsEnabled[i]) {
        std::cout << "  --> disabled\n";
        continue;
      }
      std::cout << "  --> enabled\n";
    }
  }

  void evaluate(TH1* hA, TH1* hB, NCCodes::CODE code)
  {
    for (auto& metric : metricsEnabled) {
      if (!metric) {
        // here is a nullptr so it is not active
        continue;
      }
      metricResults.push_back(metric->evaluate(hA, hB, code));
    }
  }

  int countEnabled()
  {
    int nEnabled{};
    for (auto& metric : metricsEnabled) {
      if (metric) {
        nEnabled++;
      }
    }
    return nEnabled;
  }

  std::vector<Metric> metrics;
  std::vector<Metric*> metricsEnabled;

  std::vector<MetricResult> metricResults;
};


void initialiseMetrics(MetricRunner& metricRunner) {
  Metric chiSquareMetric("chi2", 1.5, [](TH1* hA, TH1* hB, MetricResult& metricResult) { metricResult.value = hA->Chi2Test(hB, "CHI2/NDF"); return NCCodes::SANE; });
  Metric kolmogorovMetric("kolmogorov", 0.5, [](TH1* hA, TH1* hB, MetricResult& metricResult) { NCCodes::CODE code = NCCodes::OBJECTS_NO_UNCERTAINTIES;
                                                                                                for (int i = 1; i <= hA->GetNbinsX(); i++) {
                                                                                                  for (int j = 1; j <= hA->GetNbinsY(); j++) {
                                                                                                    for (int k = 1; k <= hA->GetNbinsZ(); k++) {
                                                                                                      auto eA = hA->GetBinError(i, j, k);
                                                                                                      auto eB = hB->GetBinError(i, j, k);
                                                                                                      if (eA > 0 || eB > 0) {
                                                                                                        code = NCCodes::SANE;
                                                                                                        break;
                                                                                                      }
                                                                                                    }
                                                                                                  }
                                                                                                }
                                                                                                if (code == NCCodes::SANE) {
                                                                                                  metricResult.value = hA->KolmogorovTest(hB);
                                                                                                }
                                                                                                return code; }, false);
  Metric numEntriesMetric("num_entries", 0.1, [](TH1* hA, TH1* hB, MetricResult& metricResult) { double integralA = TMath::Abs(hA->Integral());
                                                                                                 double integralB = TMath::Abs(hB->Integral());
                                                                                                 metricResult.value = TMath::Abs(integralA - integralB) / ((integralA + integralB) / 2);
                                                                                                 return NCCodes::SANE; });
  metricRunner.add(chiSquareMetric);
  metricRunner.add(kolmogorovMetric);
  metricRunner.add(numEntriesMetric);
}

int ReleaseValidationMetrics()
{
  MetricRunner metricRunner;
  initialiseMetrics(metricRunner);
  metricRunner.enable();
  metricRunner.print();
  return 0;
}


