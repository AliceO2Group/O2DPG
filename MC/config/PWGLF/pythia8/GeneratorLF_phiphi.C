/// generator_phi_resonance.C
#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Generators/GeneratorPythia8Param.h"
#include "Pythia8/Pythia.h"
#include "TRandom3.h"
#include "TMath.h"
#include "TParticle.h"
#include "TSystem.h"
#if __has_include("SimulationDataFormat/MCGenStatus.h")
#include "SimulationDataFormat/MCGenStatus.h"
#else
#include "SimulationDataFormat/MCGenProperties.h"
#endif
#if __has_include("SimulationDataFormat/MCUtils.h")
#include "SimulationDataFormat/MCUtils.h"
#endif
#include <cmath>
#include <string>
#include <vector>
#endif

class GeneratorPhiResonance : public o2::eventgen::GeneratorPythia8
{
public:
    GeneratorPhiResonance(int resoPDG = 999999,
                          int customPhiPDG = 888888,
                          float ptMin = 0.0, float ptMax = 50.0, float ptMaxPhi = 100.0,
                          float yMin = -1.0, float yMax = 1.0,
                          std::string pythiaCfgMb = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/pythia8_inel_136tev.cfg",
                          int signalInterval = 3)
        : GeneratorPythia8(), mResoPDG(resoPDG), mCustomPhiPDG(customPhiPDG), mPtMin(ptMin), mPtMaxPhiPhi(ptMax), mPtMaxPhi(ptMaxPhi), mYMin(yMin), mYMax(yMax), mSignalInterval(signalInterval)
    {
        // 1. Define Custom Directly Injected Phi (PDG: 888888) with mass, width, and decay to kaons
        std::string createCustomPhi = std::to_string(mCustomPhiPDG) + ":new = custom_phi custom_phi 3 0 0 1.019461 0.004249 0.980 1.100 0.0";
        std::string customPhiMayDecay = std::to_string(mCustomPhiPDG) + ":mayDecay = on";
        std::string addPhiDecayKPlusKMinus = std::to_string(mCustomPhiPDG) + ":addChannel = 1 0.492 0 321 -321";

        // 2. Define Custom Signal Resonance (PDG: 999999) decay into standard Phis (333 333)
        std::string createReso = std::to_string(mResoPDG) + ":new = f2_Custom void 5 0 0 2.714 0.012 2.05 3.50 0.0";
        std::string resoMayDecay = std::to_string(mResoPDG) + ":mayDecay = on";
        std::string addResoDecay = std::to_string(mResoPDG) + ":addChannel = 1 1.0 0 333 333";

        // Helper lambda to load custom particle definitions across ALL Pythia engines
        auto applyCustomParticles = [&](Pythia8::Pythia &pythiaInst)
        {
            pythiaInst.readString(createCustomPhi);
            pythiaInst.readString(customPhiMayDecay);
            pythiaInst.readString(addPhiDecayKPlusKMinus);
            pythiaInst.readString(createReso);
            pythiaInst.readString(resoMayDecay);
            pythiaInst.readString(addResoDecay);
        };

        // 1: Apply particle definitions to mPythia, mPythiaGun, and pythiaObjectMinimumBias
        applyCustomParticles(mPythia);
        applyCustomParticles(mPythiaGun);

        mPythiaGun.readString("ProcessLevel:all off");
        mPythiaGun.readString("Random:setSeed = on");
        mPythiaGun.readString("Random:seed = " + std::to_string(1 + gRandom->Integer(900000000)));
        mPythiaGun.init();

        // 3. Initialize Minimum Bias Pythia Engine
        if (pythiaCfgMb.empty())
        {
            auto &param = o2::eventgen::GeneratorPythia8Param::Instance();
            pythiaCfgMb = param.config;
        }
        pythiaCfgMb = gSystem->ExpandPathName(pythiaCfgMb.c_str());

        if (!pythiaObjectMinimumBias.readFile(pythiaCfgMb))
        {
            std::cerr << "Fatal: Could not read MB configuration file: " << pythiaCfgMb << std::endl;
        }
        pythiaObjectMinimumBias.readString("Random:setSeed = on");
        pythiaObjectMinimumBias.readString("Random:seed = " + std::to_string(1 + gRandom->Integer(900000000)));

        applyCustomParticles(pythiaObjectMinimumBias);
        pythiaObjectMinimumBias.init();
    }

    Bool_t generateEvent() override
    {
        mEventCounter++;

        // 1. Generate Minimum Bias Background Event
        bool mbOK = false;
        while (!mbOK)
        {
            mbOK = pythiaObjectMinimumBias.next();
        }

        // 2: Copy MB event using exact pointer binding from generator_pythia8_LF_rapidity_width.C
        copyMinimumBiasEventForInjection();

        // 2. Clear Gun event container
        mPythiaGun.event.reset();

        // 3. Inject Signal Gun Particles into mPythiaGun
        if (mEventCounter % mSignalInterval == 0)
        {
            // Resonant signal -> Decays into 333 333 (Standard Phis)
            injectParticle(mResoPDG, 1, true);
        }
        else
        {
            // Directly injected uncorrelated Phi -> Uses Custom PDG 888888
            injectParticle(mCustomPhiPDG, 2, false);
        }

        // 4. Force Decay of injected particles using Pythia's Decayer
        mPythiaGun.moreDecays();
        mPythiaGun.next();

        // 3: Index Mapping during Event Merging
        int offset = mPythia.event.size();
        std::vector<int> indexMap(mPythiaGun.event.size(), 0);

        for (int i = 1; i < mPythiaGun.event.size(); ++i)
        {
            indexMap[i] = mPythia.event.size();
            Pythia8::Particle p = mPythiaGun.event[i];
            mPythia.event.append(p);
        }

        // Re-link mother and daughter index relationships accurately
        for (int i = 1; i < mPythiaGun.event.size(); ++i)
        {
            int newIdx = indexMap[i];
            Pythia8::Particle &p = mPythia.event[newIdx];

            int m1 = p.mother1();
            int m2 = p.mother2();
            int d1 = p.daughter1();
            int d2 = p.daughter2();

            p.mothers((m1 > 0 && m1 < (int)indexMap.size()) ? indexMap[m1] : 0,
                      (m2 > 0 && m2 < (int)indexMap.size()) ? indexMap[m2] : 0);

            p.daughters((d1 > 0 && d1 < (int)indexMap.size()) ? indexMap[d1] : 0,
                        (d2 > 0 && d2 < (int)indexMap.size()) ? indexMap[d2] : 0);
        }

        // 4: Restore Pythia particleData pointers for O2 exporter
        mPythia.event.restorePtrs();

        return true;
    }

private:
    void copyMinimumBiasEventForInjection()
    {
        mPythia.event = pythiaObjectMinimumBias.event;
        mPythia.event.init("Minimum-bias event with injected particles", &mPythia.particleData);
        mPythia.event.restorePtrs();
    }

    void injectParticle(int pdg, int nParticles, bool thermalPt)
    {
        const double phiMass = 1.019461;

        for (int i = 0; i < nParticles; ++i)
        {
            const double y = gRandom->Uniform(mYMin, mYMax);
            const double phi = gRandom->Uniform(0, TMath::TwoPi());

            double mass = 0.0;
            if (pdg == mResoPDG)
            {
                do
                {
                    mass = gRandom->BreitWigner(2.714, 0.012);
                } while (mass <= 2.0 * phiMass || mass < 2.05 || mass > 3.50);
            }
            else
            {
                mass = mPythiaGun.particleData.mSel(333); // Use standard phi mass for directly injected custom phi
            }

            double pt;
            if (thermalPt)
            {
                pt = gRandom->Uniform(mPtMin, mPtMaxPhiPhi);
            }
            else
            {
                pt = gRandom->Uniform(mPtMin, mPtMaxPhi);
            }

            const double px = pt * std::cos(phi);
            const double py = pt * std::sin(phi);
            const double mT = std::sqrt(mass * mass + pt * pt);
            const double pz = mT * std::sinh(y);
            const double et = mT * std::cosh(y);

            Pythia8::Particle particle;
            particle.id(pdg);
            particle.status(11);
            particle.m(mass);
            particle.px(px);
            particle.py(py);
            particle.pz(pz);
            particle.e(et);
            particle.xProd(0.);
            particle.yProd(0.);
            particle.zProd(0.);

            mPythiaGun.particleData.mayDecay(pdg, true);
            mPythiaGun.event.append(particle);
        }
    }

    int mEventCounter = 0;
    int mResoPDG;
    int mCustomPhiPDG;
    int mSignalInterval;
    float mPtMin, mPtMaxPhiPhi, mPtMaxPhi, mYMin, mYMax;

    Pythia8::Pythia mPythiaGun;
    Pythia8::Pythia pythiaObjectMinimumBias;
};

/// Entry point for o2-sim
FairGenerator *generatePhiResonanceGun(int resoPDG = 999999, int customPhiPDG = 888888, float ptMin = 0.0, float ptMax = 50.0, float ptMaxPhi = 100.0, float yMin = -1.0, float yMax = 1.0, std::string pythiaCfgMb = "", int signalInterval = 3)
{
    return new GeneratorPhiResonance(resoPDG, customPhiPDG, ptMin, ptMax, ptMaxPhi, yMin, yMax, pythiaCfgMb, signalInterval);
}