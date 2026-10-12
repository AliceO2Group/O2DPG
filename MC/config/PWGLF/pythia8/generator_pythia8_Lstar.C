
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
  GeneratorPythia8ExtraStrangeness(int input_pdg) 
  {
    genMinPt=0.0;
    genMaxPt=12.0;
    genminY=-1.5;
    genmaxY=1.5;
    genminEta=-1.5;
    genmaxEta=1.5;
    
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

    randomizePDGsign = false;

    fSpectra = makeLevySpectrum("fSpectra", genMinPt, genMaxPt, mPythia.particleData.m0(input_pdg), 0.30, 7.);
  }

  /// randomize the PDG code sign of core particle
  void setRandomizePDGsign() { randomizePDGsign = true; }

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
    // random generator
    std::unique_ptr<TRandom3> ranGenerator { new TRandom3() };
    ranGenerator->SetSeed(0);
    
    // generate transverse momentum
    //const double gen_pT = ranGenerator->Uniform(minPt, maxPt);
    const double gen_pT = fSpectra->GetRandom(minPt,maxPt);
    
    //Actually could be something else without loss of generality but okay
    const double gen_phi = ranGenerator->Uniform(0,2*TMath::Pi());
    
    // sample flat in rapidity, calculate eta
    Double_t gen_Y=10, gen_eta=10;
    
    while( gen_eta>genmaxEta || gen_eta<genminEta ){
      gen_Y = ranGenerator->Uniform(minY,maxY);
      gen_eta = y2eta(gen_pT, m, gen_Y);
    }
    
    fLVHelper->SetPtEtaPhiM(gen_pT, gen_eta, gen_phi, m);
    set4momentum(fLVHelper->Px(),fLVHelper->Py(),fLVHelper->Pz());
  }

  //__________________________________________________________________
  Pythia8::Particle createParticle(){
    //std::cout << "createParticle() mass " << m << " pdgCode " << pdg << std::endl;
    Pythia8::Particle myparticle;
    myparticle.id(pdg);
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
  int randomizeSign()
  {
    std::unique_ptr<TRandom3> gen_random{new TRandom3(0)};
    const float n = gen_random->Uniform(-1, 1);

    return n / abs(n);
  }
  
  //__________________________________________________________________
  Bool_t generateEvent() override {
    // Generate PYTHIA event
    
    mPythia.event.reset();

    /// go to next Pythia event
    Bool_t lPythiaOK = kFALSE;
    while (!lPythiaOK){
      lPythiaOK = mPythia.next();
    }

    /// reset event
    //mPythia.event.reset();

    /// create and append the desired particle
    m = sampleMass(pdg);
    genSpectraMomentumEta(genMinPt, genMaxPt, genminY, genmaxY);

    if (randomizePDGsign)
      pdg *= randomizeSign();

    Pythia8::Particle particle = createParticle();
    mPythia.event.append(particle);
    mPythia.moreDecays();

    return true;
  }
  
private:
  
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

  bool randomizePDGsign; /// bool to randomize the PDG code of the core particle
  
  TF1 *fSpectra = nullptr; /// TF1 to store more realistic shape of spectrum
  std::unique_ptr<TLorentzVector> fLVHelper;
};

 FairGenerator *generator_Lstar()
 {
  auto myGen = new GeneratorPythia8ExtraStrangeness(3124);
  myGen->setRandomizePDGsign(); // randomization of PDG switched on
  return myGen;
 }