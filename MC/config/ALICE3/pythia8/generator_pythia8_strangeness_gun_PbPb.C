#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"

#include <map>
#include <unordered_set>
//#include <utility>	// for std::pair

using namespace Pythia8;
#endif
class GeneratorPythia8Gun : public o2::eventgen::GeneratorPythia8{
public:
  /// default constructor
  GeneratorPythia8Gun() = default;
  
  /// constructor
  GeneratorPythia8Gun(int input_pdg){
    genMinPt=0.0;
    genMaxPt=20.0;
    genminY=-1.5;
    genmaxY=1.5;
    genminEta=-1.5;
    genmaxEta=1.5;
    
    UEOverSampling = 20;
    genEventCountUse = 2000; //start at large number: regen
    
    pdg = input_pdg;
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
    //addFurtherPion=false;
    
    randomizePDGsign=false;
    
    //fSpectra = new TF1("fPtDist",myLevyPt,0.0,10,3);
    fSpectra = STAR_BlastWave("fSpectra",  m, 20);
    fSpectra ->SetNpx( 1000 );
    fSpectraXi = STAR_BlastWave("fSpectraXi",  1.32171, 20);
    fSpectraXi ->SetNpx( 1000 );
    fSpectraOm = STAR_BlastWave("fSpectraOm",  1.67245, 20);
    fSpectraOm ->SetNpx( 1000 );
    
    fSpectra->SetParameter(0, m);   //mass: automatic!
    fSpectra->SetParameter(1,0.6615);   //beta-max
    fSpectra->SetParameter(2,0.0905);   //T
    fSpectra->SetParameter(3,0.7355);   //n
    fSpectra->SetParameter(4,1000);   //norm (not relevant)
    
    fSpectraXi->SetParameter(0,1.32171);   //beta-max
    fSpectraXi->SetParameter(1,0.6615);   //beta-max
    fSpectraXi->SetParameter(2,0.0905);   //T
    fSpectraXi->SetParameter(3,0.7355);   //n
    fSpectraXi->SetParameter(4,1000);   //norm (not relevant)
    
    fSpectraOm->SetParameter(0,1.67245);   //beta-max
    fSpectraOm->SetParameter(1,0.6615);   //beta-max
    fSpectraOm->SetParameter(2,0.0905);   //T
    fSpectraOm->SetParameter(3,0.7355);   //n
    fSpectraOm->SetParameter(4,1000);   //norm (not relevant)
    
    fLVHelper = new TLorentzVector();
    
    if( input_pdg!=0 ) m = getMass(input_pdg);
    if( input_pdg==4444 ) m = 4.797; 
    if( input_pdg==0 ) m = 1.0; 
    furtherPrim={};
    keys_furtherPrim={};
    cout<<"Initalizing extra PYTHIA object"<<endl;
    // Read settings from external file.
    std::string O2DPG_ROOT(getenv("O2DPG_MC_CONFIG_ROOT"));
    std::string infile = O2DPG_ROOT + "/MC/config/ALICE3/pythia8/generator/pythia8_hi.cmnd";
    pythiaObject.readFile(infile);
    //pythiaObject.readFile("pythia8_hi.cmnd");
    //pythiaObject.readFile("pp13.cmnd");
    pythiaObject.init();
    cout << "Done." << endl;

  }
  
  ///  Destructor
  ~GeneratorPythia8Gun() = default;
  
  /// set PDG code
  void setPDG(int input_pdg){pdg=input_pdg;}
  
  /// randomize the PDG code sign of core particle
  void setRandomizePDGsign(){randomizePDGsign=true;}
  
  Double_t myLevyPt(const Double_t *pt, const Double_t *par)
  {
    //Levy Fit Function
    Double_t lMass  = 4.797; //pion Mass
    Double_t ldNdy  = par[0];
    Double_t lTemp = par[1];
    Double_t lPower = par[2];

    Double_t lBigCoef = ((lPower-1)*(lPower-2)) / (lPower*lTemp*(lPower*lTemp+lMass*(lPower-2)));
    Double_t lInPower = 1 + (TMath::Sqrt(pt[0]*pt[0]+lMass*lMass)-lMass) / (lPower*lTemp);

    return ldNdy * pt[0] * lBigCoef * TMath::Power(lInPower,(-1)*lPower);
  }
  
  
  Double_t STAR_BlastWave_Func(const Double_t *x, const Double_t *p) {
    /* dN/dpt */
    
    Double_t pt = x[0];
    Double_t mass = p[0];
    Double_t mt = TMath::Sqrt(pt * pt + mass * mass);
    Double_t beta_max = p[1];
    Double_t temp = p[2];
    Double_t n = p[3];
    Double_t norm = p[4];
    
    Double_t integral = 0;
    
    if(TMath::Abs(mass-1.32171)<0.002){
      if (!fIntegrandXi)
        fIntegrandXi = new TF1("fIntegrandXi", this, &GeneratorPythia8Gun::STAR_BlastWave_Integrand_Improved, 0., 1., 5, "GeneratorPythia8Gun", "STAR_BlastWave_Integrand_Improved");
      fIntegrandXi->SetParameters(mt, pt, beta_max, temp, n);
      
      integral = fIntegrandXi->Integral(0., 1.);
    }
    if(TMath::Abs(mass-1.67245)<0.002){
      if (!fIntegrandOm)
        fIntegrandOm = new TF1("fIntegrandOm", this, &GeneratorPythia8Gun::STAR_BlastWave_Integrand_Improved, 0., 1., 5, "GeneratorPythia8Gun", "STAR_BlastWave_Integrand_Improved");
      fIntegrandOm->SetParameters(mt, pt, beta_max, temp, n);
      
      integral = fIntegrandOm->Integral(0., 1.);
    }
    if(TMath::Abs(mass-1.67245)>0.002&&TMath::Abs(mass-1.32171)>0.002){
      if (!fIntegrand)
        fIntegrand = new TF1("fIntegrand", this, &GeneratorPythia8Gun::STAR_BlastWave_Integrand_Improved, 0., 1., 5, "GeneratorPythia8Gun", "STAR_BlastWave_Integrand_Improved");
      fIntegrand->SetParameters(mt, pt, beta_max, temp, n);
      
      integral = fIntegrand->Integral(0., 1.);
    }
    return norm * pt * integral;
  }
  
  //___________________________________________________________________
  
  Double_t STAR_BlastWave_Integrand_Improved(const Double_t *x, const Double_t *p) {
      
      /*
       x[0] -> r (radius)
       p[0] -> mT (transverse mass)
       p[1] -> pT (transverse momentum)
       p[2] -> beta_max (surface velocity)
       p[3] -> T (freezout temperature)
       p[4] -> n (velocity profile)
       */
      
      Double_t r = x[0];
      Double_t mt = p[0];
      Double_t pt = p[1];
      Double_t beta_max = p[2];
      Double_t temp_1 = 1. / p[3];
      Double_t n = p[4];
      
      Double_t beta = beta_max * TMath::Power(r, n);
      Double_t rho = TMath::ATanH(beta);
      Double_t argI0 = pt * TMath::SinH(rho) * temp_1;
      Double_t argK1 = mt * TMath::CosH(rho) * temp_1;
      //  if (argI0 > 100 || argI0 < -100)
      //    printf("r=%f, pt=%f, beta_max=%f, temp=%f, n=%f, mt=%f, beta=%f, rho=%f, argI0=%f, argK1=%f\n", r, pt, beta_max, 1. / temp_1, n, mt, beta, rho, argI0, argK1);
      return r * mt * TMath::BesselI0(argI0) * TMath::BesselK1(argK1);
      
  }
  
  //___________________________________________________________________

  TF1 *STAR_BlastWave(const Char_t *name, Double_t mass,Float_t upperlim, Double_t beta_max = 0.9, Double_t temp = 0.1, Double_t n = 1., Double_t norm = 1.e6) {
    
      //new TF1("fSpectra",this ,&GeneratorPythia8GunPbPb::myLevyPt, 0.0,20,3, "GeneratorPythia8GunPbPb","myLevyPt");
      TF1 *fBlastWave = new TF1(name, this, &GeneratorPythia8Gun::STAR_BlastWave_Func, 0., upperlim, 5, "GeneratorPythia8Gun", "STAR_BlastWave_Func");
      fBlastWave->SetParameters(mass, beta_max, temp, n, norm);
      fBlastWave->SetParNames("mass", "beta_max", "T", "n", "norm");
      fBlastWave->FixParameter(0, mass);
      fBlastWave->SetParLimits(1, 0.1, 0.9); // don't touch :) adding some 99 youu get floating point exception
      fBlastWave->SetParLimits(2, 0.03,1.);//0.05, 1.);  // no negative values!! for the following as well
      fBlastWave->SetParLimits(3, 0.25,4.5); // was 2.5  // omega-->at limit even moving it to 4.5 but yield same
      return fBlastWave;
  }
  
  Double_t y2eta(Double_t pt, Double_t mass, Double_t y){
    Double_t mt = TMath::Sqrt(mass * mass + pt * pt);
    return TMath::ASinH(mt / pt * TMath::SinH(y));
  }
  
  /// set mass
  void setMass(int input_m){m=input_m;}
  
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
    
    ////std::cout << "##### Particle #####" << std::endl;
    ////std::cout << " - PDG code: " << pdg << std::endl;
    ////std::cout << " - mass: "     << m   << std::endl;
    ////std::cout << " - (px,py,pz): (" << px << "," << py << "," << pz << ")" << std::endl;
    ////std::cout << " - momentum: " << p << std::endl;
    ////std::cout << " - energy: " << E << std::endl;
    ////std::cout << " - rapidity: " << y << std::endl;
    ////std::cout << " - pseudorapidity: " << eta << std::endl;
    ////std::cout << " - production vertex: (" << xProd << "," << yProd << "," << zProd << ")" << std::endl;
  }
  
  /// set 3-momentum
  void setMomentum(double input_p){p=input_p;}
  
  /// set x,y,z of production vertex
  void setProdVtx(double input_xProd, double input_yProd, double input_zProd){xProd=input_xProd; yProd=input_xProd; zProd=input_zProd;}
  
  /// setter to add further primary particles to the event
  void setAddFurtherPrimaries(const int pdgCode, const int howMany){
    /// check if this species has been already added
    const int map_counts = furtherPrim.count(pdgCode);
    if(map_counts==1){	// species already present
      const int howMany_already = furtherPrim[pdgCode];
      std::cout << "BEWARE: " << howMany_already << " particles of species " << pdgCode << " already required.";
      std::cout << " Ignoring the command setAddFurtherPrimaries(" << pdgCode << "," << howMany << ")" << std::endl;
      return;
    }
    /// add particles, if not yet present
    furtherPrim[pdgCode] = howMany;
    keys_furtherPrim.insert(pdgCode);
  }
  
  /// set add a further primary pion
  //void setAddFurtherPion(){addFurtherPion=true;}
  
  /// get mass from TParticlePDG
  double getMass(int input_pdg){
    double mass = 0;
    if(TDatabasePDG::Instance()){
      TParticlePDG* particle = TDatabasePDG::Instance()->GetParticle(input_pdg);
      if(particle)	mass = particle->Mass();
      else			std::cout << "===> particle mass equal to 0" << std::endl;
    }
    return mass;
  }
  
  //_________________________________________________________________________________
  /// generate uniform eta and uniform momentum
  void genUniformMomentumEta(double minP, double maxP, double minY, double maxY){
    // random generator
    std::unique_ptr<TRandom3> ranGenerator { new TRandom3() };
    ranGenerator->SetSeed(0);
    
    // momentum
    const double gen_p = ranGenerator->Uniform(minP,maxP);
    // eta
    const double gen_eta = ranGenerator->Uniform(minY,maxY);
    // z-component momentum from eta
    const double cosTheta = ( exp(2*gen_eta)-1 ) / ( exp(2*gen_eta)+1 );	// starting from eta = -ln(tan(theta/2)) = 1/2*ln( (1+cos(theta))/(1-cos(theta)) ) ---> NB: valid for cos(theta)!=1
    const double gen_pz = gen_p*cosTheta;
    // y-component: random uniform
    const double maxVal = sqrt( gen_p*gen_p-gen_pz*gen_pz );
    double sign_py = ranGenerator->Uniform(0,1);
    sign_py = (sign_py>0.5)?1.:-1.;
    const double gen_py = ranGenerator->Uniform(0.,maxVal)*sign_py;
    // x-component momentum
    double sign_px = ranGenerator->Uniform(0,1);
    sign_px = (sign_px>0.5)?1.:-1.;
    const double gen_px = sqrt( gen_p*gen_p-gen_pz*gen_pz-gen_py*gen_py )*sign_px;
    
    set4momentum(gen_px,gen_py,gen_pz);
  }
  
  //_________________________________________________________________________________
  /// generate uniform eta and uniform momentum
  void genSpectraMomentumEta(double minP, double maxP, double minY, double maxY){
    // random generator
    std::unique_ptr<TRandom3> ranGenerator { new TRandom3() };
    ranGenerator->SetSeed(0);
    
    // generate transverse momentum
    const double gen_pT = fSpectra->GetRandom(minP,maxP);
    
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
  void genSpectraMomentumEtaXi(double minP, double maxP, double minY, double maxY){
    // random generator
    std::unique_ptr<TRandom3> ranGenerator { new TRandom3() };
    ranGenerator->SetSeed(0);
    
    // generate transverse momentum
    const double gen_pT = fSpectraXi->GetRandom(minP,maxP);
    
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
    const double gen_pT = fSpectraOm->GetRandom(minP,maxP);
    
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
  
protected:
  
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
  int randomizeSign(){
    
    std::unique_ptr<TRandom3> gen_random {new TRandom3(0)};
    const float n = gen_random->Uniform(-1,1);
    
    return n/abs(n);
  }
  
  //__________________________________________________________________
  Bool_t generateEvent() override {
    
    double original_m = m;
    int original_pdg  = pdg;
    
    /// reset event
    mPythia.event.reset();
    
    if(original_pdg!=211){
      for(Int_t ii=0; ii<15; ii++){
        xProd=0.0;
        yProd=0.0;
        zProd=0.0;
        genSpectraMomentumEta(genMinPt,genMaxPt,genminY,genmaxY);
        Pythia8::Particle lAddedParticle = createParticle();
        mPythia.event.append(lAddedParticle);
        lAddedParticles++;
      }
    }
    
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    Bool_t lPythiaOK = kFALSE;
    while (!lPythiaOK){
      lPythiaOK = pythiaObject.next();
      //Select rough central events, please, disregard
      //if( pythiaObject.info.hiInfo->b() > 6) lPythiaOK = kFALSE; //regenerate, please
    }
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    // use event
    Long_t nParticles = pythiaObject.event.size();
    Long_t nChargedParticlesAtMidRap = 0;
    Long_t nPionsAtMidRap = 0;
    lAddedParticles = 0;
    for ( Long_t j=0; j < nParticles; j++ ) {
      Int_t pypid = pythiaObject.event[j].id();
      Float_t pypx = pythiaObject.event[j].px();
      Float_t pypy = pythiaObject.event[j].py();
      Float_t pypz = pythiaObject.event[j].pz();
      Float_t pypt = pythiaObject.event[j].pT();
      Float_t pyrap = pythiaObject.event[j].y();
      Float_t pyeta = pythiaObject.event[j].eta();
      Int_t pystate = pythiaObject.event[j].status();
      //if(TMath::Abs(state > 89)) {continue;}
      Float_t pyenergy = pythiaObject.event[j].e();
      Int_t pycharge = pythiaObject.event[j].charge();
           
      //Per-species loop: skip outside of mid-rapidity, please
      if ( TMath::Abs(pyeta) > 4.0 ) continue; //only within ALICE 3 acceptance 
      
      //final only
      if (!pythiaObject.event[j].isFinal()) continue;
      
      if ( TMath::Abs(pyeta) < 0.5 ){
        if ( TMath::Abs(pythiaObject.event[j].charge())>1e-5 ) nChargedParticlesAtMidRap++;
        if ( TMath::Abs(pypid)==211 ) nPionsAtMidRap++;
      }
      
      pdg = pypid;
      px = pypx;
      py = pypy;
      pz = pypz;
      E = pyenergy;
      m = pythiaObject.event[j].m();
      xProd = pythiaObject.event[j].xProd();
      yProd = pythiaObject.event[j].yProd();
      zProd = pythiaObject.event[j].zProd();
      
      Pythia8::Particle lAddedParticle = createParticle();
      mPythia.event.append(lAddedParticle);
      lAddedParticles++;
    }
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        
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
    Double_t lExpectedXi = nPionsAtMidRap*lExpectedXiToPion;
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
      lAddedParticles++;
    }
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    // OMEGA ABUNDANCE FIX
    //Adjust relative abundance of multi-strange particles by injecting some
    Double_t lExpectedOmegaToPion = TMath::Max(8.55057e-04 - 7.38732e-04*TMath::Exp(-nChargedParticlesAtMidRap/2.40545e+01) - 6.56785e-05,0.);
    Double_t lExpectedOmega = nPionsAtMidRap*lExpectedOmegaToPion;
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
      lAddedParticles++;
    }
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    
    //Revert back or else there'll be trouble next time!
    m = original_m;
    pdg = original_pdg;
    
    /// go to next Pythia event
    mPythia.next();
    
    return true;
  }
  
private:
  
  double genMinPt;			/// minimum 3-momentum for generated particles
  double genMaxPt;			/// maximum 3-momentum for generated particles
  double genminY;		/// minimum pseudorapidity for generated particles
  double genmaxY;		/// maximum pseudorapidity for generated particles
  double genminEta;
  double genmaxEta;
  int UEOverSampling; //number of times to repeat underlying event
  int genEventCountUse;
  
  Pythia8::Vec4   fourMomentum;	/// four-momentum (px,py,pz,E)
  double E;				/// energy: sqrt( m*m+px*px+py*py+pz*pz ) [GeV/c]
  double m;				/// particle mass [GeV/c^2]
  int    pdg;				/// particle pdg code
  double px;				/// x-component momentum [GeV/c]
  double py;				/// y-component momentum [GeV/c]
  double pz;				/// z-component momentum [GeV/c]
  double p;				/// momentum
  double y;				/// rapidity
  double eta;				/// pseudorapidity
  double xProd;			/// x-coordinate position production vertex [cm]
  double yProd;			/// y-coordinate position production vertex [cm]
  double zProd;			/// z-coordinate position production vertex [cm]
  
  //Max number: max number of particles to be added
  long lAddedParticles;
  float ue_E[5000];
  float ue_m[5000];
  float ue_px[5000];
  float ue_py[5000];
  float ue_pz[5000];
  float ue_xProd[5000];
  float ue_yProd[5000];
  float ue_zProd[5000];
  int ue_pdg[5000];
  
  bool randomizePDGsign;	/// bool to randomize the PDG code of the core particle
  
  TF1 *fSpectra; /// TF1 to store more realistic shape of spectrum
  TF1 *fSpectraXi; /// TF1 to store more realistic shape of spectrum
  TF1 *fSpectraOm; /// TF1 to store more realistic shape of spectrum
  
  //BW integrand
  TF1 *fIntegrand = NULL;
  TF1 *fIntegrandXi = NULL;
  TF1 *fIntegrandOm = NULL;
  
  TLorentzVector *fLVHelper;
  
  Pythia8::Pythia pythiaObject; ///Generate a full event if requested to do  so
  
  //bool   addFurtherPion;	/// bool to attach an additional primary pion
  std::map<int,int> furtherPrim;				/// key: PDG code; value: how many further primaries of this species to be added
  std::unordered_set<int> keys_furtherPrim;	/// keys of the above map (NB: only unique elements allowed!)
};

FairGenerator* generateNativeOmegaCCC(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gun(4444));
}

FairGenerator* generateNativeOmegaCC(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gun(4432));
}

FairGenerator* generateNativeOmegaC(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gun(4332));
}

FairGenerator* generateNativeOmega(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gun(3334));
}

FairGenerator* generatePYTHIA(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gun(211));
}
