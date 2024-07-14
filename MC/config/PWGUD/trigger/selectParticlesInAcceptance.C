R__ADD_INCLUDE_PATH($O2DPG_ROOT)
#include <TParticle.h>
#include "Generators/Trigger.h"

/// =================================================================================================================================
/// Select event with VM or track in a given rapidity or eta window
/// =================================================================================================================================

o2::eventgen::Trigger selectMotherPartInAcc(double rapidityMin = -1., double rapidityMax = -1.)
{
  return [rapidityMin, rapidityMax](const std::vector<TParticle>& particles) -> bool {
    for (const auto& particle : particles) {
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
      if (particle.GetFirstMother() == -1)
        if ((particle.Y() < etaMin) || (particle.Y() > etaMax)) return kFALSE;
	  if (particle.GetFirstMother() != -1 && particle.GetFirstDaughter() == -1)
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