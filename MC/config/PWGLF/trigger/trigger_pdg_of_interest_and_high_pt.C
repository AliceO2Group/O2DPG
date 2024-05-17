R__ADD_INCLUDE_PATH($O2DPG_ROOT)
#include "Generators/Trigger.h"
#include "TParticle.h"
#include "TParticlePDG.h"

o2::eventgen::Trigger
trigger_pdg_of_interest_and_high_pt(double pt_leading_min = 5.0, int pdg_of_interest = -2212) {

  auto trigger = [pt_leading_min, pdg_of_interest](const std::vector<TParticle> &particles) -> bool {
    bool contains_particle_of_interest = false;
    bool has_leading_particle = false;

    double pt_max(0);

    for (const auto &particle : particles) {
      int pdg = particle.GetPdgCode();
      if (pdg == pdg_of_interest)
        contains_particle_of_interest = true;

      if (particle.GetStatusCode() <= 0)
        continue;

      if ((abs(pdg) != 11) && (abs(pdg) != 211) && (abs(pdg) != 321) && (abs(pdg) != 2212))
        continue;

      if (particle.Pt() > pt_max)
        pt_max = particle.Pt();
    }

    if (pt_max > pt_leading_min)
      has_leading_particle = true;

    if (has_leading_particle && contains_particle_of_interest)
      return true;
    return false;
  };

  return trigger;
}
