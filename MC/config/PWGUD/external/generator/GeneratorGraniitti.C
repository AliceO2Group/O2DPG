namespace o2
{
namespace eventgen
{
class GeneratorGraniitti_class : public Generator
{
 public:
  GeneratorGraniitti_class() { };
  ~GeneratorGraniitti_class() = default;
  bool setJsonFile(std::string fname) {
    jsonFile = fname;
    // check if jsonFile exists
    if (gSystem->AccessPathName(jsonFile.c_str())) {
      return false;
    }
    
    return setHepMCFile();
  }

  bool setHepMCFile() {
    // item "OUTPUT" defines the hepmcFile
    // find
    //  "OUTPUT" : hepmcFile
    std::string cmd = "grep \"OUTPUT\" "+jsonFile;
    auto res = gSystem->GetFromPipe(cmd.c_str());
    auto lines = res.Tokenize("\n");
    if (lines->GetEntries() != 1) {
      return false;
    }
    
    auto parts = ((TObjString*)lines->At(0))->GetString().Tokenize(":");
    if (parts->GetEntries() != 2) {
      return false;
    }

    auto fname = ((TObjString*)parts->At(1))->GetString();
    hepmcFile = std::string(gSystem->Getenv("PWD"))+"/"+(std::string)fname.ReplaceAll("\"", "").ReplaceAll(",", "").ReplaceAll(" ", "")+".hepmc3";
    return true;
  }
  
  bool createHepMCFile() {
    // run graniitti with
    //  jsonFile as input
    auto cmd = "$Graniitti_ROOT/bin/gr -i " + jsonFile;
    std::cout << "Generating events ...";
    auto res = gSystem->GetFromPipe(cmd.c_str());
    std::cout << "done!\n";

    // check res to be ok
    
    return true;
  }

  void openHepMCFile() {
    reader = new o2::eventgen::GeneratorHepMC();
    reader->setFileNames(hepmcFile);
    if (!reader->Init())
    {
      std::cout << "GenerateEvent: Graniitti class/object not properly initialized"
                << std::endl;
    }
  };

  bool generateEvent() override {
    if (reader->generateEvent()) {
      return true;
    } else {
      std::cout << "New file needs to be generated.";
      delete reader;
      createHepMCFile();
      openHepMCFile();
      return reader->generateEvent();
    }
  };

  bool importParticles() override {
    mParticles.clear();
    if (!reader->importParticles()) {
      return false;
    }
    for (auto part : reader->getParticles()) {
      TParticle particle(part.GetPdgCode(),
                         1,
                         part.GetFirstMother(),
                         -1,
                         part.GetFirstDaughter(),
                         part.GetLastDaughter(),
                         part.Px(),
                         part.Py(),
                         part.Pz(),
                         part.Energy(),
                         0.,
                         0.,
                         0.,
                         0.);
      mParticles.push_back(particle);
      o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(
        mParticles.back(), true);
    }
    return true;
  };

 private:
  o2::eventgen::GeneratorHepMC *reader = 0x0;
  std::string jsonFile;
  std::string hepmcFile;
  
};

} // namespace eventgen
} // namespace o2

FairGenerator* GeneratorGraniitti(std::string jsonFile) {

  // create generator
  auto gen = new o2::eventgen::GeneratorGraniitti_class();
  if (gen->setJsonFile(jsonFile)) {
    if (gen->createHepMCFile()) {
      // preparing reader
      gen->openHepMCFile();
    }
  }

  return gen;
}
