R__ADD_INCLUDE_PATH(${O2DPG_MC_CONFIG_ROOT})
#include "MC/run/common/detector_acceptance.C"
#include <TParticle.h>
#include "Generators/Trigger.h"

/// =================================================
/// \file decay_gamma_jets.C

/// \brief Select jet events with high pT decay photons within acceptance or associated parton flavor
///
/// Select 2->2 jet events with high pT decay photons on a given acceptance, defined in detector_acceptance.C
/// Only valid for PYTHIA8.
///
/// \author Gustavo Conesa Balbastre (LPSC-IN2P3-CNRS)
/// =================================================

o2::eventgen::Trigger decay_gamma_jets(int acceptanceIn = 0, float ptminIn = 0)
{
  return [acceptanceIn, ptminIn](const std::vector<TParticle>& particles) -> bool {
    // Select decay photon with min pT
    Float_t ptmin = ptminIn;
    if (ptmin <= 0 && gSystem->Getenv("PTTRIGMIN"))
      ptmin = atof(gSystem->Getenv("PTTRIGMIN"));
    // printf("Requested minimum pT %2.2f\n",ptmin);

    // Select photons within acceptance
    //
    Int_t acceptance = acceptanceIn;
    if (acceptance <= 0 && gSystem->Getenv("PARTICLE_ACCEPTANCE"))
      acceptance = atoi(gSystem->Getenv("PARTICLE_ACCEPTANCE"));
    // printf("Requested acceptance %d\n",acceptance);

    // Particle loop
    //
    // printf("N particles %lu\n",particles.size());
    Int_t ipart = 0;
    for (const TParticle part : particles) {
      ipart++;

      if (part.Pt() < ptmin)
        continue;

      if (part.GetPdgCode() != 22)
        continue;

      TParticle mother;
      if (part.GetFirstMother() > 5) // below 5 (7 in pythia6) 2->2 partons and colliding nucleons
        mother = particles.at(part.GetFirstMother());
      else
        continue;

      if (TMath::Abs(mother.GetPdgCode()) <= 100)
        continue;

      // if ( mother.GetStatusCode() != 0 )
      //        continue;

      if (!detector_acceptance(acceptance, part.Phi(), part.Eta()))
        continue;

      printf("Selected photon index %d, PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n",
             ipart - 1, part.GetPdgCode(),
             part.GetStatusCode(),
             part.GetFirstMother(),
             part.Energy(), part.Pt(),
             part.Eta(), part.Phi() * TMath::RadToDeg());

      //      printf("mother %d, PDG %d, status %d, 1st daugh %d, last daugh %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n",
      //             part.GetFirstMother(), mother.GetPdgCode(),
      //             mother.GetStatusCode(),
      //             mother.GetFirstDaughter(), mother.GetLastDaughter(),
      //             mother.Energy(), mother.Pt(),
      //             mother.Eta(),    mother.Phi()*TMath::RadToDeg());
      //
      //      printf("+++ Accepted event +++ \n");

      return true;

    } // loop

    // printf("+++ Rejected event +++ \n");

    return false;
  };
}
