/// generator_phi_resonance.C
#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Generators/GeneratorPythia8Param.h"
#include "Pythia8/Pythia.h"
#include "TRandom3.h"
#include "TMath.h"
// #include "TF1.h"
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
#endif

// Double_t FuncLavy(Double_t *x, Double_t *par)
// {

//     Double_t p = (par[0] - 1) * (par[0] - 2) * par[1] * x[0] / (((pow((1 + (((sqrt((par[2] * par[2]) + (x[0] * x[0]))) - par[2]) / (par[0] * par[3]))), par[0]) * (par[0] * par[3] * ((par[0] * par[3]) + (par[2] * (par[0] - 2)))))));
//     return (p);
// }

class GeneratorPhiResonance : public o2::eventgen::GeneratorPythia8
{
public:
    GeneratorPhiResonance(int resoPDG = 999999,
                          float ptMin = 0.0, float ptMax = 50.0,
                          float yMin = -1.0, float yMax = 1.0,
                          std::string pythiaCfgMb = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/pythia8_inel_136tev.cfg",
                          int signalInterval = 3)
        : GeneratorPythia8(), mResoPDG(resoPDG), mPtMin(ptMin), mPtMaxPhiPhi(ptMax), mYMin(yMin), mYMax(yMax), mSignalInterval(signalInterval)
    {
        // 1. Initialize Gun Pythia object & define custom resonance
        // # id::all = name antiName spinType chargeType colType m0 mWidth mMin mMax tau0
        std::string createReso = std::to_string(mResoPDG) + ":new = f2_Custom void 5 0 0 2.714 0.012 2.05 3.50 0.0";
        mPythiaGun.readString(createReso);
        mPythiaGun.readString(std::to_string(mResoPDG) + ":mayDecay = on");
        // id:addChannel = onMode bRatio meMode product1 product2, (onMode = 1: allow decay, bRatio = branching ratio, meMode = matrix element mode where 0 is isotropic decay)
        std::string addDecay = std::to_string(mResoPDG) + ":addChannel = 1 1.0 0 333 333";
        mPythiaGun.readString(addDecay);

        mPythiaGun.readString("ProcessLevel:all off");
        mPythiaGun.readString("Random:setSeed = on");
        mPythiaGun.readString("Random:seed = " + std::to_string(1 + gRandom->Integer(900000000)));
        mPythiaGun.init();

        // 2. Initialize Minimum Bias Pythia Engine
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

        // Add custom particle definition to MB instance so particle table matches
        pythiaObjectMinimumBias.readString(createReso);
        pythiaObjectMinimumBias.readString(std::to_string(mResoPDG) + ":mayDecay = on");
        pythiaObjectMinimumBias.readString(addDecay);

        pythiaObjectMinimumBias.init();

        // // Thermal pT distribution for phi-phi resonance
        // mThermal = new TF1("mThermal", "x*sqrt(x*x+[0]*[0])*exp(-sqrt(x*x+[0]*[0])/[1])", mPtMin, mPtMaxPhiPhi);

        // // Lévy-Tsallis pT distribution for direct phi
        // mLevyTsallis = new TF1("mLevyTsallis", FuncLavy, mPtMin, 100.0, 4);

        // mLevyTsallis->SetParameters(
        //     7.60279,   // n
        //     0.0374237, // dN/dy
        //     1.01946,   // mass
        //     0.338379   // T
        // );
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

        // Copy MB event into mPythia
        mPythia.event = pythiaObjectMinimumBias.event;

        // 2. Clear Gun event container
        mPythiaGun.event.reset();

        // 3. Inject Signal Gun Particles into mPythiaGun
        if (mEventCounter % mSignalInterval == 0)
        {
            // Theramal distribution
            injectParticle(mResoPDG, 1, true);
        }
        else
        {
            // From published
            injectParticle(333, 2, false);
        }

        // 4. Force Decay of injected particles using Pythia's Decayer
        for (int i = 1; i < mPythiaGun.event.size(); ++i)
        {
            if (mPythiaGun.event[i].status() > 0)
            { // Active injected particles
                mPythiaGun.particleData.mayDecay(mPythiaGun.event[i].id(), true);
                mPythiaGun.moreDecays();
            }
        }

        // 5. Merge mPythiaGun event into mPythia.event
        int offset = mPythia.event.size();

        for (int i = 1; i < mPythiaGun.event.size(); ++i)
        { // Skip system particle 0
            Pythia8::Particle p = mPythiaGun.event[i];

            // Adjust history indices accurately
            int mother1 = (p.mother1() > 0) ? p.mother1() + offset - 1 : p.mother1();
            int mother2 = (p.mother2() > 0) ? p.mother2() + offset - 1 : p.mother2();
            int daughter1 = (p.daughter1() > 0) ? p.daughter1() + offset - 1 : p.daughter1();
            int daughter2 = (p.daughter2() > 0) ? p.daughter2() + offset - 1 : p.daughter2();

            p.mothers(mother1, mother2);
            p.daughters(daughter1, daughter2);

            mPythia.event.append(p);
        }

        // 6. CRITICAL: Restore Pythia particleData pointers for O2 exporter
        mPythia.event.restorePtrs();

        // 7. Invoke base generator hooks to sync O2 event record
        // return GeneratorPythia8::generateEvent();
        return true; // Skip base generator processing to avoid overwriting injected particles
    }

private:
    void injectParticle(int pdg, int nParticles, bool thermalPt)
    {
        const double phiMass = 1.019461;

        for (int i = 0; i < nParticles; ++i)
        {
            // const double pt = gRandom->Uniform(mPtMin, mPtMaxPhiPhi);
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
                mass = mPythiaGun.particleData.mSel(pdg);
            }

            double pt;

            if (thermalPt)
            {
                // const double T = 0.160;

                // mThermal->SetParameter(0, mass);
                // mThermal->SetParameter(1, T);

                // pt = mThermal->GetRandom();

                pt = gRandom->Uniform(mPtMin, mPtMaxPhiPhi); // Falling back to flat pT due to low statistics in high pT
            }
            else
            {
                // pt = mLevyTsallis->GetRandom();
                pt = gRandom->Uniform(mPtMin, 100.0); // Falling back to flat pT due to low statistics in high pT
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

            mPythiaGun.event.append(particle);
        }
    }

    int mEventCounter = 0;
    int mResoPDG;
    int mSignalInterval;
    float mPtMin, mPtMaxPhiPhi, mYMin, mYMax;

    Pythia8::Pythia mPythiaGun;
    Pythia8::Pythia pythiaObjectMinimumBias;

    // TF1 *mThermal;
    // TF1 *mLevyTsallis;
};

/// Entry point for o2-sim
FairGenerator *generatePhiResonanceGun(int resoPDG = 999999, float ptMin = 0.0, float ptMax = 50.0, float yMin = -1.0, float yMax = 1.0, std::string pythiaCfgMb = "", int signalInterval = 3)
{
    return new GeneratorPhiResonance(resoPDG, ptMin, ptMax, yMin, yMax, pythiaCfgMb, signalInterval);
}