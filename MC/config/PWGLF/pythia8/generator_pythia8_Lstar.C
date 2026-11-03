#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TF1.h"
#include "TRandom3.h"
//#include "TParticlePDG.h"
//#include "TDatabasePDG.h"

#include <map>
#include <unordered_set>

class GeneratorPythia8ExtraStrangeness : public o2::eventgen::GeneratorPythia8
{
public:
  /// default constructor
  GeneratorPythia8ExtraStrangeness() = default;

  /// Constructor
  GeneratorPythia8ExtraStrangeness(int input_pdg, int inputTriggerRatio)
  {

    if (inputTriggerRatio <= 0) {
      throw std::invalid_argument("inputTriggerRatio must be positive");
    }

    LOG(info) << "Gap trigger ratio N = " << inputTriggerRatio << " events";
  

    mGeneratedEvents = 0;
    mTriggerRatio = inputTriggerRatio;

    genMinPt=0.0;
    genMaxPt=10.0;
    genminY=-1.0;
    genmaxY=1.0;
    genminEta=-2.5;
    genmaxEta=2.5;
    
    pdg=input_pdg;
    m = 0;
    E=0;
    px=0;
    py=0;
    pz=0;
    p=0;
    y=0;
    eta=0;
    xProd=0.; yProd=0.; zProd=0.;
    
    fLVHelper = std::make_unique<TLorentzVector>();
  }


  Double_t y2eta(Double_t pt, Double_t mass, Double_t y){
    Double_t mt = TMath::Sqrt(mass * mass + pt * pt);
    return TMath::ASinH(mt / pt * TMath::SinH(y));
  }
  

  /// set mass
  double sampleMass(int input_pdg)
  {
    auto& pd = mPythia.particleData;
    const double mass = pd.mWidth(input_pdg) > 0. ? pd.mSel(input_pdg) : pd.m0(input_pdg);
    return mass;
  }

  static double myLevyPt(double* pt, double* par)
  {
    const double lMass  = par[0];
    const double ldNdy  = par[1];
    const double lTemp  = par[2];
    const double lPower = par[3];

    const double lBigCoef = ((lPower-1)*(lPower-2)) / (lPower*lTemp*(lPower*lTemp+lMass*(lPower-2)));
    const double lInPower = 1 + (TMath::Sqrt(pt[0]*pt[0]+lMass*lMass)-lMass) / (lPower*lTemp);

    return ldNdy * pt[0] * lBigCoef * TMath::Power(lInPower, -lPower);
  }

  /// build a Levy-Tsallis pT spectrum for a particle of given mass
TF1* makeLevySpectrum(const char* name, double ptMin, double ptMax, double mass, double T, double n, double norm = 1.)
  {
    TF1* f = new TF1(name, myLevyPt, ptMin, ptMax, 4);
    f->SetParNames("mass", "norm", "T", "n");
    f->FixParameter(0, mass);   // mass [GeV/c^2]
    f->SetParameter(1, norm);   // normalization (irrelevant for GetRandom)
    f->SetParameter(2, T);      // slope parameter [GeV]
    f->SetParameter(3, n);      // power-law exponent
    f->SetNpx(1000);
    return f;
  }

  /// set 4-momentum
  void set4momentum(double input_px, double input_py, double input_pz){
    px = input_px;
    py = input_py;
    pz = input_pz;
    E  = sqrt( m*m+px*px+py*py+pz*pz );
    fourMomentum.px(px);
    fourMomentum.py(py);
    fourMomentum.pz(pz);
    fourMomentum.e(E);
    p   = sqrt( px*px+py*py+pz*pz );
    y   = 0.5*log( (E+pz)/(E-pz) );
    eta = 0.5*log( (p+pz)/(p-pz) );
  }
  

  //_________________________________________________________________________________
  /// generate uniform eta and uniform momentum
  void genSpectraMomentumEta(double minPt, double maxPt, double minY, double maxY){

    // generate transverse momentum
    //const double gen_pT = ranGenerator->Uniform(minPt, maxPt);
    const double gen_pT = fSpectra->GetRandom(minPt, maxPt, &mRandom);
    
    //Actually could be something else without loss of generality but okay
    const double gen_phi = mRandom.Uniform(0,2*TMath::Pi());
    
    // sample flat in rapidity, calculate eta
    Double_t gen_Y=10, gen_eta=10;
    
    while( gen_eta>genmaxEta || gen_eta<genminEta ){
      gen_Y = mRandom.Uniform(minY,maxY);
      gen_eta = y2eta(gen_pT, m, gen_Y);
    }
    
    fLVHelper->SetPtEtaPhiM(gen_pT, gen_eta, gen_phi, m);
    set4momentum(fLVHelper->Px(),fLVHelper->Py(),fLVHelper->Pz());
  }

  //__________________________________________________________________
  Pythia8::Particle createParticle(int id){
    //std::cout << "createParticle() mass " << m << " pdgCode " << pdg << std::endl;
    Pythia8::Particle myparticle;
    myparticle.id(id);
    myparticle.status(11);
    myparticle.px(px);
    myparticle.py(py);
    myparticle.pz(pz);
    myparticle.e(E);
    myparticle.m(m);
    myparticle.xProd(xProd);
    myparticle.yProd(yProd);
    myparticle.zProd(zProd);
    
    return myparticle;
  }

  
  //__________________________________________________________________
  // look for final-state (anti)Lambdas in the event; if there are any, remove one
  // (chosen at random) from the event record and return the Lambda id, otherwise return 0
  int removeLambda()
  {
    int kLambdaPdg = 3122;
    auto& event = mPythia.event;

    std::vector<int> candidates;
    for (int i = 0; i < event.size(); ++i) {
      bool isFromDecay = event[i].status() >= 91 && event[i].status() <= 99;
      bool isAcc = std::abs(event[i].y()) < genmaxY;

      if (event[i].idAbs() == kLambdaPdg && event[i].isFinal() && isAcc && !isFromDecay) {
        // not considering lambdas that are the first daughter in the event record.
        bool isEdge = false;
        for (int mom : event[i].motherList()) {
          if (i == event[mom].daughter1() || i == event[mom].daughter2()) isEdge = true;
        }

        if (!isEdge) {
          candidates.push_back(i);
        }
      }
    }
    if (candidates.empty()) {
      return 0;
    }

    const int idx = candidates[static_cast<int>(mRandom.Uniform(0,candidates.size()))];
    const int lambdaId = event[idx].id();

    // remove the entry and shift the indices of the others
    event.remove(idx, idx, true);

    return lambdaId;
  }

  //__________________________________________________________________
  Bool_t generateEvent() override {
    // Generate PYTHIA event
    
    if (!fSpectra) {
      fSpectra = makeLevySpectrum("fSpectra", genMinPt, genMaxPt, mPythia.particleData.m0(pdg), 0.3942, 9.943);
    }

    mPythia.event.reset();
    Bool_t lPythiaOK = kFALSE;

    mGeneratedEvents++;
    if (mGeneratedEvents % mTriggerRatio == 0) {
      int lambdaId = 0;

      // regenerate until the event contains a Lambda or an anti-Lambda, which is removed
      while (lambdaId == 0)
      {
        lPythiaOK = mPythia.next();
        if (lPythiaOK) {
          lambdaId = removeLambda();
        }
      }

      m = sampleMass(pdg);
      genSpectraMomentumEta(genMinPt, genMaxPt, genminY, genmaxY);

      // Lambda -> Lambda*, anti-Lambda -> anti-Lambda*
      const int sign = lambdaId > 0 ? 1 : -1;

      Pythia8::Particle particle = createParticle(sign*pdg);
      int idxL = mPythia.event.append(particle);
      mPythia.moreDecays(idxL);
    } else {
      while (!lPythiaOK){
        lPythiaOK = mPythia.next();
      }
    }
    return true;
  }

  
private:

  unsigned long long mGeneratedEvents;
  int mTriggerRatio;

  double genMinPt;      /// minimum 3-momentum for generated particles
  double genMaxPt;      /// maximum 3-momentum for generated particles
  double genminY;    /// minimum pseudorapidity for generated particles
  double genmaxY;    /// maximum pseudorapidity for generated particles
  double genminEta;
  double genmaxEta;
  
  Pythia8::Vec4   fourMomentum;  /// four-momentum (px,py,pz,E)
  //std::unique_ptr<o2::eventgen::FlowMapper> lutGen;
  
  double E;        /// energy: sqrt( m*m+px*px+py*py+pz*pz ) [GeV/c]
  double m;        /// particle mass [GeV/c^2]
  int    pdg;        /// particle pdg code
  double px;        /// x-component momentum [GeV/c]
  double py;        /// y-component momentum [GeV/c]
  double pz;        /// z-component momentum [GeV/c]
  double p;        /// momentum
  double y;        /// rapidity
  double eta;        /// pseudorapidity
  double xProd;      /// x-coordinate position production vertex [cm]
  double yProd;      /// y-coordinate position production vertex [cm]
  double zProd;      /// z-coordinate position production vertex [cm]
  
  TF1 *fSpectra = nullptr; /// TF1 to store more realistic shape of spectrum
  std::unique_ptr<TLorentzVector> fLVHelper;
  TRandom3 mRandom{0};
};

 FairGenerator *generator_Lstar(int inputTriggerRatio = 3)
 {
  auto myGen = new GeneratorPythia8ExtraStrangeness(3124, inputTriggerRatio);
  return myGen;
 }