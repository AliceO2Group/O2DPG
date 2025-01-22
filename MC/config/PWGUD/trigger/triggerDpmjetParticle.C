R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
#include <TParticle.h>
#include "Generators/Trigger.h"

/// =================================================================================================================================
/// Select events with at least one particle in a given rapidity or eta window
/// =================================================================================================================================

o2::eventgen::Trigger triggerDzero(double rapidityMin = -1., double rapidityMax = -1.)
{
  return [rapidityMin, rapidityMax](const std::vector<TParticle>& particles) -> bool {
    for (const auto& particle : particles) {
      if (TMath::Abs(particle.GetPdgCode()) == 421)
        if ((particle.Y() > rapidityMin) && (particle.Y() < rapidityMax))
	  return kTRUE;
    }
    return kFALSE;  
  };
}

o2::eventgen::Trigger triggerDcharged(double rapidityMin = -1., double rapidityMax = -1.)
{
  return [rapidityMin, rapidityMax](const std::vector<TParticle>& particles) -> bool {
    for (const auto& particle : particles) {
      if (TMath::Abs(particle.GetPdgCode()) == 411)
        if ((particle.Y() > rapidityMin) && (particle.Y() < rapidityMax))
	  return kTRUE;
    }
    return kFALSE;
  };
}

o2::eventgen::Trigger triggerDstar(double rapidityMin = -1., double rapidityMax = -1.)
{
  return [rapidityMin, rapidityMax](const std::vector<TParticle>& particles) -> bool {
    for (const auto& particle : particles) {
      if (TMath::Abs(particle.GetPdgCode()) == 413)
        if ((particle.Y() > rapidityMin) && (particle.Y() < rapidityMax))
	  return kTRUE;
    }
    return kFALSE;
  };
}

o2::eventgen::Trigger triggerPhi(double rapidityMin = -1., double rapidityMax = -1.)
{
  return [rapidityMin, rapidityMax](const std::vector<TParticle>& particles) -> bool {
    for (std::vector<TParticle>::size_type i = 0; i != (particles.size()-1); i++) {
      if ((particles[i].GetPdgCode() == 321 && particles[i+1].GetPdgCode() == -321) || (particles[i].GetPdgCode() == -321 && particles[i+1].GetPdgCode() == 321))
        if ((particles[i].Eta() > rapidityMin) && (particles[i].Eta() < rapidityMax) && (particles[i+1].Eta() > rapidityMin) && (particles[i+1].Eta() < rapidityMax))
	  return kTRUE;
    }
    return kFALSE;
  };
}

o2::eventgen::Trigger triggerKstar(double rapidityMin = -1., double rapidityMax = -1.)
{
  return [rapidityMin, rapidityMax](const std::vector<TParticle>& particles) -> bool {
    for (std::vector<TParticle>::size_type i = 0; i != (particles.size()-1); i++) {
      if ((particles[i].GetPdgCode() == 321 && particles[i+1].GetPdgCode() == -211) || (particles[i].GetPdgCode() == -211 && particles[i+1].GetPdgCode() == 321))
        if ((particles[i].Eta() > rapidityMin) && (particles[i].Eta() < rapidityMax) && (particles[i+1].Eta() > rapidityMin) && (particles[i+1].Eta() < rapidityMax))
	  return kTRUE;
    }
    return kFALSE;
  };
}



