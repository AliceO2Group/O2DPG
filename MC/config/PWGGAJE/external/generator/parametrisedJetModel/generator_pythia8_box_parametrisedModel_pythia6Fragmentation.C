#if !defined(__CLING__) || defined(__ROOTCLING__)

#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TDatabasePDG.h"
#include "TF1.h"
#include "TGrid.h"
#include "TMath.h"
#include "TParticlePDG.h"
#include "TRandom3.h"
#include <cmath>
#endif

#include "Pythia8/Pythia.h"
#include <rapidjson/document.h>
#include <rapidjson/filereadstream.h>

R__LOAD_LIBRARY(libpythia6)
R__LOAD_LIBRARY(libGeneratorParam)
#include "TPythia6.h"

using namespace Pythia8;

// #include "SimulationDataFormat/ParticleStatus.h"
// #include "SimulationDataFormat/MCEventHeader.h"

// Input to simulation:
// inputFilePathName file is expected to be a json file with the structure like so:
//  {
//    "simLog": false,
//    "sglGenRAA": 1,
//    "sglGenTAA": 1,
//    "sglCutoffSteepNess": 15,
//    "sglCutoffAbscissa": 10,
//    "fallSpecterSlopeLog": 10.833274,
//    "fallSpecterAffinePowerConstantTerm": -5.476804,
//    "fallSpecterAffinePowerSlope": 0.001110,
//    "bkgAveragePt": 0.670,
//    "collTotalMultWithBkg": 2000
//  }
// can be uploaded to grid using for example: alien.py cp
// file:/local/path/parametrisedModel_PbPb_5p36TeV_cent0010.json
// alien:/path/on/alien/parametrisedModel_PbPb_5p36TeV_cent0010.json

class GeneratorParametrisedJetModel : public o2::eventgen::GeneratorPythia8 {
public:
  /// constructor
  GeneratorParametrisedJetModel(std::string inputSimParametersPath, std::string inputSimParametersFileName, bool generateUE = true) : mInputSimParametersPath{inputSimParametersPath}, mInputSimParametersFileName{inputSimParametersFileName}, mGenerateUE{generateUE} {

    std::string inputFilePathName = "alien://" + inputSimParametersPath + inputSimParametersFileName;
    if (!gGrid) {
      TGrid::Connect("alien://");
      if (!gGrid) {
        LOG(fatal) << "AliEn connection failed, check token.";
        exit(1);
      }
    }
    // fetch and copy the .json file to the sim work directory
    std::string outputPath = "./";
    TString aliencp = Form("alien_cp alien://%s%s file:%s%s", inputSimParametersPath.c_str(),
                            inputSimParametersFileName.c_str(), outputPath.c_str(), 
                            inputSimParametersFileName.c_str()); // an internal operation in ROOT that discards the
                                                                 // JSON file directly (smaller than 300 bytes and if
                                                                 // a bit bigger it would discard the file because it
                                                                 // understands it's not a ROOT file), thus one
                                                                 // cannot use TFile::Cp()
    if (gSystem->Exec(aliencp.Data()) != 0) {
      cout << "Error: Sim parameters .json file " << inputFilePathName << " does not exist!" << endl;
      exit(1);
    }
    // open the file
    std::FILE *fjson = std::fopen(inputSimParametersFileName.c_str(), "r");
    if (!fjson) {
      cout << "Could not open sim parameters file " << inputFilePathName << endl;
      exit(1);
    }

    // create streamer
    char readBuffer[65536];
    rapidjson::FileReadStream jsonStream(fjson, readBuffer, sizeof(readBuffer));

    // parse the json file
    rapidjson::Document jsonDocument;
    jsonDocument.ParseStream(jsonStream);

    // is it a proper json document?
    if (jsonDocument.HasParseError()) {
      cout << "Check the sim parameters file! There is a problem with the format!" << endl;
      exit(1);
    }

    // are the parameter names as expected?
    for (const std::string &parameterName : mConfigurableSimParameterNames) {
      if (!jsonDocument.HasMember(parameterName.c_str())) {
        cout << "Check the sim parameters file! Item " << parameterName << " is missing!" << endl;
        exit(1);
      }
    }

    // write log of simulation?
    std::string writeLog("simLog");
    if (!jsonDocument.HasMember(writeLog.c_str())) {
      cout << "Check the sim parameters file! Item " << writeLog.c_str() << " is missing!" << endl;
      exit(1);
    }
    mDebug = jsonDocument[writeLog.c_str()].GetBool();

    // get parameters for sim
    mSglGenRAA = jsonDocument[mConfigurableSimParameterNames.at(0).c_str()].GetDouble();
    mSglGenTAA = jsonDocument[mConfigurableSimParameterNames.at(1).c_str()].GetDouble();
    mSglCutoffSteepNess = jsonDocument[mConfigurableSimParameterNames.at(2).c_str()].GetDouble();
    mSglCutoffAbscissa = jsonDocument[mConfigurableSimParameterNames.at(3).c_str()].GetDouble();
    mFallSpecterSlopeLog = jsonDocument[mConfigurableSimParameterNames.at(4).c_str()].GetDouble();
    mFallSpecterAffinePowerConstantTerm = jsonDocument[mConfigurableSimParameterNames.at(5).c_str()].GetDouble();
    mFallSpecterAffinePowerSlope = jsonDocument[mConfigurableSimParameterNames.at(6).c_str()].GetDouble();
    mBkgAveragePt = jsonDocument[mConfigurableSimParameterNames.at(7).c_str()].GetDouble();
    mCollTotalMultWithBkg = jsonDocument[mConfigurableSimParameterNames.at(8).c_str()].GetDouble();

    // clean up
    std::fclose(fjson);

    cout << "param retrieved: mSglGenRAA = " << mSglGenRAA << endl;
    cout << "param retrieved: mSglGenTAA = " << mSglGenTAA << endl;
    cout << "param retrieved: mSglCutoffSteepNess = " << mSglCutoffSteepNess << endl;
    cout << "param retrieved: mSglCutoffAbscissa = " << mSglCutoffAbscissa << endl;
    cout << "param retrieved: mFallSpecterSlopeLog = " << mFallSpecterSlopeLog << endl;
    cout << "param retrieved: mFallSpecterAffinePowerConstantTerm = " << mFallSpecterAffinePowerConstantTerm << endl;
    cout << "param retrieved: mFallSpecterAffinePowerSlope = " << mFallSpecterAffinePowerSlope << endl;
    cout << "param retrieved: mBkgAveragePt = " << mBkgAveragePt << endl;
    cout << "param retrieved: mCollTotalMultWithBkg = " << mCollTotalMultWithBkg << endl;

    // thermal background function
    mBoltzmannPDF = new TF1("f1", "[0]*[0]*x*exp(-[0]*x)", mBkgGenPtMin, mPtInfinity);
    mBoltzmannPDF->SetParameter(0, 2. / mBkgAveragePt);

    // jet signal function
    // this thesis says that the jet distrib used to sample parton pt is
    // actually full jet -> solves neutral particle fragments issue (better than
    // scaling) https://drupal.star.bnl.gov/STAR/files/phd_thesis_rusnak.pdf for
    // the fragments radiating outside of the jet radius issue: instead of using
    // this PYTHIA distrib directly as the truth distrib in unfolding closure,
    // instead we do the same sim+jet reco, but without the bkg; so need to have
    // the option to run with and without UE bkg probably should use biggest
    // Radius one can find with good stats for the pp PYTHIA
    mJetYieldFit = new TF1("f2", "[0]*[1]*exp(-exp(-[2]*(x-[3]))) * exp([4])*pow(x, [5]+[6]*x)", 0, mPtInfinity); // RAA * TAA * sigmoid(cutoff at [2])  * fit to fulljetSpectrum in pp PYTHIA
    mJetYieldFit->SetParameter(0, mSglGenRAA); // rAA (single value for all pt)
    mJetYieldFit->SetParameter(1, mSglGenTAA); // <tAA>
    mJetYieldFit->SetParameter(2, mSglCutoffSteepNess); // steepness for the cutoff shape; higher is
                                                        // steeper, but looks more and more like a
                                                        // Heavyside step function as it gets to 50 or 100
    mJetYieldFit->SetParameter(3, mSglCutoffAbscissa); // cutoffpoint of hard population, in GeV/c
    mJetYieldFit->SetParameter(4, mFallSpecterSlopeLog); // falling spectrum ln() of proportionality factor
    mJetYieldFit->SetParameter(5, mFallSpecterAffinePowerConstantTerm); // falling spectrum affine power: constant term
    mJetYieldFit->SetParameter(6, mFallSpecterAffinePowerSlope); // falling spectrum affine power: proportionality factor
    // values from full jet spectra fit of R=0.6 jets in
    // https://journals.aps.org/prc/abstract/10.1103/PhysRevC.101.034911;
    // hepdata link: https://www.hepdata.net/record/ins1755387 done using TF1*
    // fitFullJetSpectrum = new TF1(fname, "exp([0]) * pow(x, [1] + [2]*x)",
    // fitMin, fitMax); fit, parameters first initialised by fitting
    // log(fullSpectrum) with log(fitFullJetSpectrum tf1);

    mNJetsAverage = mJetYieldFit->Integral(mSglCutoffAbscissa, mPtInfinity); // careful, this script assumes the mJetYieldFit is the
                                                                             // pt-differential yield, integrated over eta

    mPythia.init(); // Initialize
  }

  ///  Destructor
  ~GeneratorParametrisedJetModel() = default;

  Bool_t generateEvent() override {
    if (mDebug) {
      cout << "##########################################################################################################" << endl;
      cout << "###################################### Beginning of generateEvent() ######################################" << endl;
      cout << "##########################################################################################################" << endl;
    }

    mPythia.event.reset();

    ///////////////////////////////////////////////
    ////////////////// Jet signal /////////////////
    ///////////////////////////////////////////////

    int nJets = gRandom->Poisson(mNJetsAverage);

    if (mDebug) {
      cout << "####################### creating partons signal #######################" << endl;
      cout << "signal: count " << nJets << " for mNJetsAverage = " << mNJetsAverage << "" << endl;
    }

    TClonesArray *genParticlesArray = new TClonesArray("TParticle", 1000);

    int particleCountCurrent = 1; // counts the system fake particle pdg 90
    for (int iJet{0}; iJet < nJets; ++iJet) {
      genParticlesArray->Delete();

      const bool isQuark = gRandom->Uniform(0, 1) > 1. / 3 ? true : false; // ratio quarks:gluons = 2:1
      const int pdgQuark = gRandom->Uniform(0, 1) > 1. / 2 ? mPdgQuarkU : mPdgQuarkD; // half and half for u and d quarks
      const int pdgJet = (int)isQuark * pdgQuark + (1 - (int)isQuark) * mPdgGluon;
      const double sglMass = TDatabasePDG::Instance()->GetParticle(pdgJet)->Mass();
      const double sglPt = mJetYieldFit->GetRandom(mSglCutoffAbscissa, mPtInfinity);
      const double sglEta = gRandom->Uniform(mGenMinEta, mGenMaxEta);
      const double sglPhi = gRandom->Uniform(0, o2::constants::math::TwoPI);
      const double sglPx{sglPt * std::cos(sglPhi)};
      const double sglPy{sglPt * std::sin(sglPhi)};
      const double sglPz{sglPt * std::sinh(sglEta)};
      const double sglEt{std::hypot(std::hypot(sglPt, sglPz), sglMass)};

      Particle myJet;
      myJet.id(pdgJet);
      myJet.status(23);
      myJet.px(sglPx);
      myJet.py(sglPy);
      myJet.pz(sglPz);
      myJet.e(sglEt);
      myJet.m(sglMass);
      myJet.xProd(0);
      myJet.yProd(0);
      myJet.zProd(0);
      int jetCol = 101 + 2 * iJet; // each jet gets a different colour and acolour value,
                                   // so that the pythia knows they're distinct colour
                                   // lines, i.e. different strings
      int jetACol = 101 + 2 * iJet + 1;

      if (mDebug) {
        cout << "-- || jet parton #" << iJet
             << ", index=" << mPythia.event.back().index() + 1
             << ": isQuark = " << isQuark << ", pdg = " << pdgJet
             << ", pt = " << sglPt << ", mass = " << sglMass << endl;
      }

      auto pythia6Event = TPythia6::Instance();

      int lineNumber = 0; // line number seems to be index of particle in array; set to 0 in
                          // PM code? but doc says it runs Pyexec() right after; iJet doesn't
                          // work for ijet=1+; set to 0 and it seems to work
      double sglTheta = 2.0 * std::atan(std::exp(-1 * sglEta));
      pythia6Event->Py1ent(lineNumber, pdgJet, sglEt, sglTheta, sglPhi);

      int final = pythia6Event->ImportParticles(genParticlesArray, "Final"); // only saves final state particles; "All" would instead give all the particles
      int nConstituents = genParticlesArray->GetEntries();

      mPythia.event.append(myJet);
      for (int iParticle = 0; iParticle < nConstituents; ++iParticle) {
        TParticle *tParticle = (TParticle *)genParticlesArray->At(iParticle);

        Particle pythiaParticle;
        pythiaParticle.id(tParticle->GetPdgCode());
        pythiaParticle.status(tParticle->GetStatusCode()); // in pythia6 all the particles that are not
                                                           // the initial partons have status code 1;
                                                           // this is because apparently pythia6 does
                                                           // not decay them automatically yet; they
                                                           // are by no means all stable particles; but
                                                           // we do not care for this study
        pythiaParticle.px(tParticle->Px());
        pythiaParticle.py(tParticle->Py());
        pythiaParticle.pz(tParticle->Pz());
        pythiaParticle.e(tParticle->Energy());
        pythiaParticle.m(tParticle->GetMass());
        pythiaParticle.xProd(tParticle->Vx());
        pythiaParticle.yProd(tParticle->Vy());
        pythiaParticle.zProd(tParticle->Vz());
        pythiaParticle.mother1(particleCountCurrent); // particleCountCurrent is the offset to  account for existing IDs of constituents of previous jets.
                                                      // Not saving the actual mother ID because ImportParticles(genParticlesArray, "Final") only saves the final
                                                      // particles, and the mother id still refer to particles not saved in
                                                      // genParticlesArray a priori the mother-daughter links aren't needed
                                                      // for the closure test this will be used for; keeping the initial
                                                      // parton as mother for now

        mPythia.event.append(pythiaParticle);
      }
      particleCountCurrent += nConstituents + 1; // +1 is for the jet parton itself, which is not in the final state
    }
    delete genParticlesArray;

    if (mDebug) {
      mPythia.event.list();
    }

    ///////////////////////////////////////////////
    // Underlying Event (UE): thermal background //
    ///////////////////////////////////////////////

    if (mGenerateUE) {
      int nHardParticles = mPythia.event.size() - 1; // number of particles after hadronisation of jet partons and pruning, -1 because of system particle with pdg id 90
      int sign = 1;
      if (mDebug) {
        cout << "####################### Adding Thermal Background #######################" << endl;
      }
      for (int iBkg{0}; iBkg < mCollTotalMultWithBkg - nHardParticles; ++iBkg) {
        const double bkgPt = mBoltzmannPDF->GetRandom(mBkgGenPtMin, mPtInfinity);
        const double bkgEta = gRandom->Uniform(mGenMinEta, mGenMaxEta);
        const double bkgPhi = gRandom->Uniform(0, o2::constants::math::TwoPI);
        const double bkgPx{bkgPt * std::cos(bkgPhi)};
        const double bkgPy{bkgPt * std::sin(bkgPhi)};
        const double bkgPz{bkgPt * std::sinh(bkgEta)};
        const double bkgEt{std::hypot(std::hypot(bkgPt, bkgPz), mBkgMass)};
        sign *= gRandom->Uniform(0, 1) > 0.5 ? 1 : -1;

        Particle myParticle;
        myParticle.id(sign *
                      mPdgPion); // let's make them pions until further notice
        myParticle.status(201); // 201+ free to use by anybody; using 201 to know if's from background
                                // https://pythia.org/latest-manual/ParticleProperties.html;
        myParticle.px(bkgPx);
        myParticle.py(bkgPy);
        myParticle.pz(bkgPz);
        myParticle.e(bkgEt);
        myParticle.m(mBkgMass);
        myParticle.xProd(0);
        myParticle.yProd(0);
        myParticle.zProd(0);

        if (iBkg % 100 == 0 && mDebug) {
          cout << "------- ||||| bkg particle " << iBkg << ": pt = " << bkgPt << endl;
        }

        mPythia.event.append(myParticle);
      }
    }

    if (mDebug) {
      cout << "##########################################################################################################" << endl;
      cout << "######################################## End of generateEvent() ##########################################" << endl;
      cout << "##########################################################################################################" << endl;
    }
    return true;
  }

  //__________________________________________________________________

private:
  bool mDebug = false; // setting to true will display particle lists
  std::string mInputSimParametersPath, mInputSimParametersFileName; // input path and file name of .json used to read simulation parameters

  ////////////////////////////////////////////////
  ///////// Common signal and background parameters ////////
  ////////////////////////////////////////////////

  const double mPtInfinity = 300; // maximum pt (in GeV/c) for generated particles, and upper pT limit for integral and TF1 purposes; too high and GetRandom struggles
  const double mGenMinEta = -1.; /// minimum pseudorapidity for generated particles
  const double mGenMaxEta = +1.; /// maximum pseudorapidity for generated particles
  int mCollTotalMultWithBkg; /// total multiplicity of the collision
  bool mGenerateUE = false; /// boolean to request (or not) embedding of the jet signal inside underlying event modelled by a thermal background
  const std::vector<std::string> mConfigurableSimParameterNames = {
      "sglGenRAA",
      "sglGenTAA",
      "sglCutoffSteepNess",
      "sglCutoffAbscissa",
      "fallSpecterSlopeLog",
      "fallSpecterAffinePowerConstantTerm",
      "fallSpecterAffinePowerSlope",
      "bkgAveragePt",
      "collTotalMultWithBkg"};

  /////////////////////////////////////////////
  /////// Thermal background parameters ///////
  /////////////////////////////////////////////

  // bkg fit
  TF1 *mBoltzmannPDF; /// TF1 to store pdf function from which pt is drawn
  double mBkgAveragePt;
  const double mBkgGenPtMin = 0; /// minimum pt (in GeV/c) for generated particles
  const double mBkgMass = 0; /// particle mass [GeV/c^2]

  // bkg pdg code
  const int mPdgPion = 211; /// particle pdg code of pion check that is not
                            /// defined somewhere already

  /////////////////////////////////////
  /////// Jet signal parameters ///////
  /////////////////////////////////////

  // signal fit
  double mSglGenRAA;
  double mSglGenTAA;
  double mSglCutoffSteepNess; /// steepness for the cutoff shape; higher is  steeper, but looks more and more like a Heavyside step function as it gets to 50 or 100
  double mSglCutoffAbscissa;  /// minimum pt (in GeV/c) for jet signal distribution; it's a smooth cutoff
  double mFallSpecterSlopeLog;
  double mFallSpecterAffinePowerConstantTerm;
  double mFallSpecterAffinePowerSlope;
  TF1 *mJetYieldFit;    /// TF1 to store pdf function from which pt is drawn
  double mNJetsAverage; /// average number of jets in a collision

  // signal pdg codes
  const int mPdgQuarkU = 1; /// particle pdg code of quark u
  const int mPdgQuarkD = 2; /// particle pdg code of quark d
  const int mPdgGluon = 21; /// particle pdg code of gluon
};

///___________________________________________________________
FairGenerator *generateParametrisedJetModel(std::string inputSimParametersPath, 
                                            std::string inputSimParametersFileName, 
                                            bool generateUE = true) {
  return new GeneratorParametrisedJetModel(inputSimParametersPath, inputSimParametersFileName, generateUE);
}