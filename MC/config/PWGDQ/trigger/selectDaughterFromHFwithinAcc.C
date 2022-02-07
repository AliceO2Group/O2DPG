R__ADD_INCLUDE_PATH($O2DPG_ROOT)
#include <TParticle.h>
#include "Generators/Trigger.h"

/// =================================================================================================================================
/// Select daughters from HF particles produced in a given rapidity window
/// pdgPartForAccCut: pdg of the particle (coming from c / b) requested within the rapidity window [rapidityMin, rapidityMax]
/// cutOnSingleChild: if true the condition on the rapidity is required for only one of the child particles (e.g. bb -> J/psi J/psi, bb -> ee,...)
/// Tested for: 
///  	- non-prompt J/psi / Psi(2S) 
///  	- dielectron / dimuon pairs from cc and bb
///	- single electrons / muons from b and b -> c -> e 
/// =================================================================================================================================
Int_t GetFlavour(Int_t pdgCode);

o2::eventgen::Trigger selectDaughterFromHFwithinAcc(Int_t pdgPartForAccCut=443, Bool_t cutOnSingleChild = kTRUE, double rapidityMin = -1., double rapidityMax = -1.)
{
  return [pdgPartForAccCut,cutOnSingleChild,rapidityMin,rapidityMax](const std::vector<TParticle>& particles) -> bool {
  
  int nsig = 0; int mpdg = -1; int mpdgUpperFamily = -1; double rapidity = -999.; 
  Bool_t isSelectedY = kFALSE; if(!cutOnSingleChild) isSelectedY = kTRUE; 
  Bool_t isHF = kFALSE;
  for (const auto& particle : particles) {
	  if(cutOnSingleChild && TMath::Abs(particle.GetPdgCode()) == pdgPartForAccCut){
	  Int_t mi = particle.GetMother(0); 
	  if(mi<0) continue;
          TParticle mother = particles.at(mi);
          mpdg=TMath::Abs(mother.GetPdgCode());
          mpdgUpperFamily=(mpdg>1000 ? mpdg+1000 : mpdg+100); 
          if(GetFlavour(mpdg) == 5 || GetFlavour(mpdgUpperFamily) == 5){ // keep particles from (b->) c 
	     rapidity = particle.Y();
	     if( (rapidity > rapidityMin) && (rapidity < rapidityMax) ) isSelectedY = kTRUE; 
	    }
	  }
         ///////
	 if(!cutOnSingleChild && TMath::Abs(particle.GetPdgCode()) == pdgPartForAccCut){
          Int_t mi = particle.GetMother(0);
          if(mi<0) continue;
          TParticle mother = particles.at(mi);
          mpdg=TMath::Abs(mother.GetPdgCode());
          if( (GetFlavour(mpdg) == 5) || (GetFlavour(mpdg) == 4)){
	     isHF = kTRUE; 
             rapidity = particle.Y();
             if( (rapidity < rapidityMin) || (rapidity > rapidityMax) ) isSelectedY = kFALSE;
            }
          }
    }
    //
    if(cutOnSingleChild && !isSelectedY) return kFALSE; 
    if(!cutOnSingleChild && !(isHF && isSelectedY)) return kFALSE; 
    return kTRUE;  
  };

}

o2::eventgen::Trigger selectHFwithinAcc(Int_t pdgPartForAccCut=521, Bool_t cutonSinglePart=kTRUE, double rapidityMin = -1., double rapidityMax = -1.)
{
  return [pdgPartForAccCut,cutonSinglePart,rapidityMin,rapidityMax](const std::vector<TParticle>& particles) -> bool {

  int nsig = 0; double rapidity = -999.;
  //Bool_t isSelectedY = kFALSE; if(!cutOnSinglePart) isSelectedY = kTRUE;
  for (const auto& particle : particles) {
          if(TMath::Abs(particle.GetPdgCode()) == pdgPartForAccCut){
             rapidity = particle.Y();
             if( (rapidity > rapidityMin) && (rapidity < rapidityMax) ) nsig++;
            }
          }
    //
    if(!cutonSinglePart && (nsig < 2)) return kFALSE;
    return kTRUE;
  };

}


Int_t GetFlavour(Int_t pdgCode)
  {
  //
  // return the flavour of a particle
  // input: pdg code of the particle
  // output: Int_t
  //         3 in case of strange (open and hidden)
  //         4 in case of charm (")
  //         5 in case of beauty (")
  //
  Int_t pdg = TMath::Abs(pdgCode);
  //Resonance
  if (pdg > 100000) pdg %= 100000;
  if(pdg > 10000)  pdg %= 10000;
  // meson ?
  if(pdg > 10) pdg/=100;
  // baryon ?
  if(pdg > 10) pdg/=10;
  return pdg;
  }

