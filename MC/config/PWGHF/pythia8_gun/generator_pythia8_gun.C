#include "Pythia8/Pythia.h"
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

class GeneratorPythia8Gun : public o2::eventgen::GeneratorPythia8
{
 public:
  /// default constructor
  GeneratorPythia8Gun() = default;

  /// constructor
  GeneratorPythia8Gun(int input_pdg)
  {
    genMinP = 1.;
    genMaxP = 16.;
    genMinEta = -0.1;
    genMaxEta = 0.1;

    pdg = input_pdg;
    E = 0;
    px = 0;
    py = 0;
    pz = 0;
    p = 0;
    y = 0;
    eta = 0;
    xProd = 0;
    yProd = 0;
    zProd = 0;
    xProd = 0.;
    yProd = 0.;
    zProd = 0.;
    // addFurtherPion=false;

    randomizePDGsign = false;

    m = getMass(input_pdg);
    furtherPrim = {};
    keys_furtherPrim = {};
  }

  ///  Destructor
  ~GeneratorPythia8Gun() = default;

  /// set PDG code
  void setPDG(int input_pdg) { pdg = input_pdg; }

  /// randomize the PDG code sign of core particle
  void setRandomizePDGsign() { randomizePDGsign = true; }

  /// set mass
  void setMass(int input_m) { m = input_m; }

  /// set 4-momentum
  void set4momentum(double input_px, double input_py, double input_pz)
  {
    px = input_px;
    py = input_py;
    pz = input_pz;
    E = sqrt(m * m + px * px + py * py + pz * pz);
    fourMomentum.px(px);
    fourMomentum.py(py);
    fourMomentum.pz(pz);
    fourMomentum.e(E);
    p = sqrt(px * px + py * py + pz * pz);
    y = 0.5 * log((E + pz) / (E - pz));
    eta = 0.5 * log((p + pz) / (p - pz));

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
  void setMomentum(double input_p) { p = input_p; }

  /// set x,y,z of production vertex
  void setProdVtx(double input_xProd, double input_yProd, double input_zProd)
  {
    xProd = input_xProd;
    yProd = input_xProd;
    zProd = input_zProd;
  }

  /// setter to add further primary particles to the event
  void setAddFurtherPrimaries(const int pdgCode, const int howMany)
  {
    /// check if this species has been already added
    const int map_counts = furtherPrim.count(pdgCode);
    if (map_counts == 1) { // species already present
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
  // void setAddFurtherPion(){addFurtherPion=true;}

  /// get mass from TParticlePDG
  double getMass(int input_pdg)
  {
    double mass = 0;
    if (TDatabasePDG::Instance()) {
      TParticlePDG* particle = TDatabasePDG::Instance()->GetParticle(input_pdg);
      if (particle)
        mass = particle->Mass();
      else
        std::cout << "===> particle mass equal to 0" << std::endl;
    }
    return mass;
  }

  //_________________________________________________________________________________
  /// generate uniform eta and uniform momentum
  void genUniformMomentumEta(double minP, double maxP, double minEta, double maxEta)
  {
    // Warning: this generator samples randomly in p and not in pT. Care is advised

    // random generator
    std::unique_ptr<TRandom3> ranGenerator{new TRandom3()};
    ranGenerator->SetSeed(0);

    // momentum
    const double gen_p = ranGenerator->Uniform(minP, maxP);
    // eta
    const double gen_eta = ranGenerator->Uniform(minEta, maxEta);
    // z-component momentum from eta
    const double cosTheta = (exp(2 * gen_eta) - 1) / (exp(2 * gen_eta) + 1); // starting from eta = -ln(tan(theta/2)) = 1/2*ln( (1+cos(theta))/(1-cos(theta)) ) ---> NB: valid for cos(theta)!=1
    const double gen_pz = gen_p * cosTheta;
    // phi: random uniform, X, Y conform
    const double pT = sqrt(gen_p * gen_p - gen_pz * gen_pz);
    double phi = ranGenerator->Uniform(0., 2.0f*TMath::Pi());
    const double gen_px = pT*TMath::Cos(phi);
    const double gen_py = pT*TMath::Sin(phi);

    set4momentum(gen_px, gen_py, gen_pz);
  }

 protected:
  //__________________________________________________________________
  Particle createParticle()
  {
    std::cout << "createParticle() mass " << m << " pdgCode " << pdg << std::endl;
    Particle myparticle;
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
  Bool_t generateEvent() override
  {

    const double original_m = m;
    const int original_pdg = pdg;

    /// reset event
    mPythia.event.reset();

    /// create and append the desired particle
    // genUniformMomentumEta(1.,16.,-0.1,0.1);
    genUniformMomentumEta(genMinP, genMaxP, genMinEta, genMaxEta);
    if (randomizePDGsign)
      pdg *= randomizeSign();
    Particle particle = createParticle();
    //
    mPythia.event.append(particle);
    //

    /// add further particles, if required
    if (furtherPrim.size() > 0) {
      if (keys_furtherPrim.size() < 1) { /// protection
        std::cout << "Something wrong with the insertion of further particles" << std::endl;
        return false;
      }
      /// loop in the map
      for (const int addPDG : keys_furtherPrim) {
        const int numAddPrim = furtherPrim[addPDG]; // we will add "numAddPrim" particles of type "addPDG"
        //
        // Modify the mass before calling genUniformMomentumEta (required inside set4momentum function)
        m = getMass(addPDG);
        pdg = addPDG;
        //
        for (int iAdd = 0; iAdd < numAddPrim; iAdd++) { // generated and append the desired particle
          genUniformMomentumEta(genMinP, genMaxP, genMinEta, genMaxEta);
          Particle further_particle = createParticle();
          mPythia.event.append(further_particle);
        }
      } // end loop map

      // restore the values for the desired injected particle (mandatory for next iteration)
      m = original_m;
      pdg = original_pdg;
    }

    /// go to next Pythia event
    mPythia.next();

    return true;
  }

 private:
  double genMinP;   /// minimum 3-momentum for generated particles
  double genMaxP;   /// maximum 3-momentum for generated particles
  double genMinEta; /// minimum pseudorapidity for generated particles
  double genMaxEta; /// maximum pseudorapidity for generated particles

  Vec4 fourMomentum; /// four-momentum (px,py,pz,E)
  double E;          /// energy: sqrt( m*m+px*px+py*py+pz*pz ) [GeV/c]
  double m;          /// particle mass [GeV/c^2]
  int pdg;           /// particle pdg code
  double px;         /// x-component momentum [GeV/c]
  double py;         /// y-component momentum [GeV/c]
  double pz;         /// z-component momentum [GeV/c]
  double p;          /// momentum
  double y;          /// rapidity
  double eta;        /// pseudorapidity
  double xProd;      /// x-coordinate position production vertex [cm]
  double yProd;      /// y-coordinate position production vertex [cm]
  double zProd;      /// z-coordinate position production vertex [cm]

  bool randomizePDGsign; /// bool to randomize the PDG code of the core particle

  // bool   addFurtherPion;	/// bool to attach an additional primary pion
  std::map<int, int> furtherPrim;           /// key: PDG code; value: how many further primaries of this species to be added
  std::unordered_set<int> keys_furtherPrim; /// keys of the above map (NB: only unique elements allowed!)
};

///___________________________________________________________
FairGenerator* generateOmegaC()
{
  auto myGen = new GeneratorPythia8Gun(4332);
  myGen->setRandomizePDGsign(); // randomization of OmegaC PDG switched on
  return myGen;
}

///___________________________________________________________
FairGenerator* generateOmegaAndPions_RandomCharge(const int nPions)
{

  auto myGen = new GeneratorPythia8Gun(3334);
  myGen->setRandomizePDGsign(); // randomization of Omega PDG switched on

  /// add further pions
  myGen->setAddFurtherPrimaries(211, nPions / 2);  // pi+
  myGen->setAddFurtherPrimaries(-211, nPions / 2); // pi-

  return myGen;
}
