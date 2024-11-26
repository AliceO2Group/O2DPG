R__ADD_INCLUDE_PATH(${O2DPG_MC_CONFIG_ROOT})
#include "MC/run/common/detector_acceptance.C"
#include "Pythia8/Pythia.h"

/// =================================================
/// \file jets_hook.C

/// \brief Select jet events within acceptance or associated parton flavor using Pythia Hooks.
///
/// Select outoging parton/jets on the 2->2 process, at least one in a selected acceptance and
/// optionally select the parton with a given PDG value.
/// Only valid for PYTHIA8 and using Hooks
///
/// \author Gustavo Conesa Balbastre (LPSC-IN2P3-CNRS)
/// =================================================

class UserHooks_jets : public Pythia8::UserHooks
{

 public:
  UserHooks_jets() = default;
  ~UserHooks_jets() = default;
  bool canVetoPartonLevel() override { return true; };
  bool doVetoPartonLevel(const Pythia8::Event& event) override
  {

    //    for (Int_t id = 0; id < 10; id++)
    //    {
    //      printf("parton %d PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n",
    //             id, event[id].id() , event[id].status(), event[id].mother1(),
    //             event[id].e()  , event[id].pT(),
    //             event[id].eta(), event[id].phi()*TMath::RadToDeg());
    //    }

    // Get the outgoing 2->2 partons.
    // The jets are in position 5 or 6.
    // Note that in PYTHIA6 they are at positions 7 or 8.
    int id1 = 5;
    int id2 = 6;

    // Check the first jet
    //
    bool acc1 = detector_acceptance(mAcceptance, event[id1].phi(), event[id1].eta());
    bool okpdg1 = true;

    if (mOutPartonPDG > 0 && TMath::Abs(event[id1].id()) != mOutPartonPDG)
      okpdg1 = false;

    // Check the second jet
    //
    bool acc2 = detector_acceptance(mAcceptance, event[id2].phi(), event[id2].eta());
    bool okpdg2 = true;

    if (mOutPartonPDG > 0 && TMath::Abs(event[id2].id()) != mOutPartonPDG)
      okpdg2 = false;

    // printf("acc1 %d, acc2 %d, okpdg1 %d, okpdf2 %d\n",acc1,acc2,okpdg1,okpdg2);

    if ((acc1 || acc2) && (okpdg1 || okpdg2)) {
      printf("--- Accepted event ---\n");
      printf("\t --- jet 1 ---\n");
      printf("\t PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n",
             event[id1].id(), event[id1].status(), event[id1].mother1(),
             event[id1].e(), event[id1].pT(),
             event[id1].eta(), event[id1].phi() * TMath::RadToDeg());

      printf("\t --- jet 2 ---\n");
      printf("\t PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n",
             event[id2].id(), event[id2].status(), event[id2].mother1(),
             event[id2].e(), event[id2].pT(),
             event[id2].eta(), event[id2].phi() * TMath::RadToDeg());

      return false;
    }

    // Jets rejected
    //
    printf("\t --- Rejected event ---\n");

    return true;
  };

  void setAcceptance(int val) { mAcceptance = val; };
  void setOutPartonPDG(int val) { mOutPartonPDG = val; };

 private:
  int mAcceptance = 0;
  int mOutPartonPDG = 0;
};

Pythia8::UserHooks*
  pythia8_userhooks_jets(int acc = 0, int pdgPar = 0)
{
  auto hooks = new UserHooks_jets();

  // If default settings, check if not set via environmental variables
  //
  if (!pdgPar && gSystem->Getenv("CONFIG_OUTPARTON_PDG")) {
    pdgPar = atoi(gSystem->Getenv("CONFIG_OUTPARTON_PDG"));
    printf("Select outgoing partons with pdg = %d\n", pdgPar);
  }

  if (!acc && gSystem->Getenv("PARTICLE_ACCEPTANCE")) {
    acc = atoi(gSystem->Getenv("PARTICLE_ACCEPTANCE"));
    printf("Requested acceptance %d\n", acc);
  }

  hooks->setAcceptance(acc);
  hooks->setOutPartonPDG(pdgPar);

  return hooks;
}
