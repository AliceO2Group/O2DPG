R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
#include <TParticle.h>
#include "Generators/Trigger.h"

/// =================================================================================================================================
/// Select event with VM or track in a given rapidity or eta window
/// =================================================================================================================================

o2::eventgen::Trigger selectMotherPartInAcc(double rapidityMin = -1., double rapidityMax = -1.)
{
  return [rapidityMin, rapidityMax](const std::vector<TParticle>& particles) -> bool {
    for (const auto& particle : particles) {
      if (TMath::Abs(particle.GetPdgCode()) == 2112)continue;
      if (particle.GetFirstMother() == -1)
        if ((particle.Y() > rapidityMin) && (particle.Y() < rapidityMax))
	  return kTRUE;
    }
    return kFALSE;  
  };
}

o2::eventgen::Trigger selectDaughterPartInAcc(double etaMin = -1., double etaMax = -1.)
{
  return [etaMin, etaMax](const std::vector<TParticle>& particles) -> bool {
    for (const auto& particle : particles) {
      if (TMath::Abs(particle.GetPdgCode()) == 2112)continue;
      if (particle.GetFirstMother() == -1)
        if ((particle.Y() < etaMin) || (particle.Y() > etaMax)) return kFALSE;
	  if (particle.GetFirstMother() != -1 && particle.GetFirstDaughter() == -1 && particle.GetPdgCode() != 22 && TMath::Abs(particle.GetPdgCode()) != 12 && TMath::Abs(particle.GetPdgCode()) != 14 && TMath::Abs(particle.GetPdgCode()) != 16)
      if ((particle.Eta() < etaMin) || (particle.Eta() > etaMax)) return kFALSE; 
    }
    return kTRUE;  
  };
}

o2::eventgen::Trigger selectDileptonsInAcc(double etaMin = -1., double etaMax = -1.)
{
  return [etaMin, etaMax](const std::vector<TParticle>& particles) -> bool {
    for (const auto& particle : particles) {
	  if (particle.GetFirstMother() != -1 && particle.GetFirstDaughter() == -1 && (TMath::Abs(particle.GetPdgCode()) == 11 || TMath::Abs(particle.GetPdgCode() == 13)))
		  if ((particle.Eta() < etaMin) || (particle.Eta() > etaMax)) return kFALSE;
    }
    return kTRUE;
  };
}

o2::eventgen::Trigger selectDirectPartInAcc(double etaMin = -1., double etaMax = -1.)
{
  return [etaMin, etaMax](const std::vector<TParticle>& particles) -> bool {
    for (const auto& particle : particles) {
      if (particle.GetFirstMother() == -1)
        if ((particle.Eta() < etaMin) || (particle.Eta() > etaMax))
	  return kFALSE;
    }
    return kTRUE;  
  };
}
