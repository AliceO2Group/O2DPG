#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TDatabasePDG.h"
#include "TMath.h"
#include "TParticlePDG.h"
#include "TRandom3.h"
#include "TSystem.h"
#include "TVector2.h"
#include "fairlogger/Logger.h"
#include <cmath>
#include <fstream>
#include <string>
#include <vector>
using namespace Pythia8;
#endif

/// Event generator using Pythia ropes (Adapted from task generator_pythia8_doubleLambdas.C)
/// Triggers events containing at least two generated phi(1020) mesons.

class GeneratorPythia8DoublePhi : public o2::eventgen::GeneratorPythia8
{
public:
    /// Constructor
    GeneratorPythia8DoublePhi(int gapSize = 0, double minPt = 0.0, double maxPt = 100.0, double maxEta = 0.8)
        : o2::eventgen::GeneratorPythia8(),
          mGapSize(gapSize),
          mMinPt(minPt),
          mMaxPt(maxPt),
          mMaxEta(maxEta)
    {
        fmt::printf(">> Pythia8 generator: two phi(1020) mesons, gap = %d, minPtPhi = %f, maxPtPhi = %f, |etaPhi| < %f\n", gapSize, minPt, maxPt, maxEta);
    }
    /// Destructor
    ~GeneratorPythia8DoublePhi() = default;

    bool Init() override
    {
        addSubGenerator(0, "Pythia8 events with two phi(1020) mesons");
        return o2::eventgen::GeneratorPythia8::Init();
    }

protected:
    bool isPhiFromHFDecay(const Pythia8::Particle &p, const Pythia8::Event &event)
    {

        // Walk up ancestry
        int motherId = p.mother1();

        while (motherId > 0)
        {
            // Get mother
            const auto &mother = event[motherId];
            const int absMotherPdg = std::abs(mother.id());

            // Check if particle is from HF decay
            if (((absMotherPdg / 100) % 10 == 4) ||
                ((absMotherPdg / 100) % 10 == 5) ||
                ((absMotherPdg / 1000) % 10 == 4) ||
                ((absMotherPdg / 1000) % 10 == 5))
            {
                return true;
            }

            motherId = mother.mother1();
        }
        return false;
    }

    bool generateEvent() override
    {
        // fmt::printf(">> Generating event %d\n", mGeneratedEvents);

        bool genOk = false;
        int localCounter{0};
        constexpr int kMaxTries{100000};

        // If mGapSize <= 0, filter ALL events to contain two phis.
        // Otherwise, generate mGapSize gap events before 1 triggered event.
        if (mGapSize > 0 && (mGeneratedEvents % (mGapSize + 1) < mGapSize))
        {
            genOk = GeneratorPythia8::generateEvent();
            // fmt::printf(">> Gap-event (no phi check)\n");
        }
        else
        {
            while (!genOk && localCounter < kMaxTries)
            {
                if (GeneratorPythia8::generateEvent())
                {
                    genOk = selectEvent(mPythia.event);
                }
                localCounter++;
            }
            if (!genOk)
            {
                fmt::printf("Failed to generate triggered event after %d tries\n", kMaxTries);
                return false;
            }
            // fmt::printf(">> Triggered event: event accepted after %d iterations (double phi(1020))\n", localCounter);
        }

        notifySubGenerator(0);
        mGeneratedEvents++;
        return true;
    }

    bool selectEvent(Pythia8::Event &event)
    {
        int nPhi{0};

        for (int i = 0; i < event.size(); i++)
        {
            const auto &p = event[i];

            if (std::abs(p.id()) != 333)
                continue;

            if (p.pT() < mMinPt || p.pT() > mMaxPt)
                continue;

            if (std::abs(p.eta()) > mMaxEta)
                continue;

            if (isPhiFromHFDecay(p, event))
                continue;

            // // Avoid double-counting copy/history entries:
            // // Ensure this is the physical produced phi (e.g. check if its daughter is a copy of itself)
            // int d1 = p.daughter1();
            // int d2 = p.daughter2();
            // if (d1 > 0 && d1 == d2 && std::abs(event[d1].id()) == 333)
            // {
            //     // p decayed into another copy of phi, so skip this intermediate entry
            //     continue;
            // }

            nPhi++;
        }
        if (nPhi < 2)
            return false;

        return true;
    }

private:
    int mGapSize{0};
    double mMinPt{0.0};
    double mMaxPt{100.0};
    double mMaxEta{0.8};
    uint64_t mGeneratedEvents{0};
};

///___________________________________________________________
FairGenerator *generateDoublePhi(int gap = 0, double minPt = 0.0, double maxPt = 100.0, double maxEta = 0.8)
{
    auto myGenerator = new GeneratorPythia8DoublePhi(gap, minPt, maxPt, maxEta);

    myGenerator->readString("333:onMode = off");
    myGenerator->readString("333:onIfMatch = 321 -321");

    auto seed = (gRandom->TRandom::GetSeed() % 900000000);
    myGenerator->readString("Random:setSeed on");
    myGenerator->readString("Random:seed " + std::to_string(seed));

    return myGenerator;
}