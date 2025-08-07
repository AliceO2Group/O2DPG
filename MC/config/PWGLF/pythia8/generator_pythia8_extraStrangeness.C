
#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TF1.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"

#include <map>
#include <unordered_set>

class GeneratorPythia8ExtraStrangeness : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8ExtraStrangeness() {
    genMinPt=0.0;
    genMaxPt=20.0;
    genminY=-1.0;
    genmaxY=1.0;
    genminEta=-1.0;
    genmaxEta=1.0;
    
    pdg=0;
    E=0;
    px=0;
    py=0;
    pz=0;
    p=0;
    y=0;
    eta=0;
    xProd=0;
    yProd=0;
    zProd=0;
    xProd=0.; yProd=0.; zProd=0.;
    
    fLVHelper = std::make_unique<TLorentzVector>();

    fSpectrumXi = std::make_unique<TF1>("fSpectrumXi", this, &GeneratorPythia8ExtraStrangeness::boltzPlusPower, 0., genMaxPt, 5, "GeneratorPythia8ExtraStrangeness", "boltzPlusPower");

    fSpectrumXi->FixParameter(0, 1.32171);
    fSpectrumXi->FixParameter(1, 4.84e-1);
    fSpectrumXi->FixParameter(2, 111.9);
    fSpectrumXi->FixParameter(3, -2.56511e+00);
    fSpectrumXi->FixParameter(4, 1.14011e-04);

    fSpectrumOm = std::make_unique<TF1>("fSpectrumOm", this, &GeneratorPythia8ExtraStrangeness::boltzPlusPower, 0., genMaxPt, 5, "GeneratorPythia8ExtraStrangeness", "boltzPlusPower");

    fSpectrumOm->FixParameter(0, 1.67245e+00);
    fSpectrumOm->FixParameter(1, 5.18174e-01);
    fSpectrumOm->FixParameter(2, 1.73747e+01);
    fSpectrumOm->FixParameter(3, -2.56681e+00);
    fSpectrumOm->FixParameter(4, 1.87513e-04);
  }
  
  Double_t y2eta(Double_t pt, Double_t mass, Double_t y){
    Double_t mt = TMath::Sqrt(mass * mass + pt * pt);
    return TMath::ASinH(mt / pt * TMath::SinH(y));
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
  
  //_________________________________________________________________________________
  /// generate uniform eta and uniform momentum
  void genSpectraMomentumEtaXi(double minP, double maxP, double minY, double maxY){
    // random generator
    std::unique_ptr<TRandom3> ranGenerator { new TRandom3() };
    ranGenerator->SetSeed(0);
    
    // generate transverse momentum
    const double gen_pT = fSpectrumXi->GetRandom(genMinPt,genMaxPt);
    
    //Actually could be something else without loss of generality but okay
    const double gen_phi = ranGenerator->Uniform(0,2*TMath::Pi());
    
    // sample flat in rapidity, calculate eta
    Double_t gen_Y=10, gen_eta=10;
    
    while( gen_eta>genmaxEta || gen_eta<genminEta ){
      gen_Y = ranGenerator->Uniform(minY,maxY);
      //(Double_t pt, Double_t mass, Double_t y)
      gen_eta = y2eta(gen_pT, m, gen_Y);
    }
    
    fLVHelper->SetPtEtaPhiM(gen_pT, gen_eta, gen_phi, m);
    set4momentum(fLVHelper->Px(),fLVHelper->Py(),fLVHelper->Pz());
  }
  
  //_________________________________________________________________________________
  /// generate uniform eta and uniform momentum
  void genSpectraMomentumEtaOm(double minP, double maxP, double minY, double maxY){
    // random generator
    std::unique_ptr<TRandom3> ranGenerator { new TRandom3() };
    ranGenerator->SetSeed(0);
    
    // generate transverse momentum
    const double gen_pT = fSpectrumOm->GetRandom(genMinPt,genMaxPt);
    
    //Actually could be something else without loss of generality but okay
    const double gen_phi = ranGenerator->Uniform(0,2*TMath::Pi());
    
    // sample flat in rapidity, calculate eta
    Double_t gen_Y=10, gen_eta=10;
    
    while( gen_eta>genmaxEta || gen_eta<genminEta ){
      gen_Y = ranGenerator->Uniform(minY,maxY);
      //(Double_t pt, Double_t mass, Double_t y)
      gen_eta = y2eta(gen_pT, m, gen_Y);
    }
    
    fLVHelper->SetPtEtaPhiM(gen_pT, gen_eta, gen_phi, m);
    set4momentum(fLVHelper->Px(),fLVHelper->Py(),fLVHelper->Pz());
  }
  
Double_t boltzPlusPower(const Double_t *x, const Double_t *p)
{
  // a plain parametrization. not meant to be physics worthy. 
  // adjusted to match preliminary 5 TeV shape. 

  Double_t pt = x[0];
  Double_t mass = p[0];
  Double_t mt = TMath::Sqrt(pt * pt + mass * mass);
  Double_t T = p[1];
  Double_t norm = p[2];
  
  Double_t lowptpart = mt * TMath::Exp(-mt / T);
  Double_t highptpart = p[4]*TMath::Power(x[0], p[3]);
  
  Double_t mixup = 1./(1.+TMath::Exp((x[0]-4.5)/.1));
  
  //return pt * norm * (mixup * mt * TMath::Exp(-mt / T) + (1.-mixup)*highptpart) ;
  return pt * norm * (mt * TMath::Exp(-mt / T) + (1.-mixup)*highptpart) ;
}

  //__________________________________________________________________
  Bool_t generateEvent() override {
    
    // Generate PYTHIA event
    Bool_t lPythiaOK = kFALSE;
    while (!lPythiaOK){
      lPythiaOK = mPythia.next();
      //if(TMath::Abs(mPythia.info.hiInfo->b()-8.5)>0.5) lPythiaOK = false; // select peripheral for flow
    }
    
    // characterise event
    Long_t nParticles = mPythia.event.size();
    Long_t nChargedParticlesAtMidRap = 0;
    Long_t nPionsAtMidRap = 0;
    for ( Long_t j=0; j < nParticles; j++ ) {
      Int_t pypid = mPythia.event[j].id();
      Float_t pyrap = mPythia.event[j].y();
      Float_t pyeta = mPythia.event[j].eta();

      // final only
      if (!mPythia.event[j].isFinal()) continue;
      
      if ( TMath::Abs(pyrap) < 0.5 && TMath::Abs(pypid)==211 ) nPionsAtMidRap++;
      if ( TMath::Abs(pyeta) < 0.5 && TMath::Abs(mPythia.event[j].charge())>1e-5 ) nChargedParticlesAtMidRap++;
    }
    
    // now we have the multiplicity
    
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    // XI ABUNDANCE FIX
//    FCN=0.35879 FROM MINOS     STATUS=SUCCESSFUL    126 CALLS         634 TOTAL
//                        EDM=3.7456e-09    STRATEGY= 1      ERROR MATRIX ACCURATE
//     EXT PARAMETER                                   STEP         FIRST
//     NO.   NAME      VALUE            ERROR          SIZE      DERIVATIVE
//      1  p0           4.74929e-03   3.29248e-04  -3.35914e-06   5.38225e+00
//      2  p1          -4.08255e-03   8.62587e-04  -2.02577e-05   2.45132e+00
//      3  p2           4.76660e+00   1.93593e+00   1.93593e+00   2.70369e-04
//   Info in <TCanvas::MakeDefCanvas>:  created default TCanvas with name c1
    //Adjust relative abundance of multi-strange particles by injecting some
    Double_t lExpectedXiToPion = TMath::Max(4.74929e-03 - 4.08255e-03*TMath::Exp(-nChargedParticlesAtMidRap/4.76660e+00) - 0.00211334,0.);
    Double_t lExpectedXi = 5.0*nPionsAtMidRap*lExpectedXiToPion; // extra rich, factor 5
    Int_t lXiYield = gRandom->Poisson(3*lExpectedXi); //factor 3: fix the rapidity acceptance
    m = 1.32171;
    pdg = 3312;
    cout<<"Adding extra xi: "<<lXiYield<<" (to reach average "<<Form("%.6f",lExpectedXi)<<" at this Nch = "<<nChargedParticlesAtMidRap<<", ratio: "<<Form("%.6f",lExpectedXiToPion)<<")"<<endl;
    for(Int_t ii=0; ii<lXiYield; ii++){
      pdg *= gRandom->Uniform()>0.5?+1:-1;
      xProd=0.0;
      yProd=0.0;
      zProd=0.0;
      genSpectraMomentumEtaXi(genMinPt,genMaxPt,genminY,genmaxY);
      Pythia8::Particle lAddedParticle = createParticle();
      mPythia.event.append(lAddedParticle);
      //lAddedParticles++;
    }
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    // OMEGA ABUNDANCE FIX
    //Adjust relative abundance of multi-strange particles by injecting some
    Double_t lExpectedOmegaToPion = TMath::Max(8.55057e-04 - 7.38732e-04*TMath::Exp(-nChargedParticlesAtMidRap/2.40545e+01) - 6.56785e-05,0.);
    Double_t lExpectedOmega = 30.0*nPionsAtMidRap*lExpectedOmegaToPion; // extra rich, factor 30 (omega -> rarer -> smaller Nch bias -> ok to enrich more)
    Int_t lOmegaYield = gRandom->Poisson(3*lExpectedOmega); //factor 3: fix the rapidity acceptance
    m = 1.67245;
    pdg = 3334;
    cout<<"Adding extra omegas: "<<lOmegaYield<<" (to reach average "<<Form("%.6f",lExpectedOmega)<<" at this Nch = "<<nChargedParticlesAtMidRap<<", ratio: "<<Form("%.6f",lExpectedOmegaToPion)<<")"<<endl;
    for(Int_t ii=0; ii<lOmegaYield; ii++){
      pdg *= gRandom->Uniform()>0.5?+1:-1;
      xProd=0.0;
      yProd=0.0;
      zProd=0.0;
      genSpectraMomentumEtaOm(genMinPt,genMaxPt,genminY,genmaxY);
      Pythia8::Particle lAddedParticle = createParticle();
      mPythia.event.append(lAddedParticle);
      //lAddedParticles++;
    }
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    
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
  
  std::unique_ptr<TLorentzVector> fLVHelper;
  std::unique_ptr<TF1> fSpectrumXi;
  std::unique_ptr<TF1> fSpectrumOm;
};

 FairGenerator *generator_extraStrangeness()
 {
  auto generator = new GeneratorPythia8ExtraStrangeness();
  gRandom->SetSeed(0);
  generator->readString("Random:setSeed = on");
  generator->readString("Random:seed =" + std::to_string(gRandom->Integer(900000000 - 2) + 1));
  return generator;
 }
