R__LOAD_LIBRARY(EvtGen)
R__ADD_INCLUDE_PATH($EVTGEN_ROOT/include)

#include "EvtGenBase/EvtStdHep.hh"
#include "EvtGen/EvtGen.hh"
#include "EvtGenBase/EvtParticle.hh"
#include "EvtGenBase/EvtPDL.hh"
#include "EvtGenBase/EvtParticleFactory.hh"
#include "EvtGenExternal/EvtExternalGenList.hh"
#include "EvtGenBase/EvtAbsRadCorr.hh"
#include "EvtGenBase/EvtRandom.hh"
#include "EvtGenBase/EvtReport.hh"
#include "EvtGenExternal/EvtExternalGenList.hh"
#include "EvtTRandomEngine.hh"

enum DecayModeEvt { kEvtAll = 0,
                    kEvtBJpsiDiElectron,
                    kEvtBJpsi,
                    kEvtBJpsiDiMuon,
                    kEvtBPsiDiElectron,
                    kEvtBPsiDiMuon,
                    kEvtBPsiAndJpsiDiElectron,
                    kEvtBPsiAndJpsiDiMuon,
                    kEvtBSemiElectronic,
                    kEvtHadronicD,
                    kEvtHadronicDWithout4Bodies,
                    kEvtChiToJpsiGammaToElectronElectron,
                    kEvtChiToJpsiGammaToMuonMuon,
                    kEvtSemiElectronic,
                    kEvtBSemiMuonic,
                    kEvtSemiMuonic,
                    kEvtDiElectron,
                    kEvtDiMuon,
                    kEvtBPsiPrimeDiMuon,
                    kEvtBPsiPrimeDiElectron,
                    kEvtJpsiDiMuon,
                    kEvtPsiPrimeJpsiDiElectron,
                    kEvtPhiKK,
                    kEvtOmega,
                    kEvtLambda,
                    kEvtHardMuons,
                    kEvtElectronEM,
                    kEvtDiElectronEM,
                    kEvtGammaEM,
                    kEvtBtoPsi2SToJpsiPiPi,
                    kEvtBeautyUpgrade };

namespace o2
{
namespace eventgen
{

template <typename T>
class GeneratorEvtGen : public T
{

 public:
  GeneratorEvtGen() : T(){};
  ~GeneratorEvtGen() = default;

  // overriden methods
  Bool_t Init() override { return T::Init() && InitEvtGen(); };
  // particles imported vie GeneratorTGenerator::importParticles will be flagged to be tracked automatically
  // if their HepMC status is 1; everything else must be flagged explcitly as done below.
  Bool_t importParticles() override { return T::importParticles() && makeEvtGenDecays(); };

  // external setters
  void AddPdg(int pdg, int pos) { mPdgString.AddAt(pdg, pos); };
  void SetSizePdg(int size) { mPdgString.Set(size); };
  void PrintDebug(bool deg = kTRUE) { mDebug = deg; };
  void SetDecayTable(TString decTab) { mDecayTablePath = decTab; };
  void SetForceDecay(DecayModeEvt forceDec) { mDecayMode = forceDec; };
  void SetPolarization(Int_t polar) { mPolarization = polar; };

 protected:
  // Initialize Evtgen
  Bool_t InitEvtGen()
  {

    if (mEvtGen)
      return kTRUE;
    std::cout << "EVTGEN INITIALIZATION" << std::endl;
    mEvtstdhep = new EvtStdHep();

    mEng = new EvtTRandomEngine(); // the default seed of gRandom is 0

    EvtRandom::setRandomEngine(mEng);

    char* decayTablePath = gSystem->ExpandPathName("$EVTGEN_ROOT/share/EvtGen/DECAY.DEC"); // default decay table
    char* particleTablePath = gSystem->ExpandPathName("$EVTGEN_ROOT/share/EvtGen/evt.pdl");     // particle table
    std::list<EvtDecayBase*> extraModels;

    EvtExternalGenList genList;
    EvtAbsRadCorr* fRadCorrEngine = genList.getPhotosModel();
    extraModels = genList.getListOfModels();

    mEvtGen = new EvtGen(decayTablePath, particleTablePath, mEng, fRadCorrEngine, &extraModels);
    ForceDecay();
    if (mDecayTablePath.Contains("DEC"))
      mEvtGen->readUDecay(mDecayTablePath.Data()); // user decay table
    return kTRUE;
  };

  // Decay particles using EvtGen and push products on std::vector mParticles
  Bool_t makeEvtGenDecays()
  {
    auto nparticles = T::mParticles.size();
    for (Int_t iparticle = 0; iparticle < nparticles; ++iparticle) {
      auto particle = (TParticle)T::mParticles.at(iparticle);
      if (checkPdg(particle.GetPdgCode())) {
        if (mDebug)
          std::cout << "particles in the array (before decay): PDG " << particle.GetPdgCode() << " STATUS " << particle.GetStatusCode() << " position in the array" << iparticle << " First daughter" << particle.GetFirstDaughter() << " Last daughter " << particle.GetLastDaughter() << std::endl;
        TLorentzVector* momentum = new TLorentzVector();
        momentum->SetPxPyPzE(particle.Px(), particle.Py(), particle.Pz(), particle.Energy());
        DecayEvtGen(particle.GetPdgCode(), momentum, mPolarization);
        if (!ImportParticlesEvtGen(iparticle)) {
          std::cout << "Attention: Import Particles failed" << std::endl;
          return kFALSE;
        }
        if (mDebug)
          std::cout << "particles in the array (after decay): PDG " << particle.GetPdgCode() << " STATUS " << particle.GetStatusCode() << " position in the array" << iparticle << " First daughter" << particle.GetFirstDaughter() << " Last daughter " << particle.GetLastDaughter() << std::endl;
      }
    }
    return kTRUE;
  }

  // decay particle
  void DecayEvtGen(Int_t ipart, TLorentzVector* p, Int_t alpha)
  {
    //
    // Decay a particle
    // input: pdg code and momentum of the particle to be decayed
    // all informations about decay products are stored in mEvtstdhep
    //
    // for particles with spin 1 (e.g. jpsi) is possible to set
    // the polarization status (fully transversal alpha=1 / longitudinal alpha=-1)
    // through spin density matrix
    //
    EvtId IPART = EvtPDL::evtIdFromStdHep(ipart);
    EvtVector4R p_init(p->E(), p->Px(), p->Py(), p->Pz());
    EvtParticle* froot_part = EvtParticleFactory::particleFactory(IPART, p_init);

    if (TMath::Abs(alpha) == 1) {

      // check if particle has spin 1 (i.e. 3 states)
      if (froot_part->getSpinStates() != 3) {
        std::cout << "Error: Polarization settings available for spin 1 particles" << std::endl;
        return;
      }

      EvtSpinDensity rho;
      // transversal
      if (alpha == 1) {
        rho.setDiag(3);
        rho.set(1, 1, EvtComplex(0.0, 0.0)); // eps00 = 0, eps++ = 1, eps-- = 1
      } else {
        // longitudinal
        rho.setDiag(3);
        rho.set(0, 0, EvtComplex(0.0, 0.0)); // eps++ = 0
        rho.set(2, 2, EvtComplex(0.0, 0.0)); // eps-- = 0
      }

      froot_part->setSpinDensityForwardHelicityBasis(rho, p->Phi(), p->Theta(), 0);
    } // close polarization settings

    mEvtGen->generateDecay(froot_part);
    mEvtstdhep->init();
    froot_part->makeStdHep(*mEvtstdhep);
    if (mDebug)
      froot_part->printTree(); // to print the decay chain
    froot_part->deleteTree();
    return;
  }

  Bool_t ImportParticlesEvtGen(Int_t indexMother)
  {
    //
    // Input: index of mother particle in the vector of generated particles (mParticles)
    // return kTRUE if the size of mParticles is updated
    // Put all the informations about the decay products in mParticles
    //

    int j;
    int istat;
    int partnum;
    double px, py, pz, e;
    double x, y, z, t;
    EvtVector4R p4, x4;
    Int_t originalSize = T::mParticles.size();
    Int_t npart = mEvtstdhep->getNPart();
    // 0 -> mother particle
    T::mParticles[indexMother].SetFirstDaughter(mEvtstdhep->getFirstDaughter(0) + T::mParticles.size() - 1);
    T::mParticles[indexMother].SetLastDaughter(mEvtstdhep->getLastDaughter(0) + T::mParticles.size() - 1);
    // set another HepMC code and switch off transport
    mcutils::MCGenHelper::encodeParticleStatusAndTracking(T::mParticles[indexMother], 11, 0, false);
    if (mDebug)
      std::cout << "index mother " << indexMother << " first daughter " << mEvtstdhep->getFirstDaughter(0) + T::mParticles.size() - 1 << " last daughter " << mEvtstdhep->getLastDaughter(0) + T::mParticles.size() - 1 << std::endl;
    for (int i = 1; i < mEvtstdhep->getNPart(); i++) {
      int jmotherfirst = mEvtstdhep->getFirstMother(i) > 0 ? mEvtstdhep->getFirstMother(i) + originalSize - 1 : mEvtstdhep->getFirstMother(i);
      int jmotherlast = mEvtstdhep->getLastMother(i) > 0 ? mEvtstdhep->getLastMother(i) + originalSize - 1 : mEvtstdhep->getLastMother(i);
      int jdaugfirst = mEvtstdhep->getFirstDaughter(i) > 0 ? mEvtstdhep->getFirstDaughter(i) + originalSize - 1 : mEvtstdhep->getFirstDaughter(i);
      int jdauglast = mEvtstdhep->getLastDaughter(i) > 0 ? mEvtstdhep->getLastDaughter(i) + originalSize - 1 : mEvtstdhep->getLastDaughter(i);

      if (jmotherfirst == 0)
        jmotherfirst = indexMother;
      if (jmotherlast == 0)
        jmotherlast = indexMother;

      partnum = mEvtstdhep->getStdHepID(i);

      // verify if all particles of decay chain are in the TDatabasePDG
      TParticlePDG* partPDG = TDatabasePDG::Instance()->GetParticle(partnum);
      if (!partPDG) {
        std::cout << "Particle code non known in TDatabasePDG - set pdg = 89" << std::endl;
        partnum = 89; // internal use for unspecified resonance data
      }

      istat = mEvtstdhep->getIStat(i);

      if (istat != 1 && istat != 2)
        std::cout << "ImportParticles: Attention unknown status code!" << std::endl;
      if (istat == 2)
        istat = 11; // status decayed

      p4 = mEvtstdhep->getP4(i);
      x4 = mEvtstdhep->getX4(i);
      px = p4.get(1);
      py = p4.get(2);
      pz = p4.get(3);
      e = p4.get(0);
      const Float_t kconvT = 0.01 / 2.999792458e8; // cm/c to seconds conversion
      const Float_t kconvL = 1.;                   // dummy conversion
      // shift time / position
      x = x4.get(1) * kconvL + T::mParticles[indexMother].Vx(); //[cm]
      y = x4.get(2) * kconvL + T::mParticles[indexMother].Vy(); //[cm]
      z = x4.get(3) * kconvL + T::mParticles[indexMother].Vz(); //[cm]
      t = x4.get(0) * kconvT + T::mParticles[indexMother].T();  //[s]

      T::mParticles.push_back(TParticle(partnum, istat, jmotherfirst, -1, jdaugfirst, jdauglast, px, py, pz, e, x, y, z, t));
      // make sure status codes are properly encoded and enable transport if HepMC status ==1
      mcutils::MCGenHelper::encodeParticleStatusAndTracking(T::mParticles.back(), istat == 1);
      ////
      if (mDebug)
        std::cout << "   -> PDG " << partnum << " STATUS " << istat << " position in the array" << T::mParticles.size() - 1 << " mother " << jmotherfirst << " First daughter" << jdaugfirst << " Last daughter " << jdauglast << std::endl;
    }
    if (mDebug)
      std::cout << "actual size " << T::mParticles.size() << " original size " << originalSize << std::endl;
    return (T::mParticles.size() > originalSize) ? kTRUE : kFALSE;
  }

  bool checkPdg(int pdgPart)
  {
    for (int ij = 0; ij < mPdgString.GetSize(); ij++) {
      if (TMath::Abs(TMath::Abs(pdgPart) - mPdgString.At(ij)) < 1.e-06)
        return kTRUE;
    }
    return kFALSE;
  };

  void ForceDecay()
  {
    //
    // Intupt: none - Output: none
    // Set the decay mode to decay particles: for each case is read a
    // different decay table. case kAll read the default decay table only
    //
    DecayModeEvt decay = mDecayMode;
    TString pathO2 = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/EvtGen/DecayTablesEvtgen");
    switch (decay) {
      case kEvtAll: // particles decayed "naturally" according to $ALICE_ROOT/TEvtGen/EvtGen/DECAY.DEC
        break;
      case kEvtBJpsiDiElectron:
        SetDecayTable(Form("%s/BTOJPSITOELE.DEC", pathO2.Data()));
        break;
      case kEvtBJpsi:
        SetDecayTable(Form("%s/BTOJPSI.DEC", pathO2.Data()));
        break;
      case kEvtBJpsiDiMuon:
        SetDecayTable(Form("%s/BTOJPSITOMU.DEC", pathO2.Data()));
        break;
      case kEvtBPsiDiElectron:
        SetDecayTable(Form("%s/BTOPSITOELE.DEC", pathO2.Data()));
        break;
      case kEvtBPsiDiMuon:
        SetDecayTable(Form("%s/BTOPSITOMU.DEC", pathO2.Data()));
        break;
      case kEvtBPsiAndJpsiDiElectron:
        SetDecayTable(Form("%s/BTOPSIJPSITODIELECTRON.DEC", pathO2.Data()));
        break;
      case kEvtBPsiAndJpsiDiMuon:
        SetDecayTable(Form("%s/BTOPSIJPSITODIMUON.DEC", pathO2.Data()));
        break;
      case kEvtBSemiElectronic:
        SetDecayTable(Form("%s/BTOELE.DEC", pathO2.Data()));
        break;
      case kEvtHadronicD:
        SetDecayTable(Form("%s/HADRONICD.DEC", pathO2.Data()));
        break;
      case kEvtHadronicDWithout4Bodies:
        SetDecayTable(Form("%s/HADRONICDWITHOUT4BODIES.DEC", pathO2.Data()));
        break;
      case kEvtChiToJpsiGammaToElectronElectron:
        SetDecayTable(Form("%s/CHICTOJPSITOELE.DEC", pathO2.Data()));
        break;
      case kEvtChiToJpsiGammaToMuonMuon:
        SetDecayTable(Form("%s/CHICTOJPSITOMUON.DEC", pathO2.Data()));
        break;
      case kEvtSemiElectronic:
        SetDecayTable(Form("%s/BANDCTOELE.DEC", pathO2.Data()));
        break;
      case kEvtBSemiMuonic:
        SetDecayTable(Form("%s/BTOMU.DEC", pathO2.Data()));
        break;
      case kEvtSemiMuonic:
        SetDecayTable(Form("%s/BANDCTOMU.DEC", pathO2.Data()));
        break;
      case kEvtDiElectron:
        SetDecayTable(Form("%s/DIELECTRON.DEC", pathO2.Data()));
        break;
      case kEvtDiMuon:
        SetDecayTable(Form("%s/DIMUON.DEC", pathO2.Data()));
        break;
      case kEvtBPsiPrimeDiMuon:
        SetDecayTable(Form("%s/BTOPSIPRIMETODIMUON.DEC", pathO2.Data()));
        break;
      case kEvtBPsiPrimeDiElectron:
        SetDecayTable(Form("%s/BTOPSIPRIMETODIELECTRON.DEC", pathO2.Data()));
        break;
      case kEvtJpsiDiMuon:
        SetDecayTable(Form("%s/JPSIDIMUON.DEC", pathO2.Data()));
        break;
      case kEvtPsiPrimeJpsiDiElectron:
        SetDecayTable(Form("%s/PSIPRIMETOJPSITOMU.DEC", pathO2.Data()));
        break;
      case kEvtPhiKK:
        SetDecayTable(Form("%s/PHITOK.DEC", pathO2.Data()));
        break;
      case kEvtOmega:
        SetDecayTable(Form("%s/OMEGATOLAMBDAK.DEC", pathO2.Data()));
        break;
      case kEvtLambda:
        SetDecayTable(Form("%s/LAMBDATOPROTPI.DEC", pathO2.Data()));
        break;
      case kEvtHardMuons:
        SetDecayTable(Form("%s/HARDMUONS.DEC", pathO2.Data()));
        break;
      case kEvtElectronEM:
        SetDecayTable(Form("%s/ELECTRONEM.DEC", pathO2.Data()));
        break;
      case kEvtDiElectronEM:
        SetDecayTable(Form("%s/DIELECTRONEM.DEC", pathO2.Data()));
        break;
      case kEvtGammaEM:
        SetDecayTable(Form("%s/GAMMAEM.DEC", pathO2.Data()));
        break;
      case kEvtBeautyUpgrade:
        SetDecayTable(Form("%s/BEAUTYUPGRADE.DEC", pathO2.Data()));
        break;
      case kEvtBtoPsi2SToJpsiPiPi:
        SetDecayTable(Form("%s/BTOPSITOJPSIPIPI.DEC", pathO2.Data()));
        break;
    }
    return;
  };

  /// evtgen pointers
  EvtGen* mEvtGen = 0x0;
  EvtStdHep* mEvtstdhep = 0x0;
  EvtTRandomEngine* mEng = 0;
  // pdg particles to be decayed
  TArrayI mPdgString;
  bool mDebug = kFALSE;
  TString mDecayTablePath;
  DecayModeEvt mDecayMode = kEvtAll;
  Int_t mPolarization = -999;
};

} // namespace eventgen
} // namespace o2
