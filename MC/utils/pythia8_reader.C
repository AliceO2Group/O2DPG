void pythia8_reader(const char* fname, int version = 2);
void user_code(const std::vector<TParticle>& particles);

void
pythia8_reader(const char* fname, int nev = 1000)
{
  
  /** instance and initialise genarator Pythia8 **/
  auto reader = new o2::eventgen::GeneratorPythia8;
  reader->setConfig(fname);
  if (!reader->Init())
    return;
  
  /** loop over events **/
  for (int iev = 0;
       reader->generateEvent() && reader->importParticles() && iev < nev;
       ++iev) {
    
    /** get particles **/
    auto& particles = reader->getParticles();
    
    /** execute user code **/
    user_code(particles);
    
  }
  
}

void
user_code(const std::vector<TParticle>& particles)
{
  for (auto& particle : particles)
    particle.Print();
}

