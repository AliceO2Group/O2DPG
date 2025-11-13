R__LOAD_LIBRARY(libDPMJET.so)
R__LOAD_LIBRARY(libDpmJetLib.so)
R__LOAD_LIBRARY(libStarlib.so)
R__ADD_INCLUDE_PATH($STARlight_ROOT/include)

#include "randomgenerator.h"
#include "upcXevent.h"
#include "upcevent.h"
#include "starlight.h"
#include "inputParameters.h"

//   usage: o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=GeneratorStarlight.C;GeneratorExternal.funcName=GeneratorStarlight("kCohJpsiToMu")'

unsigned int generateRandomSeed() {
    // Use high-resolution clock for time-based seed
    auto timeNow = std::chrono::high_resolution_clock::now();
    auto timeSeed = static_cast<unsigned int>(timeNow.time_since_epoch().count());

    // Random device for system entropy
    std::random_device rd;

    // Add process ID and thread ID for additional entropy
    unsigned int pid = static_cast<unsigned int>(getpid());
    unsigned int tid = static_cast<unsigned int>(std::hash<std::thread::id>()(std::this_thread::get_id()));

    // Combine all entropy sources
    unsigned int seed = timeSeed ^ (rd() << 1) ^ (pid << 2) ^ (tid << 3);
    return seed;
}

namespace o2
{
namespace eventgen
{
class GeneratorStarlight_class : public Generator
{
 public:
   GeneratorStarlight_class(){};
  ~GeneratorStarlight_class() = default;

  void setupDpmjet(std::string dpmjetconf){
    if(dpmjetconf.size() == 0)return;
    //Copy necesary files to the working directory
    TString pathDPMJET = gSystem->ExpandPathName("$DPMJET_ROOT/dpmdata");
    system(TString::Format("cp -r %s .",pathDPMJET.Data()));
    system(TString::Format("cp %s ./my.input",dpmjetconf.c_str()));

    //Reset four seeds of the DPMJET random generator in the config
    std::mt19937 gen(generateRandomSeed());
    std::uniform_int_distribution<> dist(1, 168);

    std::string command = "awk -i inplace -v nums=\"";
    for (int i = 0; i < 4; ++i)command += TString::Format("%d.0 ", dist(gen));
    command +=" \" \' ";
    command += "BEGIN {split(nums, newvals);}";
    command += "{if ($1 == \"RNDMINIT\") {printf \"%-16s%-9s%-9s%-9s%-9s\\n\", $1, newvals[1], newvals[2], newvals[3], newvals[4];}";
    command += " else {print $0;}}\' \"my.input\" ";
    system(command.c_str());
  }

  void selectConfiguration(std::string val) { mSelectedConfiguration = val; };
  void setExtraParams(std::string val) { mExtraParams = val; };
  void setCollisionSystem(float energyCM, int beam1Z, int beam1A, int beam2Z, int beam2A) {eCM = energyCM; projZ=beam1Z; projA=beam1A; targZ=beam2Z; targA=beam2A;};
  bool setParameter(std::string line) {
  if (not mInputParameters.setParameter(line)){
	  std::cout << " --- [ERROR] cannot set parameter: " << line << std::endl;
      return false;
    }
	return true;
  }
  int getPdgMother(){return mPdgMother;}
  double getPhotonEnergy(){
    //std::cout << mEvent.getGamma().gamma.GetE() << std::endl;
    return mEvent.getGamma().gamma.GetE();
  }

  bool Init() override
  {
    Generator::Init();

  float beam1energy = TMath::Sqrt(Double_t(projZ)/projA*targA/targZ)*eCM/2;
  float beam2energy = TMath::Sqrt(Double_t(projA)/projZ*targZ/targA)*eCM/2;
  float gamma1  = beam1energy/0.938272;
  float gamma2  = beam2energy/0.938272;
  float rapMax = 4.1 + 0.5*(TMath::ACosH(gamma2)-TMath::ACosH(gamma1));
  float dy = 0.01;

  const struct SLConfig {
    const char* name;
    int       prod_mode;
    int       prod_pid;
    int       nwbins;
    float     wmin;
    float     wmax;
	int		  pdg_mother;
	bool	  decay_EvtGen;
  } slConfig[] = {
    {"kTwoGammaToMuLow",     1,      13,  876,  0.4, 15.0,  -1, 0 }, // from 0.4 to 15 GeV
    {"kTwoGammaToElLow",     1,      11,  876,  0.4, 15.0,  -1, 0 }, // from 0.4 to 15 GeV
    {"kTwoGammaToMuMedium",  1,      13,  792,  1.8, 15.0,  -1, 0 }, // from 1.8 to 15 GeV
    {"kTwoGammaToElMedium",  1,      11,  792,  1.8, 15.0,  -1, 0 }, // from 1.8 to 15 GeV
    {"kTwoGammaToMuHigh",    1,      13,  660,  4.0, 15.0,  -1, 0 }, // from 4.0 to 15 GeV
    {"kTwoGammaToElHigh",    1,      11,  660,  4.0, 15.0,  -1, 0 }, // from 4.0 to 15 GeV
    {"kTwoGammaToRhoRho",    1,      33,   20, -1.0, -1.0,  -1, 0 }, //
    {"kTwoGammaToF2",        1,     225,   20, -1.0, -1.0,  -1, 0 }, //
    {"kCohRhoToPi",          3,     113, 1200, -1.0, -1.0,  113, 0 }, //
    {"kCohRhoToElEl",        3,  113011, 1200, -1.0, -1.0,  113, 0 }, //
    {"kCohRhoToMuMu",        3,  113013, 1200, -1.0, -1.0,  113, 0 }, //
    {"kCohRhoToPiWithCont",  3,     913, 1200, -1.0, -1.0,  113, 0 }, //
    {"kCohRhoToPiFlat",      3,     113,    1, -1.0,  2.5,  113, 0 }, //
    {"kCohPhiToKa",          2,     333,   20, -1.0, -1.0,  333, 0 }, //
    {"kCohPhiToEl",          2,  333011,   20, -1.0, -1.0,  333, 0 }, //
    {"kDirectPhiToKaKa",     3,     933,   20, -1.0, -1.0,  333, 0 }, //
    {"kCohOmegaTo2Pi",       2,     223,   20, -1.0, -1.0,  223, 0 }, //
    {"kCohOmegaTo3Pi",       2,     223,   20, -1.0, -1.0,  223, 1 }, //
    {"kCohOmegaToPiPiPi",    2, 223211111, 20, -1.0, -1.0,  233, 0 }, //
    {"kCohRhoPrimeTo4Pi",    3,     999, 1200, -1.0,  5.0,  30113, 0 }, //
    {"kCohJpsiToMu",         2,  443013,   20, -1.0, -1.0,  443, 0 }, //
    {"kCohJpsiToEl",         2,  443011,   20, -1.0, -1.0,  443, 0 }, //
    {"kCohJpsiToElRad",      2,  443011,   20, -1.0, -1.0,  443, 1 }, //
    {"kCohJpsiToProton",     2, 4432212,   20, -1.0, -1.0,  443, 0 }, //
    {"kCohJpsiToLLbar",      2, 4433122,   20, -1.0, -1.0,  443, 0 }, //
    {"kCohJpsi4Prong",       2,  443013,   20, -1.0, -1.0,  443, 1 }, //
    {"kCohJpsi6Prong",       2,  443013,   20, -1.0, -1.0,  443, 1 }, //
    {"kCohPsi2sToMu",        2,  444013,   20, -1.0, -1.0,  100443, 0 }, //
    {"kCohPsi2sToEl",        2,  444011,   20, -1.0, -1.0,  100443, 0 }, //
    {"kCohPsi2sToMuPi",      2,  444013,   20, -1.0, -1.0,  100443, 1 }, //
    {"kCohPsi2sToElPi",      2,  444011,   20, -1.0, -1.0,  100443, 1 }, //
    {"kCohUpsilonToMu",      2,  553013,   20, -1.0, -1.0,  553, 0 }, //
    {"kCohUpsilonToEl",      2,  553011,   20, -1.0, -1.0,  553, 0 }, //
    {"kIncohRhoToPi",        4,     113, 1200, -1.0, -1.0,  113, 0 }, //
    {"kIncohRhoToElEl",      4,  113011, 1200, -1.0, -1.0,  113, 0 }, //
    {"kIncohRhoToMuMu",      4,  113013, 1200, -1.0, -1.0,  113, 0 }, //
    {"kIncohRhoToPiWithCont",4,     913, 1200, -1.0, -1.0,  113, 0 }, //
    {"kIncohRhoToPiFlat",    4,     113,    1, -1.0,  2.5,  113, 0 }, //
    {"kIncohPhiToKa",        4,     333,   20, -1.0, -1.0,  333, 0 }, //
    {"kIncohOmegaTo2Pi",     4,     223,   20, -1.0, -1.0,  223, 0 }, //
    {"kIncohOmegaTo3Pi",     4,     223,   20, -1.0, -1.0,  223, 1 }, //
    {"kIncohOmegaToPiPiPi",  4, 223211111, 20, -1.0, -1.0,  223, 0 }, //
    {"kIncohRhoPrimeTo4Pi",  4,     999, 1200, -1.0,  5.0,  30113, 0 }, //
    {"kIncohJpsiToMu",       4,  443013,   20, -1.0, -1.0,  443, 0 }, //
    {"kIncohJpsiToEl",       4,  443011,   20, -1.0, -1.0,  443, 0 }, //
    {"kIncohJpsiToElRad",    4,  443011,   20, -1.0, -1.0,  443, 1 }, //
    {"kIncohJpsiToProton",   4, 4432212,   20, -1.0, -1.0,  443, 0 }, //
    {"kIncohJpsiToLLbar",    4, 4433122,   20, -1.0, -1.0,  443, 0 }, //
    {"kIncohPsi2sToMu",      4,  444013,   20, -1.0, -1.0,  100443, 0 }, //
    {"kIncohPsi2sToEl",      4,  444011,   20, -1.0, -1.0,  100443, 0 }, //
    {"kIncohPsi2sToMuPi",    4,  444013,   20, -1.0, -1.0,  100443, 1 }, //
    {"kIncohPsi2sToElPi",    4,  444011,   20, -1.0, -1.0,  100443, 1 }, //
    {"kIncohUpsilonToMu",    4,  553013,   20, -1.0, -1.0,  553, 0 }, //
    {"kIncohUpsilonToEl",    4,  553011,   20, -1.0, -1.0,  553, 0 }, //
    {"kDpmjetSingleA",        5,  113,   20, -1.0, -1.0,  -1, 0 }, //
    {"kDpmjetSingleC",        5,  113,   20, -1.0, -1.0,  -1, 0 }, //
    {"kTauLowToEl3Pi",       1,      15,  990,  3.5, 20.0,  -1, 1 }, // from 0.4 to 15 GeV
    {"kTauLowToPo3Pi",       1,      15,  990,  3.5, 20.0,  -1, 1 }, // from 0.4 to 15 GeV
    {"kTauLowToElMu",        1,      15,  990,  3.5, 20.0,  -1, 1 }, // from 0.4 to 15 GeV
    {"kTauLowToElPiPi0",     1,      15,  990,  3.5, 20.0,  -1, 1 }, // from 0.4 to 15 GeV
    {"kTauLowToPoPiPi0",     1,      15,  990,  3.5, 20.0,  -1, 1 }, // from 0.4 to 15 GeV
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

  unsigned int random_seed = generateRandomSeed();

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
  setParameter(Form("RAP_N_BINS   =   %.0f    #Bins i y",rapMax*2./dy));
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
  setParameter("XSEC_METHOD   = 0      # Set to 0 to use old method for calculating gamma-gamma luminosity"); //CM
  setParameter("BSLOPE_DEFINITION = 2");   // using default slope
  setParameter("BSLOPE_VALUE      = 4.0"); // default slope value
  setParameter("PRINT_VM = 0"); // print cross sections and fluxes vs rapidity in stdout for VM photoproduction processes

  // Photonuclear specific options, energies in Lab frame. These values should be within the range of the values specified in the DPMJet input file (when DPMJet is used)
  if(slConfig[idx].prod_mode == 5 || slConfig[idx].prod_mode == 6 || slConfig[idx].prod_mode == 7){
    setParameter("MIN_GAMMA_ENERGY = 1000.0");
    setParameter("MAX_GAMMA_ENERGY = 600000.0");
    setParameter("KEEP_PHI = 1");
    setParameter("KEEP_KSTAR = 1");
  }

  TString extraPars(mExtraParams);
  TString token;
  Ssiz_t from = 0;
  while(extraPars.Tokenize(token, from, ";"))setParameter(token.Data());

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

  if (mInputParameters.interactionType() >= 5) {
    mUpcEvent = mStarLight->produceUpcEvent();
    mUpcEvent.boost(0.5*(TMath::ACosH(mInputParameters.beam1LorentzGamma()) - TMath::ACosH(mInputParameters.beam2LorentzGamma())));
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
  const std::vector<vector3>* slVtx;
  const std::vector<starlightParticle>* slPartArr;
  int npart = 0;

  if (mInputParameters.interactionType() >= 5) {
    slVtx = mUpcEvent.getVertices();
    slPartArr = mUpcEvent.getParticles();
    npart = mUpcEvent.getParticles()->size();
  }
  else{
    slVtx = mEvent.getVertices();
    slPartArr = mEvent.getParticles();
    npart = mEvent.getParticles()->size();
  }

  if (slVtx == 0) { // not vertex assume 0,0,0,0;
    vtx = vty = vtz = vtt = 0.0;
    }
  else { // a vertex exits
      nVtx = slVtx->size();
    } // end if

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
	  o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back(), false);
  }
  if(!mDecayEvtGen || mPdgMother == -1){ // Don't import daughters in case of external decayer
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
				   (mPdgMother != -1 ? 0 :-1),
				   -1,
				   -1,
				   -1,
				   slPart->GetPx(),
				   slPart->GetPy(),
				   (mSelectedConfiguration.compare("kDpmjetSingleC") == 0 ? -1.0*slPart->GetPz() : slPart->GetPz()),
				   slPart->GetE(),
				   vtx,vty,vtz,vtt);
	  //particle.Print();
	  mParticles.push_back(particle);
      o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back(), true);
    }
  }
  return true;
  }

   protected:
   float eCM = 5020; //CMS energy
   int projA=208;	//Beam
   int targA=208;
   int projZ=82;
   int targZ=82;

   private:
   starlight        *mStarLight = 0x0;
   inputParameters  mInputParameters;  //   simulation input information.
   randomGenerator  mRandomGenerator;  //   STARLIGHT's own random generator
   upcXEvent        mEvent;            //  object holding STARlight simulated event.
   upcEvent         mUpcEvent;
   std::string mSelectedConfiguration = "";
   std::string mExtraParams = "";
   int mPdgMother = -1;
   bool mDecayEvtGen = 0;


 };

} // namespace eventgen
} // namespace o2


FairGenerator*
  GeneratorStarlight(std::string configuration = "empty",float energyCM = 5020, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "",std::string dpmjetconf = "")
{

  auto gen = new o2::eventgen::GeneratorStarlight_class();
  gen->selectConfiguration(configuration);
  gen->setCollisionSystem(energyCM, beam1Z, beam1A, beam2Z, beam2A);
  gen->setExtraParams(extrapars);
  gen->setupDpmjet(dpmjetconf);
  return gen;
}




