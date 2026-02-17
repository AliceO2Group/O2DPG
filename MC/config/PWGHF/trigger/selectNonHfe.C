#include <TParticle.h>
#include "Generators/Trigger.h"
#include <vector>
#include <TMath.h>

///============================================================================

/// Select π⁰ and η within a given rapidity window for enhancement
/// pdgPartForAccCut: PDG of the particle to select (111=π⁰, 221=η)
/// minNb: minimum number of such particles per event for enhancement

////  authors: Rashi Gupta (rashi.gupta@cern.ch)
///  authors: Ravindra Singh (ravindra.singh@cern.ch)
/// ============================================================================
o2::eventgen::Trigger selectPionEtaWithinAcc(TString pdgPartForAccCut = "111;221", double rapidityMin = -1.5, double rapidityMax = 1.5, int minNb = 1)
{
    return [pdgPartForAccCut, rapidityMin, rapidityMax, minNb](const std::vector<TParticle>& particles) -> bool {
    TObjArray* obj = pdgPartForAccCut.Tokenize(";");
    int count = 0;
    for (const auto& particle : particles) {
      int pdg = TMath::Abs(particle.GetPdgCode());
      double y = particle.Y();

      if (y < rapidityMin || y > rapidityMax) continue;

      for (int i = 0; i < obj->GetEntriesFast(); ++i) {
        int pdgCode = std::stoi(obj->At(i)->GetName());

        if (pdg == pdgCode) {
          count++;
          break;
        }
      }
    }
        // Only accept events with at least minNb π⁰/η
        if (count >= minNb)
            return kTRUE;
        else
            return kFALSE;
    };
}
