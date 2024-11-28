R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
#include "Generators/Trigger.h"
#include "TParticle.h"
#include "TParticlePDG.h"

o2::eventgen::Trigger trigger_ccbar(double yMin = -1.5, double yMax = 1.5)
{
  auto trigger = [yMin, yMax](const std::vector<TParticle>& particles) -> bool {
    Bool_t isHF = kFALSE;
    Bool_t isSelected = kFALSE;
    int mpdg = -1;
    double rapidity = -999.;
    for (const auto& particle : particles) {
      mpdg = TMath::Abs(particle.GetPdgCode());
      if (mpdg == 4 || mpdg == 5) {
        isHF = kTRUE;
        rapidity = particle.Y();
        if ((rapidity > yMin) && (rapidity < yMax))
          isSelected = kTRUE;
      }
    }
    if (!(isHF && isSelected))
      return kFALSE;
    return kTRUE;
  };
  return trigger;
}
