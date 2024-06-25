R__LOAD_LIBRARY(libStarlib.so)
R__ADD_INCLUDE_PATH($STARlight_ROOT/include)

#include "randomgenerator.h"
#include "upcXevent.h"
#include "starlight.h"
#include "inputParameters.h"

//   usage: o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=GeneratorStarlight.C;GeneratorExternal.funcName=GeneratorStarlight("kCohJpsiToMu")'

namespace o2
{
namespace eventgen
{
class GeneratorStarlight_class : public Generator
{
 public:
   GeneratorStarlight_class(){};
  ~GeneratorStarlight_class() = default;
  void selectConfiguration(std::string val) { mSelectedConfiguration = val; };
  void setCollisionSystem(float energyCM, int beam1Z, int beam1A, int beam2Z, int beam2A) {eCM = energyCM; projZ=beam1Z; projA=beam1A; targZ=beam2Z; targA=beam2A;};
  bool setParameter(std::string line) {
  if (not mInputParameters.setParameter(line)){
	  std::cout << " --- [ERROR] cannot set parameter: " << line << std::endl;
      return false;
    }
	return true;
  }
  int getPdgMother(){return mPdgMother;}

  bool Init() override
  {
    Generator::Init();
	
  float beam1energy = TMath::Sqrt(Double_t(projZ)/projA*targA/targZ)*eCM/2;
  float beam2energy = TMath::Sqrt(Double_t(projA)/projZ*targZ/targA)*eCM/2;
  float gamma1  = beam1energy/0.938272;
  float gamma2  = beam2energy/0.938272;
  float rapMax = 4.1 + 0.5*(TMath::ACosH(gamma2)-TMath::ACosH(gamma1));
	  
  const struct SLConfig {
    const char* name;
    int       prod_mode;
    int       prod_pid;
    int       nwbins;
    float     wmin;
    float     wmax;
    float     dy;
	int		  pdg_mother;
	bool	  decay_EvtGen;
  } slConfig[] = {
    {"kTwoGammaToMuLow",     1,      13,  292,  0.4, 15.0, 0.01, -1, 0 }, // from 0.4 to 15 GeV
    {"kTwoGammaToElLow",     1,      11,  292,  0.4, 15.0, 0.01, -1, 0 }, // from 0.4 to 15 GeV
    {"kTwoGammaToMuMedium",  1,      13,  264,  1.8, 15.0, 0.01, -1, 0 }, // from 1.8 to 15 GeV
    {"kTwoGammaToElMedium",  1,      11,  264,  1.8, 15.0, 0.01, -1, 0 }, // from 1.8 to 15 GeV
    {"kTwoGammaToMuHigh",    1,      13,  220,  4.0, 15.0, 0.01, -1, 0 }, // from 4.0 to 15 GeV
    {"kTwoGammaToElHigh",    1,      11,  220,  4.0, 15.0, 0.01, -1, 0 }, // from 4.0 to 15 GeV
    {"kTwoGammaToRhoRho",    1,      33,   20, -1.0, -1.0, 0.01, -1, 0 }, //
    {"kTwoGammaToF2",        1,     225,   20, -1.0, -1.0, 0.01, -1, 0 }, //
    {"kCohRhoToPi",          3,     113, 1200, -1.0, -1.0, 0.02, 113, 0 }, //
    {"kCohRhoToElEl",        3,  113011, 1200, -1.0, -1.0, 0.02, 113, 0 }, //
    {"kCohRhoToMuMu",        3,  113013, 1200, -1.0, -1.0, 0.02, 113, 0 }, //
    {"kCohRhoToPiWithCont",  3,     913, 1200, -1.0, -1.0, 0.02, -1, 0 }, //
    {"kCohRhoToPiFlat",      3,     113,    1, -1.0,  2.5, 0.02, 113, 0 }, //
    {"kCohPhiToKa",          2,     333,   20, -1.0, -1.0, 0.01, 333, 0 }, //
    {"kDirectPhiToKaKa",     3,     933,   20, -1.0, -1.0, 0.01, 333, 0 }, // 
    {"kCohOmegaTo2Pi",       2,     223,   20, -1.0, -1.0, 0.01, 223, 0 }, //
    {"kCohOmegaTo3Pi",       2,     223,   20, -1.0, -1.0, 0.01, 223, 0 }, //
    {"kCohOmegaToPiPiPi",    2, 223211111, 20, -1.0, -1.0, 0.01, 333, 0 }, // 
    {"kCohJpsiToMu",         2,  443013,   20, -1.0, -1.0, 0.01, 443, 0 }, //
    {"kCohJpsiToEl",         2,  443011,   20, -1.0, -1.0, 0.01, 443, 0 }, //
    {"kCohJpsiToElRad",      2,  443011,   20, -1.0, -1.0, 0.01, 443, 1 }, //
    {"kCohJpsiToProton",     2, 4432212,   20, -1.0, -1.0, 0.01, 443, 0 }, //
    {"kCohPsi2sToMu",        2,  444013,   20, -1.0, -1.0, 0.01, 100443, 0 }, //
    {"kCohPsi2sToEl",        2,  444011,   20, -1.0, -1.0, 0.01, 100443, 0 }, //
    {"kCohPsi2sToMuPi",      2,  444013,   20, -1.0, -1.0, 0.01, 100443, 1 }, //
    {"kCohPsi2sToElPi",      2,  444011,   20, -1.0, -1.0, 0.01, 100443, 1 }, //
    {"kCohUpsilonToMu",      2,  553013,   20, -1.0, -1.0, 0.01, 553, 0 }, //
    {"kCohUpsilonToEl",      2,  553011,   20, -1.0, -1.0, 0.01, 553, 0 }, //
    {"kIncohRhoToPi",        4,     113, 1200, -1.0, -1.0, 0.02, 113, 0 }, //
    {"kIncohRhoToElEl",      4,  113011, 1200, -1.0, -1.0, 0.02, 113, 0 }, //
    {"kIncohRhoToMuMu",      4,  113013, 1200, -1.0, -1.0, 0.02, 113, 0 }, //
    {"kIncohRhoToPiWithCont",4,     913, 1200, -1.0, -1.0, 0.02, -1, 0 }, //
    {"kIncohRhoToPiFlat",    4,     113,    1, -1.0,  2.5, 0.02, 113, 0 }, //
    {"kIncohPhiToKa",        4,     333,   20, -1.0, -1.0, 0.01, 333, 0 }, //
    {"kIncohOmegaTo2Pi",     4,     223,   20, -1.0, -1.0, 0.01, 223, 0 }, //
    {"kIncohOmegaTo3Pi",     4,     223,   20, -1.0, -1.0, 0.01, 223, 0 }, //
    {"kIncohOmegaToPiPiPi",  4, 223211111, 20, -1.0, -1.0, 0.01, 223, 0 }, //
    {"kIncohJpsiToMu",       4,  443013,   20, -1.0, -1.0, 0.01, 443, 0 }, //
    {"kIncohJpsiToEl",       4,  443011,   20, -1.0, -1.0, 0.01, 443, 0 }, //
    {"kIncohJpsiToElRad",    4,  443011,   20, -1.0, -1.0, 0.01, 443, 1 }, //
    {"kIncohJpsiToProton",   4, 4432212,   20, -1.0, -1.0, 0.01, 443, 0 }, //
    {"kIncohJpsiToLLbar",    4, 4433122,   20, -1.0, -1.0, 0.01, 443, 0 }, //
    {"kIncohPsi2sToMu",      4,  444013,   20, -1.0, -1.0, 0.01, 100443, 0 }, //
    {"kIncohPsi2sToEl",      4,  444011,   20, -1.0, -1.0, 0.01, 100443, 0 }, //
    {"kIncohPsi2sToMuPi",    4,  444013,   20, -1.0, -1.0, 0.01, 100443, 1 }, //
    {"kIncohPsi2sToElPi",    4,  444011,   20, -1.0, -1.0, 0.01, 100443, 1 }, //
    {"kIncohUpsilonToMu",    4,  553013,   20, -1.0, -1.0, 0.01, 553, 0 }, //
    {"kIncohUpsilonToEl",    4,  553011,   20, -1.0, -1.0, 0.01, 553, 0 }, //	
	};

  const int nProcess = sizeof(slConfig)/sizeof(SLConfig);
  int idx = -1;
  for (int i=0; i<nProcess; ++i) {
    if (mSelectedConfiguration.compare(slConfig[i].name) == 0) {
      idx = i;
      break;
    }
  }
  
  if (idx == -1) {
    std::cout << "STARLIGHT process "<< mSelectedConfiguration <<" is not supported" << std::endl;
    return false;
  }
  
  mPdgMother = slConfig[idx].pdg_mother;
  mDecayEvtGen = slConfig[idx].decay_EvtGen;  
  
  uint random_seed;
  unsigned long long int random_value = 0; 
  ifstream urandom("/dev/urandom", ios::in|ios::binary);
  urandom.read(reinterpret_cast<char*>(&random_value), sizeof(random_seed));
  
  setParameter(Form("BEAM_1_Z     =    %3i    #Z of target",targZ));
  setParameter(Form("BEAM_1_A     =    %3i    #A of target",targA));
  setParameter(Form("BEAM_2_Z     =    %3i    #Z of projectile",projZ));
  setParameter(Form("BEAM_2_A     =    %3i    #A of projectile",projA));
  setParameter(Form("BEAM_1_GAMMA = %6.1f    #Gamma of the target",gamma1));
  setParameter(Form("BEAM_2_GAMMA = %6.1f    #Gamma of the projectile",gamma2));
  setParameter(Form("W_MAX        =   %.1f    #Max value of w",slConfig[idx].wmax));
  setParameter(Form("W_MIN        =   %.1f    #Min value of w",slConfig[idx].wmin));
  setParameter(Form("W_N_BINS     =    %3i    #Bins i w",slConfig[idx].nwbins));
  setParameter(Form("RAP_MAX      =   %.2f    #max y",rapMax));
  setParameter(Form("RAP_N_BINS   =   %.0f    #Bins i y",rapMax*2./slConfig[idx].dy));
  setParameter("CUT_PT       =    0    #Cut in pT? 0 = (no, 1 = yes)");
  setParameter("PT_MIN       =    0    #Minimum pT in GeV");
  setParameter("PT_MAX       =   10    #Maximum pT in GeV");
  setParameter("CUT_ETA      =    0    #Cut in pseudorapidity? (0 = no, 1 = yes)");
  setParameter("ETA_MIN      =   -5    #Minimum pseudorapidity");
  setParameter("ETA_MAX      =    5    #Maximum pseudorapidity");
  setParameter(Form("PROD_MODE    =    %i    #gg or gP switch (1 = 2-photon, 2 = coherent vector meson (narrow), 3 = coherent vector meson (wide), # 4 = incoherent vector meson, 5 = A+A DPMJet single, 6 = A+A DPMJet double, 7 = p+A DPMJet single, 8 = p+A Pythia single )",slConfig[idx].prod_mode));
  setParameter(Form("PROD_PID     =   %6i    #Channel of interest (not relevant for photonuclear processes)",slConfig[idx].prod_pid));
  setParameter(Form("RND_SEED     =    %i    #Random number seed", random_seed));
  setParameter("BREAKUP_MODE  =   5    #Controls the nuclear breakup");
  setParameter("INTERFERENCE  =   0    #Interference (0 = off, 1 = on)");
  setParameter("IF_STRENGTH   =   1.   #% of interfernce (0.0 - 0.1)");
  setParameter("INT_PT_MAX    =   0.24 #Maximum pt considered, when interference is turned on");
  setParameter("INT_PT_N_BINS = 120    #Number of pt bins when interference is turned on");
  setParameter("XSEC_METHOD   = 1      # Set to 0 to use old method for calculating gamma-gamma luminosity"); //CM
  setParameter("BSLOPE_DEFINITION = 0");   // using default slope
  setParameter("BSLOPE_VALUE      = 4.0"); // default slope value
  setParameter("PRINT_VM = 0"); // print cross sections and fluxes vs rapidity in stdout for VM photoproduction processes
  
  if (not mInputParameters.init()) {
      std::cout << "InitStarLight parameter initialization has failed" << std::endl;
      return false;
    } 
	
  mStarLight = new starlight;
  mStarLight->setInputParameters(&mInputParameters);
  mRandomGenerator.SetSeed(mInputParameters.randomSeed());
  mStarLight->setRandomGenerator(&mRandomGenerator); 
  return mStarLight->init(); 
  
  };
  
  bool generateEvent() override { 
  
    if (!mStarLight) {
    std::cout <<"GenerateEvent: StarLight class/object not properly constructed"<<std::endl;
    return false;
  }

  mEvent = mStarLight->produceEvent();
  // boost event to the experiment CM frame
  mEvent.boost(0.5*(TMath::ACosH(mInputParameters.beam1LorentzGamma()) - TMath::ACosH(mInputParameters.beam2LorentzGamma())));
  
  return true; 
 
  };

  // at importParticles we add particles to the output particle vector
  // according to the selected configuration
  bool importParticles() override
  {    
  int nVtx(0);
  float vtx(0), vty(0), vtz(0), vtt(0);
  const std::vector<vector3>* slVtx(mEvent.getVertices());
  if (slVtx == 0) { // not vertex assume 0,0,0,0;
    vtx = vty = vtz = vtt = 0.0;
  } else { // a vertex exits
    slVtx = mEvent.getVertices();
    nVtx = slVtx->size();
  } // end if
  
  const std::vector<starlightParticle>* slPartArr(mEvent.getParticles());
  const int npart(mEvent.getParticles()->size());
  
  if(mPdgMother != -1){ //Reconstruct mother particle for VM processes
  TLorentzVector lmoth;
  TLorentzVector ldaug;
  for(int ipart=0;ipart<npart;ipart++) {
    const starlightParticle* slPart(&(slPartArr->at(ipart)));
    ldaug.SetPxPyPzE(slPart->GetPx(), slPart->GetPy(), slPart->GetPz(), slPart->GetE());
	lmoth += ldaug;
   }
   TParticle particle(mPdgMother,
				   11,
				   -1,
				   -1,
				   1,
				   npart,
				   lmoth.Px(),
				   lmoth.Py(),
				   lmoth.Pz(),
				   lmoth.E(),
				   0,0,0,0);
	  //particle.Print();
	  mParticles.push_back(particle);
	  o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back(), 11);
  }
  if(!mDecayEvtGen){ // Don't import daughters in case of external decayer
  for(int ipart=0;ipart<npart;ipart++) {
    const starlightParticle* slPart(&(slPartArr->at(ipart)));
      if (nVtx < 1) { // No verticies
	vtx = vty = vtz = vtt = 0.0;
      } else {
	vtx = (slVtx->at((ipart < nVtx ? ipart : 0))).X();
	vty = (slVtx->at((ipart < nVtx ? ipart : 0))).Y();
	vtz = (slVtx->at((ipart < nVtx ? ipart : 0))).Z();
	vtt = 0.0; // no time given.
      } // end if
      TParticle particle(slPart->getPdgCode(),
				   1,
				   0,
				   -1,
				   slPart->getFirstDaughter(),
				   slPart->getLastDaughter(),
				   slPart->GetPx(),
				   slPart->GetPy(),
				   slPart->GetPz(),
				   slPart->GetE(),
				   vtx,vty,vtz,vtt);
	  //particle.Print();
	  mParticles.push_back(particle);
      o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back(), 1);
    }  
    }
  return true; 
  }
 
   private:
   starlight        *mStarLight = 0x0;     
   inputParameters  mInputParameters;  //   simulation input information.
   randomGenerator  mRandomGenerator;  //   STARLIGHT's own random generator
   upcXEvent        mEvent;            //  object holding STARlight simulated event.
   std::string mSelectedConfiguration = "";
   int mPdgMother = -1;
   bool mDecayEvtGen = 0;
   float eCM = 5020; //CMS energy
   int projA=208;	//Beam 
   int targA=208;
   int projZ=82;
   int targZ=82;
   
 };
 
} // namespace eventgen
} // namespace o2
 

FairGenerator*
  GeneratorStarlight(std::string configuration = "empty",float energyCM = 5020, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208)
{
  auto gen = new o2::eventgen::GeneratorStarlight_class();
  gen->selectConfiguration(configuration);
  gen->setCollisionSystem(energyCM, beam1Z, beam1A, beam2Z, beam2A);
  return gen;
}




