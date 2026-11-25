// Copyright 2019-2026 CERN and copyright holders of ALICE O2.
// See https://alice-o2.web.cern.ch/copyright for details of the copyright holders.
// All rights not expressly granted are reserved.
//
// This software is distributed under the terms of the GNU General Public
// License v3 (GPL Version 3), copied verbatim in the file "COPYING".
//
// In applying this license CERN does not waive the privileges and immunities
// granted to it by virtue of its status as an Intergovernmental Organization
// or submit itself to any jurisdiction.

/// \file GeneratorMonopoles.C
/// \brief Configurable external generator for BSM magnetic monopoles
/// \author M. Giacalone - November 2026
/// co-authored with Claude Opus 5.5
///
/// A JSON-driven external O2 generator for magnetic monopoles. Every kinematic
/// quantity can be set to a fixed value, to a weighted list of values, or drawn
/// from a range with a choice of distributions (see MonoValue below).
///
/// Production modes ("mode" in the JSON):
///   "schwinger" : monopole / antimonopole pair, back-to-back in the pair rest
///                 frame, as produced by the Schwinger mechanism in the field of
///                 an ultraperipheral heavy-ion collision. The defaults
///                 reproduce the PbPb HepMC samples
///                 (PbPb_MMs_mass<M>GeV_g<G>_N*.hepmc): isotropic emission and
///                 a Maxwell-Juettner momentum spectrum
///                     dN/dp propto p^2 exp(-sqrt(p^2+m^2)/T),  T = 18.37 GeV
///                 which was obtained by an unbinned maximum-likelihood fit to
///                 those files (chi2/ndf ~ 1.0 for m = 100 and 200 GeV, g = 1
///                 and 3; the spectrum does not depend on the magnetic charge).
///   "single"    : independent single monopoles, charge sign fixed or random.
///
/// New modes only need a new entry in the EMode enum, in parseMode() and in
/// generateEvent(); everything else (sampling, consistency checks, bookkeeping)
/// is shared.
///
/// IMPORTANT - transport consistency
/// The transported monopole mass and magnetic charge are *transport* settings,
/// G4.monopoleMass and G4.monopoleMagneticCharge, and they live in a different
/// process than the generator, so this generator cannot set them. It instead
/// reads them back and refuses to run with an inconsistent configuration (see
/// the "transport" JSON block). Use MonopolesTransportKeys() in this same macro
/// to derive the matching --configKeyValues string from the very same JSON file.
///
/// Usage
/// The easiest way is the ini file, which sets the generator and the transport
/// settings at once:
///   o2-sim -g external -n 10 \
///     --configFile $O2DPG_MC_CONFIG_ROOT/MC/config/BSM/ini/GeneratorMonopolesSchwinger.ini
/// or on the command line, where every key has to be given explicitly:
///   o2-sim -g external -n 10 \
///     --configKeyValues "GeneratorExternal.fileName=GeneratorMonopoles.C+;GeneratorExternal.funcName=GeneratorMonopoles(\"cfg.json\");G4.monopole=1;G4.monopoleMass=100;G4.monopoleMagneticCharge=1"
///
/// The trailing "+" on fileName is mandatory: the macro is compiled with ACLiC
/// because cling cannot interpret it (it autoparses FairRoot's dictionary
/// payload, which does not compile).
///
/// Where ACLiC puts the build products (GeneratorMonopoles_C.so, .d, _rdict.pcm):
///   * next to the macro, when that directory is writable - a local checkout;
///   * in a temporary directory as soon as it is not, which is the case for an
///     installation on CVMFS. The target is $TMPDIR when it is set and exists,
///     and /tmp otherwise, with the user name appended (/tmp/<user>/...), so a
///     Grid job never tries to write into the installation and does not need
///     $TMPDIR to be set at all.
/// This macro needs an O2 that carries the monopole integration:
/// SimulationDataFormat/MonopoleParticles.h, the G4.monopole / G4.monopoleMass /
/// G4.monopoleMagneticCharge keys of o2::conf::G4Params and the two-argument
/// O2DatabasePDG::addALICEParticles(). It does not compile against an older O2,
/// by design - there is no fallback that could silently produce monopoles the
/// transport does not know.
///
/// The JSON keys are documented where they are read, in readConfig() below, and
/// the three configurations next to this file are working examples:
///   monopoles_schwinger_PbPb.json  the reference PbPb Schwinger production
///   monopoles_single.json          single monopoles, flat in pT and eta
///   monopoles_showcase.json        every knob in one file, for reference

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include <rapidjson/document.h>
#include <rapidjson/error/en.h>
#include <rapidjson/istreamwrapper.h>

#include <TDatabasePDG.h>
#include <TF1.h>
#include <TParticlePDG.h>
#include <TParticle.h>
#include <TLorentzVector.h>
#include <TRandom.h>
#include <TVector3.h>

#include <fairlogger/Logger.h>

#include "SimConfig/G4Params.h"
#include "Generators/Generator.h"
#include "SimulationDataFormat/MCEventHeader.h"
#include "SimulationDataFormat/MCUtils.h"

#include "Generators/PrimaryGeneratorParam.h"
#include "CommonUtils/FileSystemUtils.h"
#include "SimulationDataFormat/MonopoleParticles.h"
#include "SimulationDataFormat/O2DatabasePDG.h"

namespace o2::eventgen
{

/// PDG codes and default mass of the monopole species, from O2 itself
/// (SimulationDataFormat/MonopoleParticles.h), so that this generator, the PDG
/// table and the transport cannot drift apart.
constexpr int kMonopolePdgSymm = o2::sim::MonopolePdgSymm;   ///< equal electric and magnetic charge
constexpr int kMonopolePdgAsymm = o2::sim::MonopolePdgAsymm; ///< opposite electric and magnetic charge
constexpr double kMonopoleMassDefaultGeV = o2::sim::MonopoleMassDefaultGeV;
/// Default of G4.monopoleMagneticCharge in o2::conf::G4Params, for which O2 has no named constant.
constexpr double kMonopoleMagneticChargeDefault = 1.;

/// Reject unknown keys, so that a typo is an error instead of a silently ignored setting.
inline void checkKeys(const rapidjson::Value& node, const std::string& prefix,
                      const std::vector<std::string>& allowed)
{
  for (auto it = node.MemberBegin(); it != node.MemberEnd(); ++it) {
    const std::string k = it->name.GetString();
    if (std::find(allowed.begin(), allowed.end(), k) == allowed.end()) {
      std::ostringstream os;
      os << "unknown key \"" << (prefix.empty() ? k : prefix + "." + k) << "\". Known keys here:";
      for (const auto& a : allowed) {
        os << " " << a;
      }
      throw std::runtime_error(os.str());
    }
  }
}

/// Temperature of the Maxwell-Juettner spectrum fitted to the reference PbPb
/// Schwinger HepMC samples, in GeV.
constexpr double kSchwingerTemperatureGeV = 18.37;

/// The transport keys this generator has to agree with.
constexpr const char* kG4MassKey = "G4.monopoleMass";
constexpr const char* kG4ChargeKey = "G4.monopoleMagneticCharge";

/// true when a transport key was given explicitly (command line, ini file or
/// CCDB), false when it still carries the value compiled into O2. Without this
/// a key that was never set looks exactly like one set to its default, and the
/// generator would silently adopt a value nobody asked for. ConfigurableParam
/// throws for a key it does not know, which counts as "not set".
inline bool transportKeyWasSet(const char* key)
{
  try {
    return o2::conf::ConfigurableParam::getProvenance(key) != o2::conf::ConfigurableParam::kCODE;
  } catch (const std::exception&) {
    return false;
  }
}

/// The monopole transport settings, as the transport process will see them.
inline bool g4MonopolePhysicsEnabled() { return o2::conf::G4Params::Instance().monopole; }
inline double g4MonopoleMass() { return o2::conf::G4Params::Instance().monopoleMass; }
inline double g4MonopoleMagneticCharge() { return o2::conf::G4Params::Instance().monopoleMagneticCharge; }

//==============================================================================
// MonoValue: one configurable quantity
//==============================================================================

/// A single configurable number. It is read from JSON either as a bare number
/// (fixed value) or as an object selecting one of the supported distributions:
///
///   100                                                  fixed
///   {"value": 100}                                       fixed
///   {"values": [50,100,200], "weights": [1,1,2]}         weighted discrete choice
///   {"dist":"uniform",    "min":a, "max":b}
///   {"dist":"loguniform", "min":a, "max":b}              flat in ln(x), a > 0
///   {"dist":"gaus",       "mean":m, "sigma":s [,"min":a,"max":b]}
///   {"dist":"exp",        "tau":t [,"min":a,"max":b]}     propto exp(-x/t)
///   {"dist":"powerlaw",   "exponent":n, "min":a,"max":b}  propto x^n
///   {"dist":"poisson",    "mean":m [,"min":a,"max":b]}
///   {"dist":"thermal",    "temperature":T [,"mass":m,"min":a,"max":b]}
///                                                        propto x^2 exp(-sqrt(x^2+m^2)/T)
///                                                        mass defaults to the monopole mass
///   {"dist":"formula",    "formula":"x*x*exp(-x/10)", "min":a,"max":b}
///
/// Any spec accepts
///   "sampleOnce": true   draw once at Init() and reuse the value for the whole run
///                        (the default for mass and magnetic charge, which the
///                        transport cannot change event by event)
///   "integer":    true   round the drawn value to the nearest integer
///
/// Continuous shapes that have no closed-form inverse ("powerlaw", "thermal",
/// "formula", truncated "gaus"/"exp") are drawn from a tabulated inverse CDF
/// built once at Init() with kCdfBins bins, so the sampling cost and accuracy do
/// not depend on the shape.
class MonoValue
{
 public:
  enum EKind { kUnset,
               kFixed,
               kList,
               kUniform,
               kLogUniform,
               kGaus,
               kExp,
               kPowerLaw,
               kPoisson,
               kThermal,
               kFormula };

  static constexpr int kCdfBins = 20000;

  MonoValue() = default;
  explicit MonoValue(double fixed) : mKind(kFixed), mValue(fixed) {}

  bool isSet() const { return mKind != kUnset; }
  /// true when the JSON gave a plain number, as opposed to a shape to draw from
  bool isFixedSpec() const { return mKind == kFixed; }
  double min() const { return mMin; }
  double max() const { return mMax; }
  /// true if the value cannot change from one call to the next
  bool isConstant() const { return mKind == kFixed || mSampleOnce; }
  const std::string& name() const { return mName; }

  /// Parse a JSON node. Throws std::runtime_error on any malformed input.
  void parse(const rapidjson::Value& node, const std::string& name)
  {
    mName = name;
    if (node.IsNull()) {
      throw std::runtime_error(name + ": null is not a valid value specification");
    }
    if (node.IsNumber()) {
      mKind = kFixed;
      mValue = node.GetDouble();
      return;
    }
    if (!node.IsObject()) {
      throw std::runtime_error(name + ": expected a number or an object, got a " + jsonTypeName(node));
    }

    mSampleOnce = getBool(node, "sampleOnce", mSampleOnce);
    mInteger = getBool(node, "integer", mInteger);

    const bool hasValue = node.HasMember("value");
    const bool hasValues = node.HasMember("values");
    const bool hasDist = node.HasMember("dist");
    if (hasValue + hasValues + hasDist != 1) {
      throw std::runtime_error(name + ": exactly one of \"value\", \"values\" or \"dist\" must be given");
    }

    if (hasValue) {
      checkKeys(node, name, {"value", "sampleOnce", "integer"});
      mKind = kFixed;
      mValue = getNumber(node, "value");
      return;
    }

    if (hasValues) {
      checkKeys(node, name, {"values", "weights", "sampleOnce", "integer"});
      mKind = kList;
      const auto& arr = node["values"];
      if (!arr.IsArray() || arr.Empty()) {
        throw std::runtime_error(name + ".values: expected a non-empty array of numbers");
      }
      for (const auto& v : arr.GetArray()) {
        if (!v.IsNumber()) {
          throw std::runtime_error(name + ".values: all entries must be numbers");
        }
        mList.push_back(v.GetDouble());
      }
      if (node.HasMember("weights")) {
        const auto& w = node["weights"];
        if (!w.IsArray() || w.Size() != arr.Size()) {
          throw std::runtime_error(name + ".weights: expected an array with as many entries as \"values\"");
        }
        for (const auto& v : w.GetArray()) {
          if (!v.IsNumber() || v.GetDouble() < 0.) {
            throw std::runtime_error(name + ".weights: all entries must be non-negative numbers");
          }
          mWeights.push_back(v.GetDouble());
        }
      } else {
        mWeights.assign(mList.size(), 1.);
      }
      // cumulative weights, normalised
      double sum = std::accumulate(mWeights.begin(), mWeights.end(), 0.);
      if (!(sum > 0.)) {
        throw std::runtime_error(name + ".weights: the sum of the weights must be positive");
      }
      mCumWeights.resize(mWeights.size());
      double run = 0.;
      for (size_t i = 0; i < mWeights.size(); ++i) {
        run += mWeights[i] / sum;
        mCumWeights[i] = run;
      }
      mCumWeights.back() = 1.;
      return;
    }

    // dist
    if (!node["dist"].IsString()) {
      throw std::runtime_error(name + ".dist: expected a string");
    }
    const std::string dist = node["dist"].GetString();
    // the keys each distribution reads, on top of dist/min/max/sampleOnce/integer:
    // a misspelt optional parameter would otherwise silently keep its default
    static const std::map<std::string, std::vector<std::string>> kDistKeys = {
      {"uniform", {}},
      {"loguniform", {}},
      {"gaus", {"mean", "sigma"}},
      {"gauss", {"mean", "sigma"}},
      {"normal", {"mean", "sigma"}},
      {"exp", {"tau"}},
      {"exponential", {"tau"}},
      {"powerlaw", {"exponent"}},
      {"poisson", {"mean"}},
      {"thermal", {"temperature", "mass"}},
      {"formula", {"formula"}}};
    if (const auto known = kDistKeys.find(dist); known != kDistKeys.end()) {
      std::vector<std::string> allowed{"dist", "min", "max", "sampleOnce", "integer"};
      allowed.insert(allowed.end(), known->second.begin(), known->second.end());
      checkKeys(node, name, allowed);
    }
    mMin = getNumber(node, "min", -std::numeric_limits<double>::infinity());
    mMax = getNumber(node, "max", std::numeric_limits<double>::infinity());
    if (!(mMax > mMin)) {
      throw std::runtime_error(name + ": \"max\" must be larger than \"min\"");
    }

    if (dist == "uniform") {
      mKind = kUniform;
      requireFinite(name, "min", mMin);
      requireFinite(name, "max", mMax);
    } else if (dist == "loguniform") {
      mKind = kLogUniform;
      requireFinite(name, "min", mMin);
      requireFinite(name, "max", mMax);
      if (!(mMin > 0.)) {
        throw std::runtime_error(name + ": \"loguniform\" needs min > 0");
      }
    } else if (dist == "gaus" || dist == "gauss" || dist == "normal") {
      mKind = kGaus;
      mPar1 = getNumber(node, "mean");
      mPar2 = getNumber(node, "sigma");
      if (!(mPar2 > 0.)) {
        throw std::runtime_error(name + ": \"sigma\" must be positive");
      }
    } else if (dist == "exp" || dist == "exponential") {
      mKind = kExp;
      mPar1 = getNumber(node, "tau");
      if (!(mPar1 > 0.)) {
        throw std::runtime_error(name + ": \"tau\" must be positive");
      }
      if (!std::isfinite(mMin)) {
        mMin = 0.;
      }
    } else if (dist == "powerlaw") {
      mKind = kPowerLaw;
      mPar1 = getNumber(node, "exponent");
      requireFinite(name, "min", mMin);
      requireFinite(name, "max", mMax);
      if (mMin < 0. || (mPar1 < 0. && !(mMin > 0.))) {
        throw std::runtime_error(name + ": \"powerlaw\" needs min >= 0, and min > 0 for a negative exponent");
      }
    } else if (dist == "poisson") {
      mKind = kPoisson;
      mPar1 = getNumber(node, "mean");
      if (mPar1 < 0.) {
        throw std::runtime_error(name + ": \"mean\" must be non-negative");
      }
      mInteger = true;
    } else if (dist == "thermal") {
      mKind = kThermal;
      mPar1 = getNumber(node, "temperature", kSchwingerTemperatureGeV);
      if (!(mPar1 > 0.)) {
        throw std::runtime_error(name + ": \"temperature\" must be positive");
      }
      mPar2 = getNumber(node, "mass", -1.); // < 0 => take the monopole mass
      if (!std::isfinite(mMin) || mMin < 0.) {
        mMin = 0.;
      }
    } else if (dist == "formula") {
      mKind = kFormula;
      if (!node.HasMember("formula") || !node["formula"].IsString()) {
        throw std::runtime_error(name + ": \"formula\" (a TFormula string in x) is required");
      }
      mFormula = node["formula"].GetString();
      requireFinite(name, "min", mMin);
      requireFinite(name, "max", mMax);
    } else {
      throw std::runtime_error(name + ": unknown \"dist\" \"" + dist +
                               "\". Known: uniform, loguniform, gaus, exp, powerlaw, poisson, thermal, formula");
    }
  }

  /// Build the tabulated inverse CDF where needed and draw the sampleOnce value.
  /// @param defaultMass mass used by a "thermal" spec that does not give its own
  void init(double defaultMass)
  {
    switch (mKind) {
      case kThermal: {
        const double mass = mPar2 >= 0. ? mPar2 : defaultMass;
        const double T = mPar1;
        if (!std::isfinite(mMax)) {
          // the spectrum peaks near sqrt(2 m T); go far enough out that the
          // truncated tail is below 1e-14 of the peak
          mMax = autoRange([mass, T](double p) { return p * p * std::exp(-(std::sqrt(p * p + mass * mass) - mass) / T); },
                           std::max(1., std::sqrt(2. * mass * T)), mMin);
        }
        // exp() of the subtracted mass keeps the pdf in a sane numerical range
        buildCdf([mass, T](double p) { return p * p * std::exp(-(std::sqrt(p * p + mass * mass) - mass) / T); });
        break;
      }
      case kPowerLaw: {
        const double n = mPar1;
        buildCdf([n](double x) { return x <= 0. ? 0. : std::pow(x, n); });
        break;
      }
      case kFormula: {
        mTF1 = std::make_unique<TF1>((std::string("monoval_") + mName).c_str(), mFormula.c_str(), mMin, mMax);
        if (!mTF1->IsValid()) {
          throw std::runtime_error(mName + ": could not compile formula \"" + mFormula + "\"");
        }
        TF1* f = mTF1.get();
        buildCdf([f](double x) { return std::max(0., f->Eval(x)); });
        break;
      }
      case kGaus:
        if (std::isfinite(mMin) || std::isfinite(mMax)) {
          // truncated Gaussian: tabulate so that the truncation is exact and
          // does not need rejection
          const double mean = mPar1, sigma = mPar2;
          if (!std::isfinite(mMin)) {
            mMin = mean - 8. * sigma;
          }
          if (!std::isfinite(mMax)) {
            mMax = mean + 8. * sigma;
          }
          buildCdf([mean, sigma](double x) {
            const double z = (x - mean) / sigma;
            return std::exp(-0.5 * z * z);
          });
        }
        break;
      case kExp:
        if (std::isfinite(mMax)) {
          const double tau = mPar1, lo = mMin;
          buildCdf([tau, lo](double x) { return std::exp(-(x - lo) / tau); });
        }
        break;
      default:
        break;
    }

    if (mSampleOnce) {
      // keep mKind, so that the spec is still available to allows()
      mFrozenValue = draw();
      mFrozen = true;
    }
  }

  /// Draw a value, or return the fixed / drawn-once one.
  double sample() const
  {
    if (mKind == kFixed) {
      return applyInteger(mValue);
    }
    if (mFrozen) {
      return applyInteger(mFrozenValue);
    }
    return applyInteger(draw());
  }

  /// Would this spec ever produce @p v? Used to check an externally imposed
  /// value (G4.monopoleMass) against the configuration.
  bool allows(double v) const
  {
    const double tol = 1e-6 * std::max(1., std::abs(v));
    switch (mKind) {
      case kUnset:
        return false;
      case kFixed:
        return std::abs(v - mValue) <= tol;
      case kList:
        return std::any_of(mList.begin(), mList.end(),
                           [v, tol](double x) { return std::abs(v - x) <= tol; });
      default:
        return v >= mMin - tol && v <= mMax + tol;
    }
  }

  /// Human readable summary for the Init() printout.
  std::string describe() const
  {
    std::ostringstream os;
    switch (mKind) {
      case kUnset:
        os << "<unset>";
        break;
      case kFixed:
        os << mValue << " (fixed)";
        break;
      case kList: {
        os << "one of {";
        for (size_t i = 0; i < mList.size(); ++i) {
          os << (i ? ", " : "") << mList[i] << ":w=" << mWeights[i];
        }
        os << "}";
        break;
      }
      case kUniform:
        os << "uniform in [" << mMin << ", " << mMax << "]";
        break;
      case kLogUniform:
        os << "log-uniform in [" << mMin << ", " << mMax << "]";
        break;
      case kGaus:
        os << "gaus(mean=" << mPar1 << ", sigma=" << mPar2 << ")";
        break;
      case kExp:
        os << "exp(tau=" << mPar1 << ")";
        break;
      case kPowerLaw:
        os << "x^" << mPar1 << " in [" << mMin << ", " << mMax << "]";
        break;
      case kPoisson:
        os << "poisson(mean=" << mPar1 << ")";
        break;
      case kThermal:
        os << "p^2 exp(-E/T), T=" << mPar1 << " GeV, m=" << (mPar2 >= 0. ? mPar2 : -1.)
           << " GeV (<0: monopole mass)";
        break;
      case kFormula:
        os << "\"" << mFormula << "\"";
        break;
    }
    if (mKind != kFixed && mKind != kList && std::isfinite(mMin) && std::isfinite(mMax) &&
        mKind != kUniform && mKind != kLogUniform && mKind != kPowerLaw) {
      os << " restricted to [" << mMin << ", " << mMax << "]";
    }
    if (mInteger) {
      os << " [integer]";
    }
    if (mFrozen) {
      os << " -> drawn once at startup: " << mFrozenValue;
    }
    return os.str();
  }

 private:
  double applyInteger(double v) const { return mInteger ? std::round(v) : v; }

  double draw() const
  {
    switch (mKind) {
      case kFixed:
        return mValue;
      case kList: {
        const double u = gRandom->Rndm();
        auto it = std::lower_bound(mCumWeights.begin(), mCumWeights.end(), u);
        size_t i = static_cast<size_t>(it - mCumWeights.begin());
        return mList[std::min(i, mList.size() - 1)];
      }
      case kUniform:
        // an integer uniform has to be flat over the integers in [min, max]:
        // rounding Uniform(min, max) would give the two ends half the weight
        return mInteger ? std::floor(gRandom->Uniform(mMin, mMax + 1.))
                        : gRandom->Uniform(mMin, mMax);
      case kLogUniform:
        return std::exp(gRandom->Uniform(std::log(mMin), std::log(mMax)));
      case kGaus:
        if (!mCdf.empty()) {
          return sampleCdf();
        }
        return gRandom->Gaus(mPar1, mPar2);
      case kExp:
        if (!mCdf.empty()) {
          return sampleCdf();
        }
        return mMin + gRandom->Exp(mPar1);
      case kPoisson: {
        // "min"/"max" act as an acceptance window
        constexpr int kMaxTries = 100000;
        double v = gRandom->Poisson(mPar1);
        for (int trial = 0; (v < mMin || v > mMax) && trial < kMaxTries; ++trial) {
          v = gRandom->Poisson(mPar1);
        }
        if (v < mMin || v > mMax) {
          // returning an out-of-window value silently would change the
          // configured physics without any trace in the log
          const double clamped = std::min(std::max(v, mMin), mMax);
          LOG(error) << mName << ": no Poisson(" << mPar1 << ") draw fell into the configured "
                     << "window [" << mMin << ", " << mMax << "] in " << kMaxTries
                     << " tries, using " << clamped << " instead; the window and the mean are "
                     << "probably incompatible";
          return clamped;
        }
        return v;
      }
      case kPowerLaw:
      case kThermal:
      case kFormula:
        return sampleCdf();
      default:
        throw std::runtime_error(mName + ": sampling an unset value");
    }
  }

  /// Inverse-CDF sampling with linear interpolation inside the bin.
  double sampleCdf() const
  {
    const double u = gRandom->Rndm();
    auto it = std::lower_bound(mCdf.begin(), mCdf.end(), u);
    if (it == mCdf.begin()) {
      // inside the first bin: interpolate from the left edge
      const double f = mCdf[0] > 0. ? u / mCdf[0] : 0.5;
      return mCdfMin + f * mCdfStep;
    }
    const size_t i = static_cast<size_t>(it - mCdf.begin());
    if (i >= mCdf.size()) {
      return mCdfMin + mCdf.size() * mCdfStep;
    }
    const double c0 = mCdf[i - 1], c1 = mCdf[i];
    const double f = (c1 > c0) ? (u - c0) / (c1 - c0) : 0.5;
    return mCdfMin + (static_cast<double>(i) + f) * mCdfStep;
  }

  /// Tabulate the normalised cumulative of @p pdf over [mMin, mMax].
  void buildCdf(const std::function<double(double)>& pdf)
  {
    mCdfMin = mMin;
    mCdfStep = (mMax - mMin) / kCdfBins;
    mCdf.assign(kCdfBins, 0.);
    double run = 0.;
    for (int i = 0; i < kCdfBins; ++i) {
      // trapezoidal weight of the bin
      const double a = pdf(mMin + i * mCdfStep);
      const double b = pdf(mMin + (i + 1) * mCdfStep);
      run += 0.5 * (std::max(0., a) + std::max(0., b));
      mCdf[i] = run;
    }
    if (!(run > 0.)) {
      throw std::runtime_error(mName + ": the distribution integrates to zero over [" +
                               std::to_string(mMin) + ", " + std::to_string(mMax) + "]");
    }
    for (auto& c : mCdf) {
      c /= run;
    }
    mCdf.back() = 1.;
  }

  /// Walk outwards from @p peak until the pdf has dropped by 1e-14, to pick a
  /// sensible upper edge for an open-ended spectrum.
  static double autoRange(const std::function<double(double)>& pdf, double peak, double lo)
  {
    const double fpeak = std::max(pdf(peak), 1e-300);
    double x = std::max(peak, lo + 1.);
    for (int i = 0; i < 4000; ++i) {
      if (pdf(x) / fpeak < 1e-14) {
        return x;
      }
      x *= 1.05;
    }
    return x;
  }

  static void requireFinite(const std::string& name, const char* what, double v)
  {
    if (!std::isfinite(v)) {
      throw std::runtime_error(name + ": \"" + what + "\" is required for this distribution");
    }
  }

  static const char* jsonTypeName(const rapidjson::Value& v)
  {
    static const char* names[] = {"null", "false", "true", "object", "array", "string", "number"};
    return names[v.GetType()];
  }

  static double getNumber(const rapidjson::Value& node, const char* key)
  {
    if (!node.HasMember(key) || !node[key].IsNumber()) {
      throw std::runtime_error(std::string("\"") + key + "\" is required and must be a number");
    }
    return node[key].GetDouble();
  }
  static double getNumber(const rapidjson::Value& node, const char* key, double def)
  {
    if (!node.HasMember(key)) {
      return def;
    }
    if (!node[key].IsNumber()) {
      throw std::runtime_error(std::string("\"") + key + "\" must be a number");
    }
    return node[key].GetDouble();
  }
  static bool getBool(const rapidjson::Value& node, const char* key, bool def)
  {
    if (!node.HasMember(key)) {
      return def;
    }
    if (!node[key].IsBool()) {
      throw std::runtime_error(std::string("\"") + key + "\" must be true or false");
    }
    return node[key].GetBool();
  }

  EKind mKind = kUnset;
  std::string mName;
  double mValue = 0.;
  double mPar1 = 0., mPar2 = 0.;
  double mMin = -std::numeric_limits<double>::infinity();
  double mMax = std::numeric_limits<double>::infinity();
  bool mSampleOnce = false;
  bool mInteger = false;
  bool mFrozen = false;
  double mFrozenValue = 0.;
  std::string mFormula;
  std::vector<double> mList, mWeights, mCumWeights;
  std::vector<double> mCdf;
  double mCdfMin = 0., mCdfStep = 0.;
  std::unique_ptr<TF1> mTF1;
};

//==============================================================================
// GeneratorMonopoles
//==============================================================================

/// One generated monopole, in GeV / GeV/c / cm / s. At namespace scope so that
/// rootcling can build a dictionary for the vector holding them.
struct MonoObject {
  int pdg;
  double px, py, pz, e;
  double vx, vy, vz, vt;
};

class GeneratorMonopolesImpl : public Generator
{
 public:
  enum EMode { kSchwinger,
               kSingle };
  /// every mode the generator knows; extend together with EMode and modeName()
  static constexpr EMode kAllModes[] = {kSchwinger, kSingle};
  enum EChargeSign { kRandomSign,
                     kPositive,
                     kNegative };
  enum EOnMismatch { kFatal,
                     kWarn,
                     kIgnore };

  GeneratorMonopolesImpl() : Generator("GeneratorMonopoles", "ALICEo2 configurable monopole generator")
  {
    // we fill GeV, GeV/c, cm and s directly
    setMomentumUnit(1.);
    setEnergyUnit(1.);
    setPositionUnit(1.);
    setTimeUnit(1.);
  }

  ~GeneratorMonopolesImpl() override { finalMomentumReport(); }

  /// The path may contain shell variables: O2 hands the argument of funcName to
  /// the macro verbatim, and the O2DPG ini files write the path as
  /// ${O2DPG_MC_CONFIG_ROOT}/..., so it is the macro that has to expand it, with
  /// the same helper the other O2 generators use.
  void setConfigFile(const std::string& f) { mConfigFile = o2::utils::expandShellVarsInFileName(f); }

  /// Parses the configuration and prints the transport settings that go with it,
  /// both as a --configKeyValues string and as an ini snippet, without touching
  /// or even reading the transport. This is what makes a separate key-deriving
  /// script unnecessary: see MonopolesTransportKeys() at the end of this file.
  int printTransportKeys()
  {
    try {
      readConfig();
      mReportOnly = true; // only report: never read or adopt the transport values
      finaliseConfig();
    } catch (const std::exception& e) {
      LOG(error) << "GeneratorMonopoles: " << e.what();
      return 1;
    }

    std::ostringstream keys;
    keys << "G4.monopole=1"
         << ";G4.monopoleMass=" << mLastMass
         << ";G4.monopoleMagneticCharge=" << mLastCharge;
    if (mGeneratorId >= 0) {
      keys << ";PrimaryGenerator.id=" << mGeneratorId;
    }

    std::cout << "\n# transport settings matching "
              << (mConfigFile.empty() ? std::string("the built-in defaults") : mConfigFile) << "\n"
              << "\n# as --configKeyValues (append to the generator keys)\n"
              << keys.str() << "\n"
              << "\n# as an ini file section\n"
              << "[G4]\n"
              << "monopole = true\n"
              << "monopoleMass = " << mLastMass << "\n"
              << "monopoleMagneticCharge = " << mLastCharge << "\n";
    if (mGeneratorId >= 0) {
      std::cout << "\n[PrimaryGenerator]\n"
                << "id = " << mGeneratorId << "\n";
    }
    printOpenValueNote("mass", kG4MassKey, mMass, mMassFromTransport,
                       mMassFromG4 ? "transport.massFromG4 is set" : "it is not set in the configuration");
    printOpenValueNote("magnetic charge", kG4ChargeKey, mCharge, mChargeFromTransport,
                       "it is not set in the configuration");
    std::cout << std::endl;
    return 0;
  }

  /// Explains a transport value printed by printTransportKeys() that the JSON
  /// does not fix, for the mass and the charge separately. @param reason why the
  /// generator takes the value from the transport key, when fromTransport is set
  static void printOpenValueNote(const char* what, const char* key, const MonoValue& spec,
                                 bool fromTransport, const char* reason)
  {
    if (fromTransport) {
      std::cout << "\n# note: the generator takes the " << what << " from " << key << " (" << reason << ").\n"
                << "# The value above is the O2 default; set " << key << " to the " << what << " you want.\n";
    } else if (!spec.isFixedSpec()) {
      std::cout << "\n# note: the " << what << " [" << spec.describe() << "] is not a fixed value. The\n"
                << "# number above is the one drawn by this call; any other value the specification\n"
                << "# allows works too, the generator adopts " << key << " at startup.\n";
    }
  }

  //----------------------------------------------------------------------------
  Bool_t Init() override
  {
    if (!Generator::Init()) {
      return kFALSE;
    }
    return setup();
  }

  /// Read the configuration and get everything ready. Idempotent, and called
  /// from generateEvent() as well as from Init(): some O2 execution paths never
  /// call Init() on the primary generators (o2-sim --noGeant, for one), so the
  /// generator must not depend on it having run.
  Bool_t setup()
  {
    if (mSetupDone) {
      return mSetupOk;
    }
    mSetupDone = true;
    mSetupOk = kFALSE;
    try {
      readConfig();
      finaliseConfig();
    } catch (const std::exception& e) {
      LOG(fatal) << "GeneratorMonopoles: " << e.what();
      return kFALSE;
    }
    registerMonopolesInPdgDatabase(mLastMass);
    checkGeneratorId();
    // O2's sub-generator bookkeeping: the description map goes into the event
    // header and ends up in the AO2D MC collisions (o2::mcgenid), so the
    // production mode can be selected at analysis level.
    for (EMode mode : kAllModes) {
      addSubGenerator(static_cast<int>(mode), std::string("monopoles: ") + modeName(mode));
    }
    if (mVerbose > 0) {
      printConfig();
    }
    mSetupOk = checkTransport();
    return mSetupOk;
  }

  //----------------------------------------------------------------------------
  Bool_t generateEvent() override
  {
    if (!setup()) {
      return kFALSE;
    }
    notifySubGenerator(static_cast<int>(mMode));
    mObjects.clear();
    const int n = std::max(0, static_cast<int>(std::lround(mNObjects.sample())));
    for (int i = 0; i < n; ++i) {
      switch (mMode) {
        case kSchwinger:
          if (!makeSchwingerPair()) {
            return kFALSE;
          }
          break;
        case kSingle:
          if (!makeSingle()) {
            return kFALSE;
          }
          break;
      }
    }
    if (mVerbose > 1) {
      LOG(info) << "GeneratorMonopoles: generated " << mObjects.size() << " monopole(s)";
    }
    return kTRUE;
  }

  //----------------------------------------------------------------------------
  Bool_t importParticles() override
  {
    // ReadEvent() already clears it; done here too so that importParticles()
    // is also safe to call on its own
    mParticles.clear();
    for (const auto& o : mObjects) {
      TParticle p(o.pdg, 1, -1, -1, -1, -1,
                  o.px, o.py, o.pz, o.e,
                  o.vx, o.vy, o.vz, o.vt);
      // HepMC status 1 (final state), generator status 0, to be transported
      o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(p, 1, 0, true);
      mParticles.push_back(p);
    }
    mNGenerated += mObjects.size();
    ++mNEvents;
    return kTRUE;
  }

  //----------------------------------------------------------------------------
  void updateHeader(o2::dataformats::MCEventHeader* header) override
  {
    using Key = o2::dataformats::MCInfoKeys;
    header->putInfo<std::string>(Key::generator, "monopoles");
    header->putInfo<std::string>(Key::processName, modeName(mMode));
    header->putInfo<int>(Key::processCode, static_cast<int>(mMode));
    header->putInfo<float>(Key::weight, 1.f);
    header->putInfo<float>("monopole_mass", static_cast<float>(mLastMass));
    header->putInfo<float>("monopole_magnetic_charge", static_cast<float>(mLastCharge));
    header->putInfo<int>("monopole_pdg", mPdg);
    header->putInfo<int>("monopole_multiplicity", static_cast<int>(mObjects.size()));
  }

  void stop() override
  {
    if (mNEvents > 0) {
      LOG(info) << "GeneratorMonopoles: " << mNGenerated << " monopoles in " << mNEvents
                << " events (" << static_cast<double>(mNGenerated) / mNEvents << " per event), "
                << "mass " << mLastMass << " GeV"
                << valueOrigin(mMass, mLastMass, g4MonopoleMass(), kG4MassKey)
                << ", magnetic charge " << mLastCharge << " g_D"
                << valueOrigin(mCharge, mLastCharge, g4MonopoleMagneticCharge(), kG4ChargeKey);
    }
    finalMomentumReport();
  }

  /// Where the value used for the run comes from, for the summary line: nothing
  /// for a plain number in the JSON, the transport key when it was adopted from
  /// it, and the specification otherwise (the per-event values are in the event
  /// header, as monopole_mass and monopole_magnetic_charge).
  static std::string valueOrigin(const MonoValue& spec, double used, double g4value, const char* key)
  {
    if (spec.isFixedSpec()) {
      return "";
    }
    if (g4value > 0. && std::abs(g4value - used) <= 1e-6 * std::max(1., std::abs(g4value))) {
      return std::string(" (from ") + key + ")";
    }
    return " (last of " + spec.describe() + ")";
  }

 private:
  //--------------------------------------------------------------------------
  // configuration
  //--------------------------------------------------------------------------
  void readConfig()
  {
    if (mConfigFile.empty()) {
      LOG(info) << "GeneratorMonopoles: no JSON file given, using the built-in Schwinger defaults";
      return;
    }
    std::ifstream in(mConfigFile);
    if (!in.is_open()) {
      throw std::runtime_error("cannot open configuration file \"" + mConfigFile + "\"");
    }
    rapidjson::IStreamWrapper isw(in);
    rapidjson::Document doc;
    doc.ParseStream(isw);
    if (doc.HasParseError()) {
      throw std::runtime_error("parse error in \"" + mConfigFile + "\" at offset " +
                               std::to_string(doc.GetErrorOffset()) + ": " +
                               rapidjson::GetParseError_En(doc.GetParseError()));
    }
    if (!doc.IsObject()) {
      throw std::runtime_error("\"" + mConfigFile + "\": the top level must be a JSON object");
    }
    checkKeys(doc, "", {"mode", "verbose", "generatorId", "nPairs", "nParticles", "particle",
                        "kinematics", "vertex", "pairRecoil", "transport", "comment"});

    if (doc.HasMember("mode")) {
      if (!doc["mode"].IsString()) {
        throw std::runtime_error("\"mode\" must be a string");
      }
      mMode = parseMode(doc["mode"].GetString());
    }
    if (doc.HasMember("verbose")) {
      if (!doc["verbose"].IsInt()) {
        throw std::runtime_error("\"verbose\" must be an integer");
      }
      mVerbose = doc["verbose"].GetInt();
    }
    if (doc.HasMember("generatorId")) {
      if (!doc["generatorId"].IsInt() || doc["generatorId"].GetInt() < 0 || doc["generatorId"].GetInt() > 127) {
        throw std::runtime_error("\"generatorId\" must be an integer in [0, 127] (7 bits in the "
                                 "AO2D MC generator id encoding)");
      }
      mGeneratorId = doc["generatorId"].GetInt();
    }

    // multiplicity: nPairs for schwinger, nParticles for single
    const char* nKey = (mMode == kSchwinger) ? "nPairs" : "nParticles";
    const char* otherKey = (mMode == kSchwinger) ? "nParticles" : "nPairs";
    if (doc.HasMember(otherKey)) {
      throw std::runtime_error(std::string("\"") + otherKey + "\" does not apply to mode \"" +
                               modeName(mMode) + "\"; use \"" + nKey + "\"");
    }
    if (doc.HasMember(nKey)) {
      mNObjects.parse(doc[nKey], nKey);
    }

    if (doc.HasMember("particle")) {
      const auto& pn = doc["particle"];
      if (!pn.IsObject()) {
        throw std::runtime_error("\"particle\" must be an object");
      }
      checkKeys(pn, "particle", {"pdg", "species", "mass", "magneticCharge", "chargeSign"});
      if (pn.HasMember("pdg") && pn.HasMember("species")) {
        throw std::runtime_error("particle: give either \"pdg\" or \"species\", not both");
      }
      if (pn.HasMember("pdg")) {
        if (!pn["pdg"].IsInt()) {
          throw std::runtime_error("particle.pdg must be an integer");
        }
        mPdg = std::abs(pn["pdg"].GetInt());
        if (mPdg != kMonopolePdgSymm && mPdg != kMonopolePdgAsymm) {
          throw std::runtime_error("particle.pdg must be " + std::to_string(kMonopolePdgSymm) +
                                   " (symmetric) or " + std::to_string(kMonopolePdgAsymm) + " (asymmetric)");
        }
      }
      if (pn.HasMember("species")) {
        if (!pn["species"].IsString()) {
          throw std::runtime_error("particle.species must be a string");
        }
        const std::string s = pn["species"].GetString();
        if (s == "symm" || s == "symmetric") {
          mPdg = kMonopolePdgSymm;
        } else if (s == "asymm" || s == "asymmetric") {
          mPdg = kMonopolePdgAsymm;
        } else {
          throw std::runtime_error("particle.species: unknown \"" + s + "\" (known: symm, asymm)");
        }
      }
      if (pn.HasMember("mass")) {
        mMass.parse(pn["mass"], "particle.mass");
      }
      if (pn.HasMember("magneticCharge")) {
        mCharge.parse(pn["magneticCharge"], "particle.magneticCharge");
      }
      if (pn.HasMember("chargeSign")) {
        if (mMode != kSingle) {
          throw std::runtime_error("particle.chargeSign only applies to mode \"single\"; a Schwinger "
                                   "pair always contains one monopole and one antimonopole");
        }
        if (!pn["chargeSign"].IsString()) {
          throw std::runtime_error("particle.chargeSign must be a string");
        }
        const std::string s = pn["chargeSign"].GetString();
        if (s == "random") {
          mChargeSign = kRandomSign;
        } else if (s == "positive" || s == "plus" || s == "monopole") {
          mChargeSign = kPositive;
        } else if (s == "negative" || s == "minus" || s == "antimonopole") {
          mChargeSign = kNegative;
        } else {
          throw std::runtime_error("particle.chargeSign: unknown \"" + s +
                                   "\" (known: random, positive, negative)");
        }
      }
    }

    if (doc.HasMember("kinematics")) {
      const auto& kn = doc["kinematics"];
      if (!kn.IsObject()) {
        throw std::runtime_error("\"kinematics\" must be an object");
      }
      checkKeys(kn, "kinematics", {"p", "pt", "ekin", "etot", "eta", "y", "theta", "costheta", "phi"});
      for (const char* k : {"p", "pt", "ekin", "etot"}) {
        if (kn.HasMember(k)) {
          mMagnitude.parse(kn[k], std::string("kinematics.") + k);
          mMagVar = k;
        }
      }
      for (const char* k : {"eta", "y", "theta", "costheta"}) {
        if (kn.HasMember(k)) {
          if (!mAngleVar.empty()) {
            throw std::runtime_error("kinematics: \"" + mAngleVar + "\" and \"" + k +
                                     "\" are alternatives, give only one");
          }
          mAngle.parse(kn[k], std::string("kinematics.") + k);
          mAngleVar = k;
        }
      }
      if (kn.HasMember("phi")) {
        mPhi.parse(kn["phi"], "kinematics.phi");
      }
      // how many of p/pt/ekin/etot were given
      int nMag = 0;
      for (const char* k : {"p", "pt", "ekin", "etot"}) {
        nMag += kn.HasMember(k) ? 1 : 0;
      }
      if (nMag > 1) {
        throw std::runtime_error("kinematics: \"p\", \"pt\", \"ekin\" and \"etot\" are alternatives, "
                                 "give only one");
      }
    }

    if (doc.HasMember("vertex")) {
      const auto& vn = doc["vertex"];
      if (!vn.IsObject()) {
        throw std::runtime_error("\"vertex\" must be an object");
      }
      checkKeys(vn, "vertex", {"x", "y", "z", "t", "perObject"});
      if (vn.HasMember("x")) {
        mVx.parse(vn["x"], "vertex.x");
      }
      if (vn.HasMember("y")) {
        mVy.parse(vn["y"], "vertex.y");
      }
      if (vn.HasMember("z")) {
        mVz.parse(vn["z"], "vertex.z");
      }
      if (vn.HasMember("t")) {
        mVt.parse(vn["t"], "vertex.t");
      }
      if (vn.HasMember("perObject")) {
        if (!vn["perObject"].IsBool()) {
          throw std::runtime_error("vertex.perObject must be true or false");
        }
        mVertexPerObject = vn["perObject"].GetBool();
      }
    }

    if (doc.HasMember("pairRecoil")) {
      if (mMode != kSchwinger) {
        throw std::runtime_error("\"pairRecoil\" only applies to mode \"schwinger\"");
      }
      const auto& rn = doc["pairRecoil"];
      if (!rn.IsObject()) {
        throw std::runtime_error("\"pairRecoil\" must be an object");
      }
      checkKeys(rn, "pairRecoil", {"pt", "pz", "phi"});
      if (rn.HasMember("pt")) {
        mRecoilPt.parse(rn["pt"], "pairRecoil.pt");
      }
      if (rn.HasMember("pz")) {
        mRecoilPz.parse(rn["pz"], "pairRecoil.pz");
      }
      if (rn.HasMember("phi")) {
        mRecoilPhi.parse(rn["phi"], "pairRecoil.phi");
      }
    }

    if (doc.HasMember("transport")) {
      const auto& tn = doc["transport"];
      if (!tn.IsObject()) {
        throw std::runtime_error("\"transport\" must be an object");
      }
      checkKeys(tn, "transport", {"check", "onMismatch", "massFromG4", "tolerance"});
      if (tn.HasMember("check")) {
        if (!tn["check"].IsBool()) {
          throw std::runtime_error("transport.check must be true or false");
        }
        mCheckTransport = tn["check"].GetBool();
      }
      if (tn.HasMember("massFromG4")) {
        if (!tn["massFromG4"].IsBool()) {
          throw std::runtime_error("transport.massFromG4 must be true or false");
        }
        mMassFromG4 = tn["massFromG4"].GetBool();
      }
      if (tn.HasMember("tolerance")) {
        if (!tn["tolerance"].IsNumber()) {
          throw std::runtime_error("transport.tolerance must be a number");
        }
        mTolerance = tn["tolerance"].GetDouble();
      }
      if (tn.HasMember("onMismatch")) {
        if (!tn["onMismatch"].IsString()) {
          throw std::runtime_error("transport.onMismatch must be a string");
        }
        const std::string s = tn["onMismatch"].GetString();
        if (s == "fatal") {
          mOnMismatch = kFatal;
        } else if (s == "warn") {
          mOnMismatch = kWarn;
        } else if (s == "ignore") {
          mOnMismatch = kIgnore;
        } else {
          throw std::runtime_error("transport.onMismatch: unknown \"" + s +
                                   "\" (known: fatal, warn, ignore)");
        }
      }
    }
  }

  /// Apply the defaults that depend on the mode and build the samplers.
  void finaliseConfig()
  {
    // mass: explicit, from the transport, or the O2 default
    if ((!mMass.isSet() || mMassFromG4) && mReportOnly) {
      // report mode reads no transport setting: outside o2-sim even asking for
      // the provenance of a G4 key aborts in ConfigurableParamHelper
      mMass = MonoValue(kMonopoleMassDefaultGeV);
      mMassFromTransport = true;
    } else if (!mMass.isSet() || mMassFromG4) {
      const double g4mass = g4MonopoleMass();
      if (transportKeyWasSet(kG4MassKey) && g4mass > 0.) {
        mMass = MonoValue(g4mass);
        LOG(info) << "GeneratorMonopoles: taking the monopole mass from G4.monopoleMass = " << g4mass << " GeV";
      } else if (mMassFromG4) {
        throw std::runtime_error("transport.massFromG4 is set but G4.monopoleMass was not given "
                                 "(it still holds the O2 default of " + std::to_string(g4mass) + ")");
      } else {
        mMass = MonoValue(kMonopoleMassDefaultGeV);
        LOG(info) << "GeneratorMonopoles: no mass configured and G4.monopoleMass not given, "
                  << "using the O2 default of " << kMonopoleMassDefaultGeV << " GeV";
      }
    }
    if (!mCharge.isSet() && mReportOnly) {
      mCharge = MonoValue(kMonopoleMagneticChargeDefault);
      mChargeFromTransport = true;
    } else if (!mCharge.isSet()) {
      mCharge = MonoValue(g4MonopoleMagneticCharge());
    }
    if (!mNObjects.isSet()) {
      mNObjects = MonoValue(1.);
    }
    mNObjects.init(0.);

    // mass and magnetic charge have to stay constant: the transport knows a
    // single value for the whole run
    mMass.init(0.);
    mCharge.init(0.);
    if (!mMass.isConstant()) {
      throw std::runtime_error("particle.mass varies event by event, which the transport cannot "
                               "follow (it uses the single value G4.monopoleMass). Add "
                               "\"sampleOnce\": true to draw one mass per run, or give a fixed value");
    }
    if (!mCharge.isConstant()) {
      throw std::runtime_error("particle.magneticCharge varies event by event, which the transport "
                               "cannot follow (it uses the single value G4.monopoleMagneticCharge). "
                               "Add \"sampleOnce\": true, or give a fixed value");
    }
    mLastMass = mMass.sample();
    mLastCharge = mCharge.sample();

    // When the configuration leaves the mass (or the charge) open and the
    // transport has an explicit value, adopt the transport value instead of an
    // independently drawn one: the two processes cannot negotiate, so taking
    // the single value the transport will use is the only way to stay
    // consistent by construction. A mass scan then just varies
    // G4.monopoleMass over one JSON file. transport.check == false means "do
    // not look at the transport at all", so it switches this off as well.
    if (mCheckTransport && !mReportOnly) {
      adoptFromTransport("mass", kG4MassKey, mMass, g4MonopoleMass(), mLastMass);
      adoptFromTransport("magneticCharge", kG4ChargeKey, mCharge, g4MonopoleMagneticCharge(), mLastCharge);
    }

    if (!(mLastMass > 0.)) {
      throw std::runtime_error("the monopole mass must be positive, got " + std::to_string(mLastMass));
    }

    // kinematics defaults
    if (!mMagnitude.isSet()) {
      if (mMode == kSchwinger) {
        // the Maxwell-Juettner spectrum of the reference PbPb HepMC samples
        rapidjson::Document d;
        d.Parse("{\"dist\":\"thermal\",\"temperature\":18.37}");
        mMagnitude.parse(d, "kinematics.p");
        mMagVar = "p";
      } else {
        throw std::runtime_error("mode \"single\" needs one of kinematics.p, .pt, .ekin or .etot");
      }
    }
    if (mAngleVar.empty()) {
      // isotropic
      rapidjson::Document d;
      d.Parse("{\"dist\":\"uniform\",\"min\":-1.0,\"max\":1.0}");
      mAngle.parse(d, "kinematics.costheta");
      mAngleVar = "costheta";
    }
    if (!mPhi.isSet()) {
      rapidjson::Document d;
      d.Parse("{\"dist\":\"uniform\",\"min\":0.0,\"max\":6.283185307179586}");
      mPhi.parse(d, "kinematics.phi");
    }

    mMagnitude.init(mLastMass);
    mAngle.init(mLastMass);
    mPhi.init(mLastMass);
    for (auto* v : {&mVx, &mVy, &mVz, &mVt, &mRecoilPt, &mRecoilPz, &mRecoilPhi}) {
      if (v->isSet()) {
        v->init(mLastMass);
      }
    }
    if (mRecoilPt.isSet() && !mRecoilPhi.isSet()) {
      rapidjson::Document d;
      d.Parse("{\"dist\":\"uniform\",\"min\":0.0,\"max\":6.283185307179586}");
      mRecoilPhi.parse(d, "pairRecoil.phi");
      mRecoilPhi.init(mLastMass);
    }

    // a pt-based magnitude with eta is fine, but pt with costheta/theta needs
    // sin(theta) != 0
    if (mMagVar == "pt" && (mAngleVar == "costheta" || mAngleVar == "theta")) {
      LOG(warning) << "GeneratorMonopoles: kinematics.pt combined with " << mAngleVar
                   << " diverges for theta -> 0; directions with |sin(theta)| < 1e-6 are redrawn";
    }
  }

  void printConfig() const
  {
    LOG(info) << "=== GeneratorMonopoles configuration ===";
    LOG(info) << "  config file        : " << (mConfigFile.empty() ? std::string("<defaults>") : mConfigFile);
    LOG(info) << "  mode               : " << modeName(mMode);
    LOG(info) << "  species / |pdg|    : " << (mPdg == kMonopolePdgSymm ? "symm" : "asymm") << " / " << mPdg;
    LOG(info) << "  mass               : " << mLastMass << " GeV  [" << mMass.describe() << "]";
    LOG(info) << "  magnetic charge    : " << mLastCharge << " g_D  [" << mCharge.describe() << "]";
    LOG(info) << "  " << (mMode == kSchwinger ? "pairs/event      " : "monopoles/event  ") << "  : "
              << mNObjects.describe();
    if (mMode == kSingle) {
      LOG(info) << "  charge sign        : "
                << (mChargeSign == kRandomSign ? "random" : (mChargeSign == kPositive ? "positive" : "negative"));
    }
    LOG(info) << "  magnitude (" << mMagVar << ")  : " << mMagnitude.describe();
    LOG(info) << "  direction (" << mAngleVar << ")  : " << mAngle.describe();
    LOG(info) << "  phi                : " << mPhi.describe();
    if (mVx.isSet() || mVy.isSet() || mVz.isSet() || mVt.isSet()) {
      LOG(info) << "  vertex offset [cm] : x=" << (mVx.isSet() ? mVx.describe() : "0")
                << " y=" << (mVy.isSet() ? mVy.describe() : "0")
                << " z=" << (mVz.isSet() ? mVz.describe() : "0")
                << " t[s]=" << (mVt.isSet() ? mVt.describe() : "0")
                << (mVertexPerObject ? " (drawn per monopole)"
                                     : (mMode == kSchwinger ? " (drawn per pair)" : " (drawn per monopole)"));
    }
    if (mRecoilPt.isSet() || mRecoilPz.isSet()) {
      LOG(info) << "  pair recoil        : pt=" << (mRecoilPt.isSet() ? mRecoilPt.describe() : "0")
                << " pz=" << (mRecoilPz.isSet() ? mRecoilPz.describe() : "0");
    }
    LOG(info) << "========================================";
  }

  //--------------------------------------------------------------------------
  // transport consistency
  //--------------------------------------------------------------------------
  /// If @p spec is not a plain fixed number and the transport was given an
  /// explicit value, replace @p current with it after checking the configuration
  /// allows it. A key that was never set is left alone: adopting the value
  /// compiled into O2 would quietly override the configured specification, and
  /// a specification that excludes that default would fail on a key the user
  /// never touched.
  void adoptFromTransport(const char* what, const char* key, const MonoValue& spec,
                          double g4value, double& current)
  {
    if (spec.isFixedSpec() || !(g4value > 0.)) {
      return;
    }
    if (!transportKeyWasSet(key)) {
      LOG(info) << "GeneratorMonopoles: particle." << what << " is a range or a list and " << key
                << " was not given, so the drawn value " << current << " is used; set " << key
                << " to the same value for the transport";
      return;
    }
    if (!spec.allows(g4value)) {
      const std::string problem = std::string(key) + " = " + std::to_string(g4value) +
                                  " is not a value particle." + what + " can produce (" +
                                  spec.describe() + ")";
      if (mOnMismatch == kFatal) {
        throw std::runtime_error(problem);
      }
      // with onMismatch warn/ignore the generator keeps its own value; checkTransport()
      // then reports the resulting disagreement with the same severity
      if (mOnMismatch == kWarn) {
        LOG(warning) << "GeneratorMonopoles: " << problem << ", keeping the drawn value " << current;
      } else {
        LOG(info) << "GeneratorMonopoles (ignored): " << problem << ", keeping the drawn value "
                  << current;
      }
      return;
    }
    if (std::abs(g4value - current) > 1e-6 * std::max(1., std::abs(g4value))) {
      LOG(info) << "GeneratorMonopoles: particle." << what << " is configured as a range or a list, "
                << "taking the transport value " << g4value << " instead of the drawn " << current
                << " so that the generator and the transport agree";
    }
    current = g4value;
  }

  /// The generator id is stamped into the event header by o2::eventgen::PrimaryGenerator
  /// from the PrimaryGenerator.id configurable parameter, and it ends up, together with
  /// the sub-generator id, in the AO2D MC collisions (o2::mcgenid). The generator cannot
  /// set it - it belongs to the primary generator - so, exactly as for the transport
  /// settings, it is only checked here; MonopolesTransportKeys() prints the matching
  /// PrimaryGenerator.id from the "generatorId" key of this very JSON file.
  void checkGeneratorId() const
  {
    if (mGeneratorId < 0) {
      return;
    }
    const int fromParams = o2::eventgen::PrimaryGeneratorParam::Instance().id;
    if (fromParams != mGeneratorId) {
      LOG(warning) << "GeneratorMonopoles: the configuration asks for generatorId " << mGeneratorId
                   << " but PrimaryGenerator.id is " << fromParams
                   << "; add PrimaryGenerator.id=" << mGeneratorId
                   << " to the configuration keys (MonopolesTransportKeys() prints it)";
    } else if (mVerbose > 0) {
      LOG(info) << "GeneratorMonopoles: generator id " << mGeneratorId
                << " will be stamped into the event header";
    }
  }

  /// Make sure TDatabasePDG knows the monopoles with the mass this run uses.
  /// Everything that derives a mass from the PDG table - the MCTrack getters,
  /// kinematics dumps, analysis code - then agrees with the
  /// generator. TDatabasePDG keeps the first registration of a code, so if
  /// something already added the monopoles with another mass we can only report
  /// it.
  void registerMonopolesInPdgDatabase(double mass) const
  {
    auto* db = TDatabasePDG::Instance();
    // o2-sim registers them in GeneratorFactory before this generator is even
    // built, so normally there is nothing to do here; calling the O2 helper
    // again would only make TDatabasePDG warn about every particle it already
    // knows. The call is kept for hosts that build the generator themselves.
    if (db->GetParticle(kMonopolePdgSymm) == nullptr) {
      o2::O2DatabasePDG::addALICEParticles(db, mass);
      LOG(info) << "GeneratorMonopoles: registered the ALICE particles via "
                << "O2DatabasePDG::addALICEParticles() with monopole mass " << mass << " GeV";
    } else if (const auto* registered = db->GetParticle(kMonopolePdgSymm);
               std::abs(registered->Mass() - mass) > 1e-6 * std::max(1., mass)) {
      // TDatabasePDG keeps the first registration of a code, so this can only be reported
      LOG(warning) << "GeneratorMonopoles: the monopoles are already in TDatabasePDG with mass "
                   << registered->Mass() << " GeV instead of " << mass << " GeV, so a mass read "
                   << "from the PDG table (e.g. MCTrack::GetMass()) will not match the generator. "
                   << "The generated 4-momenta are not affected";
    }
  }

  Bool_t checkTransport()
  {
    if (!mCheckTransport) {
      return kTRUE;
    }
    std::vector<std::string> problems;

    if (!g4MonopolePhysicsEnabled()) {
      problems.push_back("G4.monopole is off: the monopoles will not be defined to the transport "
                         "engine. Add G4.monopole=1 to --configKeyValues (and use the Geant4 engine)");
    }
    const double g4mass = g4MonopoleMass();
    if (std::abs(g4mass - mLastMass) > mTolerance * std::max(1., std::abs(mLastMass))) {
      problems.push_back("generator mass " + std::to_string(mLastMass) + " GeV != G4.monopoleMass " +
                         std::to_string(g4mass) + " GeV");
    }
    const double g4charge = g4MonopoleMagneticCharge();
    if (std::abs(g4charge - mLastCharge) > mTolerance * std::max(1., std::abs(mLastCharge))) {
      problems.push_back("generator magnetic charge " + std::to_string(mLastCharge) +
                         " g_D != G4.monopoleMagneticCharge " + std::to_string(g4charge) + " g_D");
    }

    if (problems.empty()) {
      LOG(info) << "GeneratorMonopoles: transport settings are consistent with the generator "
                << "(G4.monopole=1, mass=" << mLastMass << " GeV, g=" << mLastCharge << " g_D)";
      return kTRUE;
    }

    const std::string hint = "the matching settings for this configuration are: G4.monopole=1;G4.monopoleMass=" +
                             std::to_string(mLastMass) + ";G4.monopoleMagneticCharge=" + std::to_string(mLastCharge);
    for (const auto& p : problems) {
      if (mOnMismatch == kFatal) {
        LOG(error) << "GeneratorMonopoles: " << p;
      } else if (mOnMismatch == kWarn) {
        LOG(warning) << "GeneratorMonopoles: " << p;
      } else {
        LOG(info) << "GeneratorMonopoles (ignored): " << p;
      }
    }
    if (mOnMismatch == kFatal) {
      LOG(fatal) << "GeneratorMonopoles: inconsistent transport configuration; " << hint
                 << ". Set transport.onMismatch to \"warn\" to continue anyway";
      return kFALSE;
    }
    LOG(warning) << "GeneratorMonopoles: " << hint;
    return kTRUE;
  }

  //--------------------------------------------------------------------------
  // kinematics
  //--------------------------------------------------------------------------
  /// Draw one 3-momentum from the configured magnitude and direction specs.
  /// Returns false only if no valid combination was found after many tries.
  bool drawMomentum(double mass, double& px, double& py, double& pz) const
  {
    constexpr int kMaxTries = 10000;
    for (int trial = 0; trial < kMaxTries; ++trial) {
      countMomentumDraw(trial > 0);
      const double phi = mPhi.sample();
      const double a = mAngle.sample();

      // magnitude variable -> |p| (except for the pt/y combination, handled below)
      double mag = mMagnitude.sample();
      double p = 0.;
      if (mMagVar == "p") {
        p = mag;
      } else if (mMagVar == "etot") {
        if (mag < mass) {
          continue;
        }
        p = std::sqrt(std::max(0., mag * mag - mass * mass));
      } else if (mMagVar == "ekin") {
        if (mag < 0.) {
          continue;
        }
        const double e = mag + mass;
        p = std::sqrt(std::max(0., e * e - mass * mass));
      }

      if (mAngleVar == "y") {
        const double y = a;
        const double sh = std::sinh(y), ch = std::cosh(y);
        double pt = 0.;
        if (mMagVar == "pt") {
          pt = mag;
        } else {
          // p^2 = pt^2 cosh^2(y) + m^2 sinh^2(y)  =>  pt^2 = (p^2 - m^2 sinh^2 y)/cosh^2 y
          const double num = p * p - mass * mass * sh * sh;
          if (num < 0.) {
            continue; // this |p| cannot reach this rapidity
          }
          pt = std::sqrt(num) / ch;
        }
        if (pt < 0.) {
          continue;
        }
        pz = std::sqrt(pt * pt + mass * mass) * sh;
        px = pt * std::cos(phi);
        py = pt * std::sin(phi);
        return true;
      }

      // costheta / theta / eta -> cos(theta)
      double ct = 0.;
      if (mAngleVar == "costheta") {
        ct = a;
      } else if (mAngleVar == "theta") {
        ct = std::cos(a);
      } else { // eta
        ct = std::tanh(a);
      }
      if (ct < -1. || ct > 1.) {
        continue;
      }
      const double st = std::sqrt(std::max(0., 1. - ct * ct));

      if (mMagVar == "pt") {
        if (st < 1e-6) {
          continue; // pt is degenerate along the beam axis
        }
        p = mag / st;
      }
      if (p < 0.) {
        continue;
      }
      px = p * st * std::cos(phi);
      py = p * st * std::sin(phi);
      pz = p * ct;
      return true;
    }
    LOG(error) << "GeneratorMonopoles: could not find a momentum consistent with the configured "
               << "magnitude (" << mMagVar << ") and direction (" << mAngleVar
               << ") after " << kMaxTries << " tries; the two ranges are probably incompatible";
    return false;
  }

  /// Every draw drawMomentum() throws away reshapes the configured distributions,
  /// so the rejections are counted and reported instead of passing silently
  /// At 100, 1000, 10000... draws, and once more at the end of the run (stop()
  /// or the destructor) so that short runs are covered too, a warning gives the
  /// fraction rejected so far when it is above kMaxRejectedFraction.
  void countMomentumDraw(bool previousRejected) const
  {
    ++mMomentumDraws;
    if (previousRejected) {
      ++mMomentumRejected;
    }
    if (mMomentumDraws < mNextRejectionReport) {
      return;
    }
    mNextRejectionReport *= 10;
    reportMomentumRejections("the first ");
  }

  void finalMomentumReport()
  {
    if (!mFinalMomentumReportDone) {
      mFinalMomentumReportDone = true;
      reportMomentumRejections("all ");
    }
  }

  void reportMomentumRejections(const char* which) const
  {
    static constexpr double kMaxRejectedFraction = 0.01;
    if (mMomentumRejected == 0) {
      return;
    }
    const double fraction = double(mMomentumRejected) / double(mMomentumDraws);
    std::ostringstream msg;
    msg << "GeneratorMonopoles: " << mMomentumRejected << " of " << which << mMomentumDraws
        << " momentum draws (" << 100. * fraction << "%) were kinematically impossible for "
        << "the configured magnitude (" << mMagVar << ") and direction (" << mAngleVar
        << ") and were redrawn";
    if (fraction > kMaxRejectedFraction) {
      LOG(warning) << msg.str() << ", so the generated distributions are narrower than the "
                   << "configured ones. Make the two ranges compatible (e.g. etot >= mass*cosh(y))";
    } else {
      LOG(info) << msg.str();
    }
  }

  void drawVertex(double& x, double& y, double& z, double& t) const
  {
    x = mVx.isSet() ? mVx.sample() : 0.;
    y = mVy.isSet() ? mVy.sample() : 0.;
    z = mVz.isSet() ? mVz.sample() : 0.;
    t = mVt.isSet() ? mVt.sample() : 0.;
  }

  bool makeSchwingerPair()
  {
    const double m = mLastMass;
    double px = 0., py = 0., pz = 0.;
    if (!drawMomentum(m, px, py, pz)) {
      return false;
    }
    // optional net momentum of the pair; zero by default, which is the
    // back-to-back topology of the reference HepMC samples
    double rx = 0., ry = 0., rz = 0.;
    if (mRecoilPt.isSet()) {
      const double pt = mRecoilPt.sample();
      const double phi = mRecoilPhi.sample();
      rx = pt * std::cos(phi);
      ry = pt * std::sin(phi);
    }
    if (mRecoilPz.isSet()) {
      rz = mRecoilPz.sample();
    }

    double vx, vy, vz, vt;
    drawVertex(vx, vy, vz, vt);

    const double e = std::sqrt(px * px + py * py + pz * pz + m * m);
    TLorentzVector plus(px, py, pz, e);
    TLorentzVector minus(-px, -py, -pz, e);
    if (rx != 0. || ry != 0. || rz != 0.) {
      // The net momentum is given to the pair as a Lorentz boost of the
      // back-to-back configuration (TLorentzVector::Boost), so the pair keeps
      // its invariant mass and the two monopoles stay back-to-back in the pair
      // rest frame. Adding half of the recoil to each momentum instead would
      // silently change the pair mass.
      const double mPair = plus.E() + minus.E(); // pair rest frame: p_tot = 0
      const double eTot = std::sqrt(mPair * mPair + rx * rx + ry * ry + rz * rz);
      const TVector3 beta(rx / eTot, ry / eTot, rz / eTot);
      plus.Boost(beta);
      minus.Boost(beta);
    }

    auto push = [&](int pdg, const TLorentzVector& q) {
      if (mVertexPerObject) {
        drawVertex(vx, vy, vz, vt);
      }
      mObjects.push_back({pdg, q.Px(), q.Py(), q.Pz(), q.E(), vx, vy, vz, vt});
    };
    push(+mPdg, plus);
    push(-mPdg, minus);
    return true;
  }

  bool makeSingle()
  {
    const double m = mLastMass;
    double px = 0., py = 0., pz = 0.;
    if (!drawMomentum(m, px, py, pz)) {
      return false;
    }
    int sign = +1;
    if (mChargeSign == kRandomSign) {
      sign = gRandom->Rndm() < 0.5 ? -1 : +1;
    } else if (mChargeSign == kNegative) {
      sign = -1;
    }
    double vx, vy, vz, vt;
    drawVertex(vx, vy, vz, vt);
    const double e = std::sqrt(px * px + py * py + pz * pz + m * m);
    mObjects.push_back({sign * mPdg, px, py, pz, e, vx, vy, vz, vt});
    return true;
  }

  //--------------------------------------------------------------------------
  static EMode parseMode(const std::string& s)
  {
    if (s == "schwinger" || s == "pair") {
      return kSchwinger;
    }
    if (s == "single") {
      return kSingle;
    }
    throw std::runtime_error("unknown \"mode\" \"" + s + "\" (known: schwinger, single)");
  }
  static const char* modeName(EMode m)
  {
    switch (m) {
      case kSchwinger:
        return "schwinger";
      case kSingle:
        return "single";
    }
    return "unknown";
  }

  //--------------------------------------------------------------------------
  std::string mConfigFile;
  int mVerbose = 1;
  int mGeneratorId = -1; ///< wanted PrimaryGenerator.id, -1 = not requested
  EMode mMode = kSchwinger;
  int mPdg = kMonopolePdgSymm;
  EChargeSign mChargeSign = kRandomSign;

  MonoValue mNObjects, mMass, mCharge;
  MonoValue mMagnitude, mAngle, mPhi;
  MonoValue mVx, mVy, mVz, mVt;
  MonoValue mRecoilPt, mRecoilPz, mRecoilPhi;
  std::string mMagVar = "p";
  std::string mAngleVar;
  bool mVertexPerObject = false;

  bool mSetupDone = false;
  Bool_t mSetupOk = kFALSE;

  bool mCheckTransport = true;
  bool mReportOnly = false; ///< MonopolesTransportKeys(): parse and print, never touch the transport
  bool mMassFromTransport = false;   ///< report mode: the JSON leaves the mass to G4.monopoleMass
  bool mChargeFromTransport = false; ///< report mode: the JSON leaves the charge to G4.monopoleMagneticCharge
  // momentum draws rejected by drawMomentum(), see countMomentumDraw()
  mutable long mMomentumDraws = 0;
  mutable long mMomentumRejected = 0;
  mutable long mNextRejectionReport = 100;
  bool mFinalMomentumReportDone = false;
  bool mMassFromG4 = false;
  EOnMismatch mOnMismatch = kFatal;
  double mTolerance = 1e-4;

  double mLastMass = 0., mLastCharge = 0.;
  std::vector<MonoObject> mObjects;
  unsigned long mNGenerated = 0;
  unsigned long mNEvents = 0;

  ClassDefOverride(GeneratorMonopolesImpl, 1);
};

} // namespace o2::eventgen

/// Loader for GeneratorExternal.funcName:
///
///   GeneratorExternal.funcName=GeneratorMonopoles("myconfig.json")
///
/// With no argument the configuration file is taken from the environment
/// variable MONOPOLES_CONFIG. That route exists because O2DPG strips the inner
/// double quotes out of a -confKey string, which would turn the argument into
/// an unquoted path and break the macro; in a workflow, export MONOPOLES_CONFIG
/// and leave GeneratorExternal.funcName at GeneratorMonopoles() - or leave it
/// empty altogether, since O2 then derives the function name from the file name.
/// With neither, the built-in Schwinger defaults are used.
FairGenerator* GeneratorMonopoles(std::string configFile = "")
{
  if (configFile.empty()) {
    if (const char* fromEnv = std::getenv("MONOPOLES_CONFIG"); fromEnv != nullptr && *fromEnv) {
      configFile = fromEnv;
      LOG(info) << "GeneratorMonopoles: taking the configuration from $MONOPOLES_CONFIG = " << configFile;
    }
  }
  auto* gen = new o2::eventgen::GeneratorMonopolesImpl();
  gen->setConfigFile(configFile);
  return gen;
}

//==============================================================================
// Tools, in this same macro so that the generator needs nothing but ROOT and O2
//==============================================================================

/// The configuration file an entry point should use: the argument, else
/// $MONOPOLES_CONFIG, else none (the built-in defaults).
inline std::string monopolesConfigFile(std::string configFile)
{
  if (configFile.empty()) {
    if (const char* fromEnv = std::getenv("MONOPOLES_CONFIG"); fromEnv != nullptr && *fromEnv) {
      configFile = fromEnv;
    }
  }
  return configFile;
}

/// Prints the transport settings (G4.monopole*, PrimaryGenerator.id) that match a
/// configuration file, as a --configKeyValues string and as an ini section:
///
///   root -l -b -q 'GeneratorMonopoles.C+' -e 'MonopolesTransportKeys("cfg.json")'
///
/// The generator cannot set them itself: they are read in the transport process,
/// before the generator of that process even exists, so they have to be on the
/// command line or in the ini file. Returns 0 on success.
int MonopolesTransportKeys(std::string configFile = "")
{
  auto gen = std::make_unique<o2::eventgen::GeneratorMonopolesImpl>();
  gen->setConfigFile(monopolesConfigFile(std::move(configFile)));
  return gen->printTransportKeys();
}
