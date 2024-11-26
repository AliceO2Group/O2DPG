R__ADD_INCLUDE_PATH(${O2DPG_MC_CONFIG_ROOT})
#include "MC/run/common/detector_acceptance.C"
#include "Pythia8/Pythia.h"

/// =================================================
/// \file prompt_gamma_hook.C

/// \brief Select prompt photon events within acceptance or associated parton flavor using Pythia Hooks.
///
/// Select prompt photons checking the first generated outoging photon on the 2->2 process
/// Then select if requested that the associated parton has a given PDG value.
/// Finally check if the photon is in the detector acceptances defined in detector_acceptance.C
/// Only valid for PYTHIA8 and using Hooks
///
/// \author Gustavo Conesa Balbastre (LPSC-IN2P3-CNRS)
/// =================================================

class UserHooks_promptgamma : public Pythia8::UserHooks
{

 public:
  UserHooks_promptgamma() = default;
  ~UserHooks_promptgamma() = default;
  bool canVetoPartonLevel() override { return true; };
  bool doVetoPartonLevel(const Pythia8::Event& event) override
  {

    //    printf("Event,  size %d\n", event.size());

    // Get the outgoing 2->2 partons.
    // The photon and the associated outgoing parton are in position 5 or 6.
    // Note that in PYTHIA6 they are at positions 7 or 8.
    Int_t idGam = 5;
    Int_t idPar = 6;
    if (event[idGam].id() != 22) {
      idGam = 6;
      idPar = 5;
    }

    if (event[idGam].id() != 22) {
      printf("No direct photon found in the parton list!\n");

      for (Int_t ida = 0; ida < 10; ida++) {
        printf("parton %d, PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n", ida,
               event[ida].id(),
               event[ida].status(),
               event[ida].mother1(),
               event[ida].e(),
               event[ida].pT(),
               event[ida].eta(),
               event[ida].phi() * TMath::RadToDeg());
      }

      return true;
    }

    if (mOutPartonPDG > 0 && mOutPartonPDG <= 22) {
      // d  1, u  2, s  3, c  4, b  5, t  6

      if (TMath::Abs(event[idPar].id()) != mOutPartonPDG) {
        // printf("--- Rejected event, parton pdg ---\n");
        return true;
      }
    }

    // Select photons within acceptance
    //
    if (detector_acceptance(mAcceptance, event[idGam].phi(), event[idGam].eta())) {
      // printf("+++ Accepted event +++ \n");
      printf("Selected gamma, id %d, PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n", idGam,
             event[idGam].id(), event[idGam].status(), event[idGam].mother1(),
             event[idGam].e(), event[idGam].pT(),
             event[idGam].eta(), event[idGam].phi() * TMath::RadToDeg());

      //     printf("Back-to-back parton, id  %d, PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n", idPar,
      //                 event[idPar].id() , event[idPar].status(), event[idPar].mother1(),
      //                 event[idPar].e()  , event[idPar].pT(),
      //                 event[idPar].eta(), event[idPar].phi()*TMath::RadToDeg());
      //
      //      // Check difference in pT and azimuthal angle, it should be 0 and +-180 degrees, respectively.
      //      printf("parton-photon, Delta E %2.2f, Delta pT %2.2f, Delta eta %2.2f, Delta phi %2.2f\n",
      //             event[idPar].e()  - event[idGam].e(),
      //             event[idPar].pT() - event[idGam].pT(),
      //             event[idPar].eta()- event[idGam].eta(),
      //             event[idPar].phi()*TMath::RadToDeg()-event[idGam].phi()*TMath::RadToDeg());

      return false;
    } else {
      // printf("--- Rejected event ---\n");
      return true;
    }

    return false;
  };

  void setAcceptance(int val) { mAcceptance = val; };
  void setOutPartonPDG(int val) { mOutPartonPDG = val; };

 private:
  int mAcceptance = 0;
  int mOutPartonPDG = 0;
};

Pythia8::UserHooks*
  pythia8_userhooks_promptgamma(int acc = 0, int pdgPar = 0)
{
  auto hooks = new UserHooks_promptgamma();

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
