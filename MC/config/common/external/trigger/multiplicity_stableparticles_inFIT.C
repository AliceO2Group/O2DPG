// multiplicity trigger using the number of "stable" particle in the FIT acceptance
//
//   usage: o2sim --trigger external --extTrgFile multiplicity_stableparticles_inFIT.C
// options:                          --extTrgFunc "multiplicity_stableparticles_inFIT(5350)"
//

/// \author R+Bailhache - February 2022

#include "Generators/Trigger.h"
#include "TParticle.h"
#include "TParticlePDG.h"
#include "TMath.h"

Bool_t IsStable(Int_t pdg);

o2::eventgen::Trigger
  multiplicity_stableparticles_inFIT(int minNch = 5350)
{
  return [minNch](const std::vector<TParticle>& particles) -> bool {
    int nch = 0;
   

    for (const auto& particle : particles) {
      
      if (particle.GetStatusCode() != 1) continue;
      if (!particle.GetPDG()) continue;
      //printf("pass the pdg condition\n");
      Int_t pdgcode = particle.GetPdgCode();
      //printf("Pdgcode is %d\n",pdgcode);
      if (particle.GetPDG()->Charge() == 0) continue;
      //printf("Is charge\n");
      if(!IsStable(pdgcode)) continue;
      //printf("Pass stable\n");

      // FIT acceptance
      if(!((2.2<particle.Eta() && particle.Eta()< 5.0) || (-3.4<particle.Eta() && particle.Eta()<-2.3))) continue;
      //printf("Pass FIT acceptance\n");
    
      nch++;
    }
    bool fired = kFALSE;
    if(nch >= minNch) fired = kTRUE;
    //printf("nch %d and minNch %d\n",nch,minNch);
    return fired;
  };

  //return trigger;
}


Bool_t IsStable(Int_t pdg)
{
  //
  // Decide whether particle (pdg) is stable
  //

  const Int_t kNstable = 19;
  Int_t pdgStable[kNstable] = {
    22,             // Photon
    11,          // Electron
    -13,          // Muon
    211,            // Pion
    321,             // Kaon
    310,           // K0s
    130,            // K0l
    2212,            // Proton
    2112,           // Neutron
    3122,           // Lambda_0
    3212,         // Sigma0
    3112,        // Sigma Minus
    3222,         // Sigma Plus
    3312,               // Xsi Minus
    3322,               // Xsi
    3334,               // Omega
    12,               // Electron Neutrino
    14,              // Muon Neutrino
    16              // Tau Neutrino
  };
  

  // All ions/nucleons are considered as stable
  // Nuclear code is 10LZZZAAAI
  if(pdg>1000000000)return kTRUE;

 

  Bool_t isStablee = kFALSE;
  for (Int_t i = 0; i < kNstable; i++) {
   if (TMath::Abs(pdg) == TMath::Abs(pdgStable[i])) {
     isStablee = kTRUE;
     break;
   }
  }

  return isStablee;
}

