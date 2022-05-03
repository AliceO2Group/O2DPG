void hepmc_reader(const char* fname, int version = 2);
void user_code(const std::vector<TParticle>& particles);

void hepmc_reader(const char* fname, int version)
{

  /** instance and initialise genarator HepMC **/
  auto reader = new o2::eventgen::GeneratorHepMC;
  reader->setFileName(fname);
  reader->setVersion(version);
  if (!reader->Init())
    return;

  /** loop over events **/
  while (reader->generateEvent() && reader->importParticles()) {

    /** get particles **/
    auto& particles = reader->getParticles();

    /** execute user code **/
    user_code(particles);
  }
}

void user_code(const std::vector<TParticle>& particles)
{
  for (auto& particle : particles)
    particle.Print();
}
