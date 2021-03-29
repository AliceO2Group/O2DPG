R__ADD_INCLUDE_PATH($O2DPG_ROOT)
#include "MC/run/common/detector_acceptance.C"
#include <TParticle.h>
#include "Generators/Trigger.h"

/// =================================================
/// \file prompt_gamma.C

/// \brief Select prompt photon events within acceptance or associated parton flavor
///
/// Select prompt photons checking the first generated outoging photon on the 2->2 process
/// Then select if requested that the associated parton has a given PDG value.
/// Finally check if the photon is in the detector acceptances defined in detector_acceptance.C
/// Only valid for PYTHIA8.
///
/// \author Gustavo Conesa Balbastre (LPSC-IN2P3-CNRS)
/// =================================================

o2::eventgen::Trigger prompt_gamma( )
{
  return [](const std::vector<TParticle>& particles) -> bool {
    
//    for(Int_t ipart = 3; ipart < 10; ipart++)
//    {
//      TParticle parton = particles.at(ipart);
//      printf("parton %d, PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n", ipart, 
//             parton.GetPdgCode(), 
//             parton.GetStatusCode(), 
//             parton.GetFirstMother(),
//             parton.Energy(), 
//             parton.Pt(),
//             parton.Eta(),
//             parton.Phi()*TMath::RadToDeg());
//    }
  
    // Get the outgoing 2->2 partons. 
    // The photon and the associated outgoing parton are in position 5 or 6.
    // Note that in PYTHIA6 they are at positions 7 or 8.
    TParticle gamma  = particles.at(5);
    TParticle parton = particles.at(6);
    if ( gamma.GetPdgCode() != 22 ) {
      gamma  = particles.at(6);
      parton = particles.at(5);
    }
    
    if ( gamma.GetPdgCode() != 22 )
    {
      printf("No direct photon found in the parton list!\n");
      return false;
    }
    
    // Select the flavour of the outgoing parton
    //
    Int_t partonpdg = 0;
    if ( gSystem->Getenv("CONFIG_OUTPARTON_PDG") )
      partonpdg = atoi(gSystem->Getenv("CONFIG_OUTPARTON_PDG"));
    
    if ( partonpdg > 0 && partonpdg <= 22 ) 
    {
      // d  1, u  2, s  3, c  4, b  5, t  6
      
      //printf("Select outgoing partons with pdg = %d\n",partonpdg);
  
      if ( TMath::Abs(parton.GetPdgCode()) != partonpdg )
      {
        //printf("--- Rejected event, parton pdg ---\n");
        return false;
      }
    }
    
    // Select photons within acceptance
    //
    Int_t acceptance = 0;
    if ( gSystem->Getenv("PARTICLE_ACCEPTANCE") )
      acceptance = atoi(gSystem->Getenv("PARTICLE_ACCEPTANCE"));
    //printf("Requested acceptance %d\n",acceptance);
    
    if ( detector_acceptance(acceptance, gamma.Phi(),gamma.Eta()) ) 
    {
      printf("+++ Accepted event +++ \n");
      printf("gamma, PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n", 
             gamma.GetPdgCode(), gamma.GetStatusCode(), gamma.GetFirstMother(),
             gamma.Energy()    , gamma.Pt(),
             gamma.Eta()       , gamma.Phi()*TMath::RadToDeg());
      
      printf("parton, PDG %d, status %d, mother %d, E %2.2f, pT %2.2f, eta %2.2f, phi %2.2f\n", 
             parton.GetPdgCode(), parton.GetStatusCode(), parton.GetFirstMother(),
             parton.Energy()    , parton.Pt(),
             parton.Eta()       , parton.Phi()*TMath::RadToDeg());
      
//      // Check difference in pT and azimuthal angle, it should be 0 and +-180 degrees, respectively.
//      printf("parton-photon, Delta E %2.2f, Delta pT %2.2f, Delta eta %2.2f, Delta phi %2.2f\n", 
//             parton.Energy()-gamma.Energy(), parton.Pt() - gamma.Pt(),
//             parton.Eta()   -gamma.Eta()   , parton.Phi()*TMath::RadToDeg()-gamma.Phi()*TMath::RadToDeg());
      
      return true;
    }
    else  
    {
      //printf("--- Rejected event ---\n");
      return false;
    }
    
    return true; // triggered
        
  };
}
