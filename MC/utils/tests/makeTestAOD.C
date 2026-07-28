// makeTestAOD.C
//
// Builds a tiny synthetic AO2D that reproduces, in a few kB, every pathology
// AODBcRewriter.C exists to repair — so the tool can be tested in seconds
// without a simulation, a GRID job or a committed binary fixture.
//
//   root -l -b -q 'makeTestAOD.C("AO2D_test.root")'
//
// -----------------------------------------------------------------------------
// WHAT THE FIXTURE CONTAINS
// -----------------------------------------------------------------------------
// One DF holding two "sub-timeframe" blocks, as o2-aod-merger produces when MC
// timeframes are merged into the parent data file's DF (data-embedding
// anchoring).  That layout is what makes all of the following true at once:
//
//   * fGlobalBC is non-monotonic   — block B's BCs are earlier than block A's
//   * fGlobalBC has a duplicate    — BC 201 appears in both blocks
//   * MCCollisions have a duplicate — same (BC, fEventWeight) in both blocks
//   * the tracks' "-1" ambiguous group is SPLIT into two runs, one per block
//
// so the BC sort cascades into a collision reorder, which cascades into a track
// regroup.  Every table then has to follow, and every index column has to be
// remapped — which is the whole job.
//
// Row payloads are unique by construction (fX = 10+i for tracks, 1000+i for MFT
// tracks, 2000+i for fwd tracks, ...) so a test can state ground truth as
// "fwd track 2000+i must still point at MFT track 1000+i" and check it after
// the rows have moved.
//
// Cross-table links present here, and why each one matters:
//
//   O2fwdtrack.fIndexMFTTracks               -> another Stage-1b table
//   O2fwdtrack.fIndexFwdTracks_MatchMCHTrack -> ITSELF
//        These two are O2-7098.  Both referents are reordered in the same stage
//        as the referrer, so they only work if writing is deferred until every
//        permutation is known.
//   O2v0/O2cascade fIndexTracks_Pos/_Neg/fIndexTracks, fIndexV0s
//        references into reordered tables from tables that are not reordered.
//   O2ambiguoustrack.fIndexSliceBCs          -> a [2] slice into a DEDUPLICATED
//        table; endpoints must follow the compaction.
//   O2mcparticle fIndexArray_Mothers (VLA) / fIndexSlice_Daughters ([2])
//        intra-table links that must follow the table's own reordering.
//   paste-join children (O2trackextra_002, O2fwdtrackcov, O2mc*label)
//        no index column of their own for the row order — they must follow
//        their parent row-for-row.
//   O2origin
//        no links at all — exercises the fast-clone path.

#ifndef __CLING__
#include "TFile.h"
#include "TTree.h"
#include <cstdint>
#include <iostream>
#include <vector>
#endif

namespace
{

// ---------------------------------------------------------------------------
// The fixture layout, spelled out once so tests can refer to it.
//
// BCs (input row -> fGlobalBC):   block A: 0:200 1:201 2:202
//                                 block B: 3:100 4:101 5:201  (5 duplicates 1)
//   -> after Stage 0: [100,101,200,201,202], bcPerm = [2,3,4,0,1,3]
//
// Collisions:  0->bc0  1->bc2  |  2->bc3  3->bc4
//   -> remapped to 2,4,0,1 -> reordered to [2,3,0,1]
//
// MCCollisions: 0->bc0 w1.5   1->bc1 w2.5  |  2->bc3 w3.5  3->bc4 w4.5
//               4->bc5 w2.5   <- same (newBC,weight) as 1: dropped as duplicate
//
// Tracks:      A: 0,1 -> coll0   2 -> coll1   3 -> -1
//              B: 4 -> coll2     5 -> coll3   6 -> -1      (-1 group is split)
// MFT tracks:  A: 0 -> coll0     1 -> coll1   2 -> -1
//              B: 3 -> coll2     4 -> coll3   5 -> -1
// Fwd tracks:  A: 0 -> coll0     1 -> coll1   2 -> -1
//              B: 3 -> coll2     4 -> coll3   5 -> -1
//   fwd i matches MFT i (all six).  fwd 1 -> fwd 0 and fwd 4 -> fwd 3 as
//   MCH matches; the rest have none.
// ---------------------------------------------------------------------------

const int      kNBC        = 6;
const uint64_t kGlobalBC[] = {200, 201, 202, 100, 101, 201};

const int kNColl        = 4;
const int kCollBC[]     = {0, 2, 3, 4};

const int   kNMcColl       = 5;
const int   kMcCollBC[]    = {0, 1, 3, 4, 5};
const float kMcCollWeight[]= {1.5f, 2.5f, 3.5f, 4.5f, 2.5f};

const int kNPartPerMcColl = 3;                 // mother + two daughters
const int kNPart          = kNMcColl * kNPartPerMcColl;

const int kNTrack      = 7;
const int kTrackColl[] = {0, 0, 1, -1, 2, 3, -1};
const int kTrackMcPart[] = {0, 1, 3, -1, 6, 9, -1};

const int kNMft      = 6;
const int kMftColl[] = {0, 1, -1, 2, 3, -1};
const int kMftMcPart[] = {0, 3, -1, 6, 9, -1};

const int kNFwd        = 6;
const int kFwdColl[]   = {0, 1, -1, 2, 3, -1};
const int kFwdMft[]    = {0, 1, 2, 3, 4, 5};    // fwd i <-> MFT i
const int kFwdMatch[]  = {-1, 0, -1, -1, 3, -1};// fwd -> fwd self-reference
// The MC particle of a fwd track is the one of its matched MFT track: a correct
// rewrite keeps "same particle" at 100%, a broken one collapses it to ~0 —
// exactly the metric O2-7098 was reported with.
const int kFwdMcPart[] = {0, 3, -1, 6, 9, -1};

const int kNV0        = 2;
const int kV0Coll[]   = {0, 2};
const int kV0Pos[]    = {0, 4};
const int kV0Neg[]    = {1, 5};

const int kNCasc      = 1;
const int kCascColl[] = {0};
const int kCascV0[]   = {0};
const int kCascBach[] = {2};

const int kNAmb          = 2;
const int kAmbTrack[]    = {3, 6};
const int kAmbBCFirst[]  = {0, 3};
const int kAmbBCLast[]   = {2, 4};

} // namespace

void makeTestAOD(const char *outFileName = "AO2D_test.root")
{
  TFile f(outFileName, "RECREATE");
  TDirectory *df = f.mkdir("DF_1000000000001");
  df->cd();

  // ---- O2bc_001 -----------------------------------------------------------
  {
    TTree t("O2bc_001", "bcs");
    uint64_t globalBC; int runNumber; uint64_t triggerMask;
    t.Branch("fRunNumber",   &runNumber,   "fRunNumber/I");
    t.Branch("fGlobalBC",    &globalBC,    "fGlobalBC/l");
    t.Branch("fTriggerMask", &triggerMask, "fTriggerMask/l");
    for (int i = 0; i < kNBC; ++i) {
      runNumber = 300000; globalBC = kGlobalBC[i]; triggerMask = 1000 + i;
      t.Fill();
    }
    t.Write();
  }

  // ---- O2bcflag (paste-joined to O2bc) ------------------------------------
  {
    TTree t("O2bcflag", "bc flags");
    uint8_t flags;
    t.Branch("fBCFlags", &flags, "fBCFlags/b");
    for (int i = 0; i < kNBC; ++i) { flags = (uint8_t)(i + 1); t.Fill(); }
    t.Write();
  }

  // ---- O2collision_001 ----------------------------------------------------
  {
    TTree t("O2collision_001", "collisions");
    int bc; float posX;
    t.Branch("fIndexBCs", &bc,   "fIndexBCs/I");
    t.Branch("fPosX",     &posX, "fPosX/F");
    for (int i = 0; i < kNColl; ++i) { bc = kCollBC[i]; posX = 500.f + i; t.Fill(); }
    t.Write();
  }

  // ---- O2mccollision_001 --------------------------------------------------
  {
    TTree t("O2mccollision_001", "mc collisions");
    int bc; float weight, posX;
    t.Branch("fIndexBCs",   &bc,     "fIndexBCs/I");
    t.Branch("fPosX",       &posX,   "fPosX/F");
    t.Branch("fEventWeight",&weight, "fEventWeight/F");
    for (int i = 0; i < kNMcColl; ++i) {
      bc = kMcCollBC[i]; weight = kMcCollWeight[i];
      // The duplicate must be byte-identical to the row it duplicates, as it
      // would be in a real merged file.
      posX = (i == 4) ? 600.f + 1 : 600.f + i;
      t.Fill();
    }
    t.Write();
  }

  // ---- O2mcparticle_001 ---------------------------------------------------
  {
    TTree t("O2mcparticle_001", "mc particles");
    int mcColl, pdg, motherSize, mothers[4], daughters[2];
    t.Branch("fIndexMcCollisions",      &mcColl,     "fIndexMcCollisions/I");
    t.Branch("fPdgCode",                &pdg,        "fPdgCode/I");
    t.Branch("fIndexArray_Mothers_size",&motherSize, "fIndexArray_Mothers_size/I");
    t.Branch("fIndexArray_Mothers",      mothers,    "fIndexArray_Mothers[fIndexArray_Mothers_size]/I");
    t.Branch("fIndexSlice_Daughters",    daughters,  "fIndexSlice_Daughters[2]/I");
    for (int c = 0; c < kNMcColl; ++c) {
      int base = c * kNPartPerMcColl;
      for (int j = 0; j < kNPartPerMcColl; ++j) {
        mcColl = c;
        pdg    = 100 + base + j;   // unique per particle
        if (j == 0) {              // the mother: daughters are the next two rows
          motherSize   = 0;
          daughters[0] = base + 1;
          daughters[1] = base + 2;
        } else {                   // a daughter: its mother is the first row
          motherSize   = 1;
          mothers[0]   = base;
          daughters[0] = -1;
          daughters[1] = -1;
        }
        t.Fill();
      }
    }
    t.Write();
  }

  // ---- O2track_iu + paste-join children -----------------------------------
  {
    TTree t("O2track_iu", "tracks");
    int coll; float x;
    t.Branch("fIndexCollisions", &coll, "fIndexCollisions/I");
    t.Branch("fX",               &x,    "fX/F");
    for (int i = 0; i < kNTrack; ++i) { coll = kTrackColl[i]; x = 10.f + i; t.Fill(); }
    t.Write();
  }
  {
    TTree t("O2trackextra_002", "track extras");
    uint8_t nClsFindable;
    t.Branch("fTPCNClsFindable", &nClsFindable, "fTPCNClsFindable/b");
    for (int i = 0; i < kNTrack; ++i) { nClsFindable = (uint8_t)(50 + i); t.Fill(); }
    t.Write();
  }
  {
    TTree t("O2mctracklabel", "track mc labels");
    int mcPart; uint16_t mask;
    t.Branch("fIndexMcParticles", &mcPart, "fIndexMcParticles/I");
    t.Branch("fMcMask",           &mask,   "fMcMask/s");
    for (int i = 0; i < kNTrack; ++i) { mcPart = kTrackMcPart[i]; mask = (uint16_t)i; t.Fill(); }
    t.Write();
  }

  // ---- O2mfttrack_001 + label ---------------------------------------------
  {
    TTree t("O2mfttrack_001", "mft tracks");
    int coll; float x;
    t.Branch("fIndexCollisions", &coll, "fIndexCollisions/I");
    t.Branch("fX",               &x,    "fX/F");
    for (int i = 0; i < kNMft; ++i) { coll = kMftColl[i]; x = 1000.f + i; t.Fill(); }
    t.Write();
  }
  {
    TTree t("O2mcmfttracklabel", "mft mc labels");
    int mcPart; uint16_t mask;
    t.Branch("fIndexMcParticles", &mcPart, "fIndexMcParticles/I");
    t.Branch("fMcMask",           &mask,   "fMcMask/s");
    for (int i = 0; i < kNMft; ++i) { mcPart = kMftMcPart[i]; mask = (uint16_t)(100 + i); t.Fill(); }
    t.Write();
  }

  // ---- O2fwdtrack + cov + label -------------------------------------------
  // The table O2-7098 is about: two index columns pointing into tables that are
  // reordered in the same stage as this one, one of them itself.
  {
    TTree t("O2fwdtrack", "fwd tracks");
    int coll, mft, match; float x;
    t.Branch("fIndexCollisions",              &coll,  "fIndexCollisions/I");
    t.Branch("fX",                            &x,     "fX/F");
    t.Branch("fIndexMFTTracks",               &mft,   "fIndexMFTTracks/I");
    t.Branch("fIndexFwdTracks_MatchMCHTrack", &match, "fIndexFwdTracks_MatchMCHTrack/I");
    for (int i = 0; i < kNFwd; ++i) {
      coll = kFwdColl[i]; mft = kFwdMft[i]; match = kFwdMatch[i]; x = 2000.f + i;
      t.Fill();
    }
    t.Write();
  }
  {
    TTree t("O2fwdtrackcov", "fwd track cov");
    float sigmaX;
    t.Branch("fSigmaX", &sigmaX, "fSigmaX/F");
    for (int i = 0; i < kNFwd; ++i) { sigmaX = 0.5f + i; t.Fill(); }
    t.Write();
  }
  {
    TTree t("O2mcfwdtracklabel", "fwd mc labels");
    int mcPart; uint16_t mask;
    t.Branch("fIndexMcParticles", &mcPart, "fIndexMcParticles/I");
    t.Branch("fMcMask",           &mask,   "fMcMask/s");
    for (int i = 0; i < kNFwd; ++i) { mcPart = kFwdMcPart[i]; mask = (uint16_t)(200 + i); t.Fill(); }
    t.Write();
  }

  // ---- O2v0_002 / O2cascade_001 -------------------------------------------
  {
    TTree t("O2v0_002", "v0s");
    int coll, pos, neg;
    t.Branch("fIndexCollisions",  &coll, "fIndexCollisions/I");
    t.Branch("fIndexTracks_Pos",  &pos,  "fIndexTracks_Pos/I");
    t.Branch("fIndexTracks_Neg",  &neg,  "fIndexTracks_Neg/I");
    for (int i = 0; i < kNV0; ++i) { coll = kV0Coll[i]; pos = kV0Pos[i]; neg = kV0Neg[i]; t.Fill(); }
    t.Write();
  }
  {
    TTree t("O2cascade_001", "cascades");
    int coll, v0, bach;
    t.Branch("fIndexCollisions", &coll, "fIndexCollisions/I");
    t.Branch("fIndexV0s",        &v0,   "fIndexV0s/I");
    t.Branch("fIndexTracks",     &bach, "fIndexTracks/I");
    for (int i = 0; i < kNCasc; ++i) { coll = kCascColl[i]; v0 = kCascV0[i]; bach = kCascBach[i]; t.Fill(); }
    t.Write();
  }

  // ---- O2ambiguoustrack (slice into the deduplicated BC table) ------------
  {
    TTree t("O2ambiguoustrack", "ambiguous tracks");
    int track, sliceBCs[2];
    t.Branch("fIndexTracks",    &track,   "fIndexTracks/I");
    t.Branch("fIndexSliceBCs",   sliceBCs,"fIndexSliceBCs[2]/I");
    for (int i = 0; i < kNAmb; ++i) {
      track = kAmbTrack[i]; sliceBCs[0] = kAmbBCFirst[i]; sliceBCs[1] = kAmbBCLast[i];
      t.Fill();
    }
    t.Write();
  }

  // ---- O2origin (no links at all — exercises the fast-clone path) ---------
  {
    TTree t("O2origin", "origins");
    int dataframeID;
    t.Branch("fDataframeID", &dataframeID, "fDataframeID/I");
    dataframeID = 1; t.Fill();
    t.Write();
  }

  f.Write();
  f.Close();
  std::cout << "makeTestAOD: wrote " << outFileName << "\n";
}
