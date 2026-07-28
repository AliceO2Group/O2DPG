// testAODBcRewriter.C
//
// Physics-readable assertions on a rewritten AO2D, on top of the generic
// AODBcRewriterValidate() / AODBcRewriterCheckLinks() checks.
//
//   root -l -b -q 'testAODBcRewriter.C("AO2D_test.root","AO2D_test_rewritten.root")'
//
// Returns 0 on success, the number of failed assertions otherwise.
//
// Expectations are derived from the INPUT file rather than hard-coded, so the
// fixture in makeTestAOD.C can grow without this file having to be kept in
// sync.  What is hard-coded is only the *invariant*: a rewrite permutes rows,
// it never changes which row points at which.
//
// The headline assertion is the one from the O2-7098 report: for a fwd track
// with an MFT match, the MFT leg and the MCH leg must belong to the same MC
// particle.  In this fixture the matching is perfect by construction, so the
// correct answer is 100% and a mis-remapped fIndexMFTTracks gives ~0% —
// the same signature seen in the anchored pO production.

#ifndef __CLING__
#include "TFile.h"
#include "TTree.h"
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <vector>
#endif

namespace
{

int gFailures = 0;

void fail(const std::string &what)
{
  std::cerr << "  [FAIL] " << what << "\n";
  ++gFailures;
}

void pass(const std::string &what)
{
  std::cout << "  [ ok ] " << what << "\n";
}

TTree *get(TDirectory *d, const char *name)
{
  TTree *t = dynamic_cast<TTree *>(d->Get(name));
  if (!t) fail(std::string("table ") + name + " missing");
  return t;
}

std::vector<Int_t> readInt(TTree *t, const char *branch)
{
  std::vector<Int_t> v;
  if (!t || !t->GetBranch(branch)) return v;
  Int_t x = 0;
  t->ResetBranchAddresses();
  t->SetBranchAddress(branch, &x);
  v.reserve(t->GetEntries());
  for (Long64_t i = 0; i < t->GetEntries(); ++i) { t->GetEntry(i); v.push_back(x); }
  t->ResetBranchAddresses();
  return v;
}

std::vector<Float_t> readFloat(TTree *t, const char *branch)
{
  std::vector<Float_t> v;
  if (!t || !t->GetBranch(branch)) return v;
  Float_t x = 0;
  t->ResetBranchAddresses();
  t->SetBranchAddress(branch, &x);
  v.reserve(t->GetEntries());
  for (Long64_t i = 0; i < t->GetEntries(); ++i) { t->GetEntry(i); v.push_back(x); }
  t->ResetBranchAddresses();
  return v;
}

std::vector<ULong64_t> readULong(TTree *t, const char *branch)
{
  std::vector<ULong64_t> v;
  if (!t || !t->GetBranch(branch)) return v;
  ULong64_t x = 0;
  t->ResetBranchAddresses();
  t->SetBranchAddress(branch, &x);
  v.reserve(t->GetEntries());
  for (Long64_t i = 0; i < t->GetEntries(); ++i) { t->GetEntry(i); v.push_back(x); }
  t->ResetBranchAddresses();
  return v;
}

// The multiset of (referrer payload, referent payload) pairs implied by an
// index column.  Rows with no link contribute (payload, sentinel).
std::multimap<float, float> linkPairs(const std::vector<Int_t> &idx,
                                      const std::vector<Float_t> &ownPayload,
                                      const std::vector<Float_t> &refPayload)
{
  std::multimap<float, float> pairs;
  for (size_t i = 0; i < idx.size() && i < ownPayload.size(); ++i) {
    float ref = -1.f;
    if (idx[i] >= 0 && (size_t)idx[i] < refPayload.size()) ref = refPayload[idx[i]];
    pairs.emplace(ownPayload[i], ref);
  }
  return pairs;
}

void expectSameLinks(const char *what,
                     const std::multimap<float, float> &in,
                     const std::multimap<float, float> &out)
{
  if (in.size() != out.size()) {
    fail(std::string(what) + ": row count changed (" +
         std::to_string(in.size()) + " -> " + std::to_string(out.size()) + ")");
    return;
  }
  std::vector<std::pair<float, float>> a(in.begin(), in.end()), b(out.begin(), out.end());
  std::sort(a.begin(), a.end());
  std::sort(b.begin(), b.end());
  if (a != b) {
    size_t shown = 0;
    for (size_t i = 0; i < a.size() && shown < 5; ++i) {
      if (a[i] != b[i]) {
        std::cerr << "        row " << a[i].first << " pointed at " << a[i].second
                  << " before, at " << b[i].second << " after\n";
        ++shown;
      }
    }
    fail(std::string(what) + ": links not preserved");
    return;
  }
  pass(std::string(what) + ": links preserved (" + std::to_string(a.size()) + " rows)");
}

} // namespace

int testAODBcRewriter(const char *inFileName  = "AO2D_test.root",
                      const char *outFileName = "AO2D_test_rewritten.root")
{
  gFailures = 0;
  std::cout << "testAODBcRewriter: " << inFileName << " -> " << outFileName << "\n";

  TFile fin(inFileName, "READ");
  TFile fout(outFileName, "READ");
  if (fin.IsZombie())  { std::cerr << "cannot open " << inFileName << "\n";  return 1; }
  if (fout.IsZombie()) { std::cerr << "cannot open " << outFileName << "\n"; return 1; }

  const char *dfName = "DF_1000000000001";
  TDirectory *din  = dynamic_cast<TDirectory *>(fin.Get(dfName));
  TDirectory *dout = dynamic_cast<TDirectory *>(fout.Get(dfName));
  if (!din || !dout) { std::cerr << "DF " << dfName << " missing\n"; return 1; }

  // ---- Stage 0 did its job -------------------------------------------------
  {
    auto bc = readULong(get(dout, "O2bc_001"), "fGlobalBC");
    bool mono = true;
    for (size_t i = 1; i < bc.size(); ++i) if (bc[i] <= bc[i - 1]) mono = false;
    if (!mono)          fail("O2bc_001: fGlobalBC not strictly monotonic after rewrite");
    else                pass("O2bc_001: fGlobalBC strictly increasing");
    if (bc.size() != 5) fail("O2bc_001: expected 5 unique BCs, got " + std::to_string(bc.size()));
    else                pass("O2bc_001: duplicate BC removed (6 -> 5)");
  }

  // ---- MCCollision deduplication ------------------------------------------
  {
    Long64_t n = get(dout, "O2mccollision_001")->GetEntries();
    if (n != 4) fail("O2mccollision_001: expected 4 rows after dedup, got " + std::to_string(n));
    else        pass("O2mccollision_001: duplicate MC collision removed (5 -> 4)");
  }

  // ---- The O2-7098 links ---------------------------------------------------
  {
    auto fwdXIn   = readFloat(get(din,  "O2fwdtrack"),      "fX");
    auto fwdXOut  = readFloat(get(dout, "O2fwdtrack"),      "fX");
    auto mftXIn   = readFloat(get(din,  "O2mfttrack_001"),  "fX");
    auto mftXOut  = readFloat(get(dout, "O2mfttrack_001"),  "fX");

    expectSameLinks("O2fwdtrack.fIndexMFTTracks",
                    linkPairs(readInt(get(din,  "O2fwdtrack"), "fIndexMFTTracks"), fwdXIn,  mftXIn),
                    linkPairs(readInt(get(dout, "O2fwdtrack"), "fIndexMFTTracks"), fwdXOut, mftXOut));

    expectSameLinks("O2fwdtrack.fIndexFwdTracks_MatchMCHTrack (self-reference)",
                    linkPairs(readInt(get(din,  "O2fwdtrack"), "fIndexFwdTracks_MatchMCHTrack"), fwdXIn,  fwdXIn),
                    linkPairs(readInt(get(dout, "O2fwdtrack"), "fIndexFwdTracks_MatchMCHTrack"), fwdXOut, fwdXOut));
  }

  // ---- The reported symptom: MFT leg and MCH leg of the same global muon ---
  // must carry the same MC particle.  This is Maurice Coquet's tableMakerMC
  // check, reduced to the label tables.  Perfect matching by construction here.
  {
    auto mftIdx = readInt(get(dout, "O2fwdtrack"),        "fIndexMFTTracks");
    auto fwdLbl = readInt(get(dout, "O2mcfwdtracklabel"), "fIndexMcParticles");
    auto mftLbl = readInt(get(dout, "O2mcmfttracklabel"), "fIndexMcParticles");
    int checked = 0, same = 0;
    for (size_t i = 0; i < mftIdx.size() && i < fwdLbl.size(); ++i) {
      if (mftIdx[i] < 0 || (size_t)mftIdx[i] >= mftLbl.size()) continue;
      ++checked;
      if (fwdLbl[i] == mftLbl[mftIdx[i]]) ++same;
    }
    if (checked == 0)        fail("MFT-MCH match check: nothing to check");
    else if (same != checked) fail("MFT-MCH match: sameParticle=" + std::to_string(same) +
                                   "/" + std::to_string(checked) + ", expected all (this is O2-7098)");
    else                      pass("MFT-MCH match: sameParticle=" + std::to_string(same) +
                                   "/" + std::to_string(checked) + " (100%)");
  }

  // ---- References into the reordered track tables from elsewhere -----------
  {
    auto trkXIn  = readFloat(get(din,  "O2track_iu"), "fX");
    auto trkXOut = readFloat(get(dout, "O2track_iu"), "fX");

    // V0s have no float payload of their own; identify them by their positive
    // leg, which is unique in this fixture.
    auto v0PosIn  = readInt(get(din,  "O2v0_002"), "fIndexTracks_Pos");
    auto v0PosOut = readInt(get(dout, "O2v0_002"), "fIndexTracks_Pos");
    auto v0NegIn  = readInt(get(din,  "O2v0_002"), "fIndexTracks_Neg");
    auto v0NegOut = readInt(get(dout, "O2v0_002"), "fIndexTracks_Neg");
    std::vector<Float_t> v0IdIn, v0IdOut;
    for (auto p : v0PosIn)  v0IdIn.push_back(p >= 0 && (size_t)p < trkXIn.size()  ? trkXIn[p]  : -1.f);
    for (auto p : v0PosOut) v0IdOut.push_back(p >= 0 && (size_t)p < trkXOut.size() ? trkXOut[p] : -1.f);
    expectSameLinks("O2v0_002.fIndexTracks_Neg",
                    linkPairs(v0NegIn,  v0IdIn,  trkXIn),
                    linkPairs(v0NegOut, v0IdOut, trkXOut));
  }

  // ---- Paste-join children still line up with their parent ----------------
  {
    auto fwdXOut = readFloat(get(dout, "O2fwdtrack"),    "fX");
    auto sigmaIn = readFloat(get(din,  "O2fwdtrackcov"), "fSigmaX");
    auto sigmaOut= readFloat(get(dout, "O2fwdtrackcov"), "fSigmaX");
    auto fwdXIn  = readFloat(get(din,  "O2fwdtrack"),    "fX");
    std::map<float, float> expect;   // fX -> fSigmaX, from the input
    for (size_t i = 0; i < fwdXIn.size() && i < sigmaIn.size(); ++i) expect[fwdXIn[i]] = sigmaIn[i];
    bool aligned = (fwdXOut.size() == sigmaOut.size());
    for (size_t i = 0; aligned && i < fwdXOut.size(); ++i)
      if (expect.count(fwdXOut[i]) == 0 || expect[fwdXOut[i]] != sigmaOut[i]) aligned = false;
    if (!aligned) fail("O2fwdtrackcov: paste-join alignment with O2fwdtrack broken");
    else          pass("O2fwdtrackcov: follows O2fwdtrack row-for-row");
  }

  // ---- Intra-table MC particle links --------------------------------------
  {
    TTree *mcp = get(dout, "O2mcparticle_001");
    auto pdg = readInt(mcp, "fPdgCode");
    Int_t daughters[2] = {-1, -1};
    mcp->ResetBranchAddresses();
    mcp->SetBranchAddress("fIndexSlice_Daughters", daughters);
    int checked = 0, bad = 0;
    for (Long64_t i = 0; i < mcp->GetEntries(); ++i) {
      mcp->GetEntry(i);
      if (daughters[0] < 0) continue;
      ++checked;
      // In the fixture a mother with fPdgCode P has daughters P+1 and P+2.
      if (daughters[1] - daughters[0] != 1) { ++bad; continue; }
      if (pdg[daughters[0]] != pdg[i] + 1 || pdg[daughters[1]] != pdg[i] + 2) ++bad;
    }
    mcp->ResetBranchAddresses();
    if (checked == 0) fail("O2mcparticle_001: no daughter slices found");
    else if (bad)     fail("O2mcparticle_001: " + std::to_string(bad) + "/" +
                           std::to_string(checked) + " daughter slices point at the wrong particles");
    else              pass("O2mcparticle_001: all " + std::to_string(checked) +
                           " daughter slices still point at the right particles");
  }

  // ---- Slice into the deduplicated BC table -------------------------------
  {
    auto bcIn  = readULong(get(din,  "O2bc_001"), "fGlobalBC");
    auto bcOut = readULong(get(dout, "O2bc_001"), "fGlobalBC");
    TTree *aIn  = get(din,  "O2ambiguoustrack");
    TTree *aOut = get(dout, "O2ambiguoustrack");
    Int_t sIn[2] = {-1, -1}, sOut[2] = {-1, -1};
    aIn->ResetBranchAddresses();  aIn->SetBranchAddress("fIndexSliceBCs", sIn);
    aOut->ResetBranchAddresses(); aOut->SetBranchAddress("fIndexSliceBCs", sOut);
    int bad = 0;
    Long64_t n = std::min(aIn->GetEntries(), aOut->GetEntries());
    for (Long64_t i = 0; i < n; ++i) {
      aIn->GetEntry(i); aOut->GetEntry(i);
      for (int j = 0; j < 2; ++j) {
        if (sIn[j] < 0 || (size_t)sIn[j] >= bcIn.size()) continue;
        if (sOut[j] < 0 || (size_t)sOut[j] >= bcOut.size()) { ++bad; continue; }
        if (bcIn[sIn[j]] != bcOut[sOut[j]]) ++bad;
      }
    }
    aIn->ResetBranchAddresses(); aOut->ResetBranchAddresses();
    if (bad) fail("O2ambiguoustrack.fIndexSliceBCs: " + std::to_string(bad) +
                  " endpoint(s) no longer point at the same bunch crossing");
    else     pass("O2ambiguoustrack.fIndexSliceBCs: endpoints follow the BC compaction");
  }

  if (gFailures == 0) std::cout << "testAODBcRewriter: ALL CHECKS PASSED\n";
  else                std::cout << "testAODBcRewriter: " << gFailures << " CHECK(S) FAILED\n";
  return gFailures;
}
