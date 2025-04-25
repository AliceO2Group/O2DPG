// Copyright 2019-2020 CERN and copyright holders of ALICE O2.
// See https://alice-o2.web.cern.ch/copyright for details of the copyright holders.
// All rights not expressly granted are reserved.
//
// This software is distributed under the terms of the GNU General Public
// License v3 (GPL Version 3), copied verbatim in the file "COPYING".
//
// In applying this license CERN does not waive the privileges and immunities
// granted to it by virtue of its status as an Intergovernmental Organization
// or submit itself to any jurisdiction.

#include "Pythia8/Pythia.h"
#include "fairlogger/Logger.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "TSystem.h"
#include "TMath.h"
#include <cmath>
#include <vector>
#include <fstream>
#include <string>
using namespace Pythia8;

/// Coalescence afterburner for Pythia8
/// Utility to compute naive coalescence afterburner as done in PRL 126, 101101 (2021)

enum NucleiBits {
  kDeuteron = 0,
  kTriton = 1,
  kHe3 = 2,
  kHyperTriton = 3,
  kHe4 = 4,
};

std::vector<unsigned int> pdgList = {10010010, 1000010030, 1000020030, 1010010030, 1000020040};
std::vector<float> massList = {1.875612, 2.80892113298, 2.808391, 2.991134, 3.727379};

bool doCoal(Pythia8::Event& event, int charge, int pdgCode, float mass, bool trivialCoal, double coalescenceRadius, bool nuclFromDecay, int iD1, int iD2, int iD3 = -1, int iD4 = -1)
{
  std::vector<int> nucleonIDs = std::vector<int>{iD1, iD2};
  // add A=3 and A=4 nuclei if enabled
  if (iD3 > 0) {
    nucleonIDs.push_back(iD3);
  }
  if (iD4 > 0) {
    nucleonIDs.push_back(iD4);
  }
  Pythia8::Vec4 p;
  for (auto nID : nucleonIDs) {
    if (event[nID].status() < 0) {
      // nucleon already used in coalescence
      return false;
    }
    p += event[nID].p();
  }
  bool isCoalescence = true;
  for (auto nID : nucleonIDs) {
    auto pN = event[nID].p();
    pN.bstback(p);
    // trivial coal does not check the distance of the nucleons
    if (pN.pAbs() > coalescenceRadius && !trivialCoal) {
      isCoalescence = false;
      break;
    }
  }
  if (!isCoalescence) {
    return false;
  }
  p.e(std::hypot(p.pAbs(), mass));

  if (!nuclFromDecay) {
    /// keep the original nucleons with negative status, store the mother with status 94
    event.append((charge * 2 - 1) * pdgCode, 94, 0, 0, 0, 0, 0, 0, p.px(), p.py(), p.pz(), p.e(), mass);
    for (auto nID : nucleonIDs) {
      event[nID].statusNeg();
      event[nID].daughter1(event.size() - 1);
    }
  } else {
    // first nucleon will be replaced by the nucleus, the others will be removed
    bool swap = true;
    int nRemoved = 0;
    for (auto iPart{0}; iPart < event.size(); ++iPart) {
      for (auto nID : nucleonIDs) {
        if (iPart == nID && swap) {
          // replace the nucleon with the nucleus
          LOG(debug) << "Replacing nucleon with index " << iPart << " and pdg code " << event[iPart].id() << " with nucleus with pdg code " << (charge * 2 - 1) * pdgCode;
          event[iPart].id((charge * 2 - 1) * pdgCode);
          event[iPart].status(94);
          event[iPart].px(p.px());
          event[iPart].py(p.py());
          event[iPart].pz(p.pz());
          event[iPart].e(std::hypot(p.pAbs(), mass));
          event[iPart].m(mass);
          swap = false;
        } else if (iPart == nID - nRemoved && !swap) {
          LOG(debug) << "Removing nucleon with index " << iPart << " and pdg code " << event[iPart].id();
          event.remove(iPart, iPart, true);
          nRemoved++;
        }
      }
    }
  }
  LOG(debug) << "Adding a " << (charge * 2 - 1) * pdgCode << " with p = " << p.px() << ", " << p.py() << ", " << p.pz() << ", E = " << p.e();
  return true;
}

bool CoalescencePythia8(Pythia8::Event& event, std::vector<unsigned int> inputPdgList = {}, bool trivialCoal = false, double coalMomentum = 0.4, int firstDauID = -1, int lastDauId = -1)
{
  const double coalescenceRadius{0.5 * 1.122462 * coalMomentum};
  // if coalescence from a heavy hadron, loop only between firstDauID and lastDauID
  int loopStart = firstDauID > -1 ? firstDauID : 0;
  int loopEnd = lastDauId > -1 ? lastDauId : event.size() - 1;
  // fill the nuclear mask
  uint8_t nuclearMask = 0;
  for (auto nuclPdg : inputPdgList) {
    if (nuclPdg == pdgList[NucleiBits::kDeuteron]) {
      nuclearMask |= (1 << kDeuteron);
    } else if (nuclPdg == pdgList[NucleiBits::kTriton]) {
      nuclearMask |= (1 << kTriton);
    } else if (nuclPdg == pdgList[NucleiBits::kHe3]) {
      nuclearMask |= (1 << kHe3);
    } else if (nuclPdg == pdgList[NucleiBits::kHyperTriton]) {
      nuclearMask |= (1 << kHyperTriton);
    } else if (nuclPdg == pdgList[NucleiBits::kHe4]) {
      nuclearMask |= (1 << kHe4);
    } else {
      LOG(fatal) << "Unknown pdg code for coalescence generator: " << nuclPdg;
      return false;
    }
  }
  // fill nucleon pools
  std::vector<int> protons[2], neutrons[2], lambdas[2];
  for (auto iPart{loopStart}; iPart <= loopEnd; ++iPart) {
    if (std::abs(event[iPart].y()) > 1.) // skip particles with y > 1
    {
      continue;
    }
    if (std::abs(event[iPart].id()) == 2212) {
      protons[event[iPart].id() > 0].push_back(iPart);
    } else if (std::abs(event[iPart].id()) == 2112) {
      neutrons[event[iPart].id() > 0].push_back(iPart);
    } else if (std::abs(event[iPart].id()) == 3122 && (nuclearMask & (1 << kHyperTriton))) {
      lambdas[event[iPart].id() > 0].push_back(iPart);
    }
  }
  // run coalescence
  bool nuclFromDecay = firstDauID > -1;
  bool coalHappened = false;

  for (int iC{0}; iC < 2; ++iC) {
    for (int iP{0}; iP < protons[iC].size(); ++iP) {
      for (int iN{0}; iN < neutrons[iC].size(); ++iN) {
        if (nuclearMask & (1 << kDeuteron)) {
          coalHappened |= doCoal(event, iC, pdgList[kDeuteron], massList[kDeuteron], trivialCoal, coalescenceRadius, nuclFromDecay, protons[iC][iP], neutrons[iC][iN]);
        }
        if (nuclearMask & (1 << kTriton)) {
          for (int iN2{iN + 1}; iN2 < neutrons[iC].size(); ++iN2) {
            coalHappened |= doCoal(event, iC, pdgList[kTriton], massList[kTriton], trivialCoal, coalescenceRadius, nuclFromDecay, protons[iC][iP], neutrons[iC][iN], neutrons[iC][iN2]);
          }
        }
        if (nuclearMask & (1 << kHe3)) {
          for (int iP2{iP + 1}; iP2 < protons[iC].size(); ++iP2) {
            coalHappened |= doCoal(event, iC, pdgList[kHe3], massList[kHe3], trivialCoal, coalescenceRadius, nuclFromDecay, protons[iC][iP], protons[iC][iP2], neutrons[iC][iN]);
          }
        }
        if (nuclearMask & (1 << kHyperTriton)) {
          for (int iL{0}; iL < lambdas[iC].size(); ++iL) {
            coalHappened |= doCoal(event, iC, pdgList[kHyperTriton], massList[kHyperTriton], trivialCoal, coalescenceRadius, nuclFromDecay, protons[iC][iP], neutrons[iC][iN], lambdas[iC][iL]);
          }
        }
        if (nuclearMask & (1 << kHe4)) {
          for (int iP2{iP + 1}; iP2 < protons[iC].size(); ++iP2) {
            for (int iN2{iN + 1}; iN2 < neutrons[iC].size(); ++iN2) {
              coalHappened |= doCoal(event, iC, pdgList[kHe4], massList[kHe4], trivialCoal, coalescenceRadius, nuclFromDecay, protons[iC][iP], protons[iC][iP2], neutrons[iC][iN], neutrons[iC][iN2]);
            }
          }
        }
      }
    }
  }
  return coalHappened;
}