#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "Pythia8/Pythia.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"

#include <map>
#include <unordered_set>
#include <string>
//#include <utility>	// for std::pair

using namespace Pythia8;
#endif

class GeneratorPythia8Gunpp : public o2::eventgen::GeneratorPythia8{
public:
  /// default constructor
  GeneratorPythia8Gunpp() = default;
  
  /// constructor
  GeneratorPythia8Gunpp(int input_pdg){
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
    
    fLVHelper = new TLorentzVector();
    
    if( input_pdg!=0 ) m = getMass(input_pdg);
    if( input_pdg==0 ) m = 1.0;
    
    //fSpectra = new TF1("fPtDist",myLevyPt,0.0,10,3);
    fSpectra = new TF1("fSpectra",this ,&GeneratorPythia8Gunpp::myLevyPt, 0.0,20,4, "GeneratorPythia8Gunpp","myLevyPt");
    fSpectra ->SetNpx( 1000 );
    
    fSpectra->SetParameter(3, m);
//    FCN=15.8379 FROM MINOS     STATUS=SUCCESSFUL    178 CALLS         585 TOTAL
//                        EDM=9.01697e-09    STRATEGY= 1      ERROR MATRIX ACCURATE
//     EXT PARAMETER                                   STEP         FIRST
//     NO.   NAME      VALUE            ERROR          SIZE      DERIVATIVE
//      1  p0           1.26147e+02   8.41042e+00  -8.50770e-02  -1.07709e-04
//      2  p1           1.09727e+00   1.90660e-01   4.06859e-03  -1.92045e-02
//      3  p2           7.63330e+00   4.45207e+00   4.45207e+00   6.13882e-05
    
    //Default: OmegaCCC parameters, cause we're bold
    fSpectra->SetParameter(0, 1.26147e+02);
    fSpectra->SetParameter(1, 1.09727e+00);
    fSpectra->SetParameter(2, 7.63330e+00);
    
    if(input_pdg == 4432){
//      FCN=42.0607 FROM MINOS     STATUS=SUCCESSFUL     46 CALLS         320 TOTAL
//                          EDM=7.15202e-08    STRATEGY= 1      ERROR MATRIX ACCURATE
//       EXT PARAMETER                                   STEP         FIRST
//       NO.   NAME      VALUE            ERROR          SIZE      DERIVATIVE
//        1  p0           1.33563e+04   8.17396e+01  -2.03998e-02  -4.89388e-06
//        2  p1           1.03858e+00   1.31862e-02   7.73307e-04  -8.47151e-02
//        3  p2           1.21413e+01   6.20997e-01   6.20997e-01  -9.73367e-04
      fSpectra->SetParameter(0, 1.33563e+04);
      fSpectra->SetParameter(1, 1.03858e+00);
      fSpectra->SetParameter(2, 1.21413e+01);
    }
    if(input_pdg == 4422){
//      FCN=171.16 FROM MINOS     STATUS=SUCCESSFUL     40 CALLS         273 TOTAL
//                          EDM=1.03965e-07    STRATEGY= 1      ERROR MATRIX ACCURATE
//       EXT PARAMETER                                   STEP         FIRST
//       NO.   NAME      VALUE            ERROR          SIZE      DERIVATIVE
//        1  p0           7.13200e+04   1.88918e+02  -3.46221e-02  -1.08268e-07
//        2  p1           1.02063e+00   5.68532e-03   1.16706e-04  -8.96155e-03
//        3  p2           1.04043e+01   1.95790e-01   1.95790e-01   4.39759e-04
      fSpectra->SetParameter(0, 7.13200e+04);
      fSpectra->SetParameter(1, 1.02063e+00);
      fSpectra->SetParameter(2, 1.04043e+01);
    }
    
    if(input_pdg == 4232){
//    FCN=2950.22 FROM MINOS     STATUS=SUCCESSFUL     40 CALLS         290 TOTAL
//                        EDM=1.43216e-07    STRATEGY= 1      ERROR MATRIX ACCURATE
//     EXT PARAMETER                                   STEP         FIRST
//     NO.   NAME      VALUE            ERROR          SIZE      DERIVATIVE
//      1  p0           6.95382e+04   8.34455e+01  -6.76782e-03  -7.12877e-09
//      2  p1           5.21608e-01   1.34221e-03   6.80074e-06  -8.00314e-04
//      3  p2           6.54815e+00   3.09274e-02   3.09274e-02   4.20673e-02
      fSpectra->SetParameter(0, 6.95382e+04);
      fSpectra->SetParameter(1, 5.21608e-01);
      fSpectra->SetParameter(2, 6.54815e+00);
    }
    
    furtherPrim={};
    keys_furtherPrim={};

    cout << "Initalizing extra PYTHIA object " << endl;

    // Read settings from external file.
    std::string O2DPG_ROOT(getenv("O2DPG_ROOT"));
    std::string infile = O2DPG_ROOT + "/MC/config/ALICE3/pythia8/generator/pythia8_pp.cmnd";
    pythiaObject.readFile(infile);

    // Set seed to job id
    char* alien_proc_id = getenv("ALIEN_PROC_ID");
    uint64_t seedFull;
    uint64_t seed = 0;
    if (alien_proc_id != NULL) {
      seedFull = static_cast<uint64_t>(atol(alien_proc_id));
      for(int ii=0; ii<29; ii++) // there might be a cleaner way but this will work
        seed |= ((seedFull) & (static_cast<uint64_t>(1) << static_cast<uint64_t>(ii)));
      LOG(info) << "Value of ALIEN_PROC_ID: " << seedFull <<" truncated to 0-28 bits: "<<seed<<endl;
    } else {
      LOG(info) << "Unable to retrieve ALIEN_PROC_ID";
      LOG(info) << "Setting seed to 0 (random)";
      seed = 0;
    }
    pythiaObject.readString("Random:seed = "+std::to_string(static_cast<int>(seed)));
    pythiaObject.init();
    
    cout << "Done." << endl;

  }
  
  ///  Destructor
  ~GeneratorPythia8Gunpp() = default;
  
  /// set PDG code
  void setPDG(int input_pdg){pdg=input_pdg;}
  
  /// randomize the PDG code sign of core particle
  void setRandomizePDGsign(){randomizePDGsign=true;}
  
  Double_t myLevyPt(const Double_t *pt, const Double_t *par)
  {
    //Levy Fit Function
    Double_t lMass  = par[3];
    Double_t ldNdy  = par[0];
    Double_t lTemp = par[1];
    Double_t lPower = par[2];

    Double_t lBigCoef = ((lPower-1)*(lPower-2)) / (lPower*lTemp*(lPower*lTemp+lMass*(lPower-2)));
    Double_t lInPower = 1 + (TMath::Sqrt(pt[0]*pt[0]+lMass*lMass)-lMass) / (lPower*lTemp);

    return ldNdy * pt[0] * lBigCoef * TMath::Power(lInPower,(-1)*lPower);
  }

  //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  
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
    //Override database if needed, please
    if( input_pdg==4444 ) mass = 4.797; //OmegaCCC
    if( input_pdg==4432 ) mass = 3.746; //OmegaCC
    if( input_pdg==4422) mass = 3.621; //XiCC
    if( input_pdg==4232) mass = 2.46793; //XiC+
    return mass;
  }
  
  //_________________________________________________________________________________
  /// generate uniform eta and uniform momentum
  void genUniformMomentumEta(double minP, double maxP, double minY, double maxY){
    // Warning: this generator samples randomly in p and not in pT. Care is advised

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
    // phi: random uniform, X, Y conform
    const double pT = sqrt(gen_p * gen_p - gen_pz * gen_pz);
    double phi = ranGenerator->Uniform(0., 2.0f*TMath::Pi());
    const double gen_px = pT*TMath::Cos(phi);
    const double gen_py = pT*TMath::Sin(phi);

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
      if ( TMath::Abs(pyeta) > 2.0 ) continue;
      
      //final only
      if (!pythiaObject.event[j].isFinal()) continue;
      
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
  
  bool randomizePDGsign;	/// bool to randomize the PDG code of the core particle
  
  TF1 *fSpectra; /// TF1 to store more realistic shape of spectrum
  
  TLorentzVector *fLVHelper;
  
  Pythia8::Pythia pythiaObject; ///Generate a full event if requested to do  so
  
  //bool   addFurtherPion;	/// bool to attach an additional primary pion
  std::map<int,int> furtherPrim;				/// key: PDG code; value: how many further primaries of this species to be added
  std::unordered_set<int> keys_furtherPrim;	/// keys of the above map (NB: only unique elements allowed!)
};

//The Omega Family
FairGenerator* generateNativeOmegaCCC(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gunpp(4444));
}

FairGenerator* generateNativeOmegaCC(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gunpp(4432));
}

FairGenerator* generateNativeOmegaC(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gunpp(4332));
}

FairGenerator* generateNativeOmega(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gunpp(3334));
}

//The Xi Family
FairGenerator* generateNativeXiCC(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gunpp(4422));
}

FairGenerator* generateNativeXiC(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gunpp(4232));
}

FairGenerator* generateNativeXi(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gunpp(3312));
}

//Use this for minimum-bias
FairGenerator* generatePYTHIA(){
  return reinterpret_cast<FairGenerator*>(new GeneratorPythia8Gunpp(211));
}
