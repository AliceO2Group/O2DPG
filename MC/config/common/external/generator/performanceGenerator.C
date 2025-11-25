// External generator requested in https://its.cern.ch/jira/browse/O2-6235
// for multidimensional performance studies
// Example usage:
// o2-sim -j 8 -o test -n 100 --seed 612 -g hybrid --configKeyValues "GeneratorHybrid.configFile=${O2DPG_MC_CONFIG_ROOT}/MC/config/common/external/generator/perfConf.json"
namespace o2
{
    namespace eventgen
    {

        class GenPerf : public Generator
        {
        public:
            GenPerf(float fraction = 0.03f, unsigned short int nsig = 100, unsigned short int tag = 1)
            {
                if (fraction == -1) {
                    LOG(info) << nsig << " Signal particles will be generated in each event";
                    mNSig = nsig;
                    mFraction = -1.f;
                } else if (fraction >= 0) {
                    LOG(info) << "Fraction based signal generation is enabled";
                    LOG(info) << fraction << "*nUE tracks per event will be generated";
                    mFraction = fraction;
                } else {
                    LOG(fatal) << "Wrong fraction selected. Accepted values are:";
                    LOG(fatal) << "\t -1 => fixed number of tracks per event";
                    LOG(fatal) << ">=0 => fraction based signal generation over the number of UE tracks per event";
                    exit(1);
                }
                initGenMap();
                if (genMap.find(tag) == genMap.end()) {
                    LOG(fatal) << "Wrong tag selected. Accepted values are:";
                    for (const auto& [key, _] : genMap) {
                        LOG(fatal) << "\t" << key;
                    }
                    exit(1);
                } else {
                    mTag = tag;
                    LOG(info) << "Generator with tag " << mTag << " is selected";
                }
                LOG(info) << "Z0 decays are handled with Pythia8";
                mPythia = std::make_unique<Pythia8::Pythia>();
                // Turn off all event generation - we only want to decay our Z0
                mPythia->readString("ProcessLevel:all = off");
                // Disable standard event checks since we're manually building the event
                mPythia->readString("Check:event = off");
                mPythia->init(); // Initialize
                Generator::setTimeUnit(1.0);
                Generator::setPositionUnit(1.0);
            }

            Bool_t generateEvent() override
            {
                return kTRUE;
            }

            Bool_t importParticles() override
            {
                mNUE = 0;
                if ( mFraction != -1) {
                    // This line assumes that the current generator is run in a cocktail with another generator
                    // which is run before the current one in a sequential way
                    if (!mGenList) {
                        auto &hybridInstance = GeneratorHybrid::Instance();
                        mGenList = &hybridInstance.getGenerators();
                    }
                    if (!mGenList->empty()) {
                        mNUE = mGenList->front()->getParticles().size();
                        LOG(debug) << "Number of tracks from UE is " << mNUE;
                    }
                }
                unsigned short nSig = (mFraction == -1) ? mNSig : std::lround(mFraction * mNUE);
                LOG(debug) << "Generating additional " << nSig << " particles";
                for (int k = 0; k < nSig; k++){
                    auto part = genMap[mTag]();
                    if(part.GetPdgCode() == 23) {
                        auto daughters = decayZ0(part);
                        for (auto &dau : daughters)
                        {
                            mParticles.push_back(dau);
                        }
                    } else {
                        mParticles.push_back(part);
                    }
                }
                return kTRUE;
            }

        private:
            float mFraction = 0.03f;    // Fraction based generation
            unsigned short int mNSig = 0;   // Number of particles to generate
            unsigned int mNUE = 0;  // Number of tracks in the Underlying event
            unsigned short int mTag = 1; // Tag to select the generation function
            std::unique_ptr<Pythia8::Pythia> mPythia; // Pythia8 instance for particle decays not present in the physics list of Geant4 (like Z0)
            const std::vector<std::shared_ptr<o2::eventgen::Generator>>* mGenList = nullptr; // Cached generators list
            std::map<unsigned short int, std::function<TParticle()>> genMap;
            UInt_t mGenID = 42;

            // This is performance test generator with uniform weighting for PDG
            TParticle generateParticle0()
            {
                // 1. Get the singleton instances
                TDatabasePDG *pdg = TDatabasePDG::Instance();
                // 2. Define the list of PDG codes
                const int ncodes = 13;
                const int pdgCodes[ncodes] = {
                    310,          // K0_s
                    421,          // D0
                    3122,         // Lambda
                    -3122,        // Anti-Lambda
                    443,          // J/psi
                    13,           // mu-
                    22,           // gamma
                    23,           // Z0
                    1, 2, 3, 4, 5 // Quarks: d, u, s, c, b (t-quark is 6, often excluded for kinematics)
                };
                // 3. Randomly select and validate a PDG code
                // TMath::Nint(gRandom->Rndm() * ncodes) selects an index from 0 to ncodes-1 safely.
                int index = TMath::Nint(gRandom->Rndm() * (ncodes - 1));
                int pdgCode = pdgCodes[index];
                // Check if the particle exists and switch to antiparticle if needed
                if (pdg->GetParticle(pdgCode) == nullptr)
                {
                    if (pdg->GetParticle(-pdgCode) != nullptr)
                    {
                        pdgCode *= -1; // Use the negative code (antiparticle)
                    }
                    else
                    {
                        LOG(error) << "Error: PDG code " << pdgCode << " not found in TDatabasePDG. Using Muon (13).";
                        pdgCode = 13;
                    }
                }
                // 4. Generate Kinematics (p_T, phi, eta)
                float pt = 1 / (gRandom->Rndm()); // flat 1/pt distribution
                float phi = gRandom->Rndm() * 2.0f * TMath::Pi();
                float eta = 3.0f * (gRandom->Rndm() - 0.5f); // eta from -1.5 to 1.5
                // Initial position (origin)
                float xyz[3] = {0.0f, 0.0f, 0.0f};
                // if cosmic, you might want to randomize the vertex position
                if (pdgCode == 13 || pdgCode == -13)
                {
                    xyz[0] = (gRandom->Rndm() - 0.5) * 300.0f; // x from -100 to 100 cm
                    xyz[1] = (gRandom->Rndm() - 0.5) * 300.0f; // y from -100 to 100 cm
                    xyz[2] = 400;
                    pt = 1 / (gRandom->Rndm() + 0.01);
                    eta = gRandom->Gaus() * 0.2;
                }
                //
                // Convert spherical coordinates (pt, phi, eta) to Cartesian (px, py, pz)
                float pz = pt * TMath::SinH(eta);
                float px = pt * TMath::Cos(phi);
                float py = pt * TMath::Sin(phi);
                // 5. Calculate Energy (E) from Mass (M)
                TParticlePDG *particleInfo = pdg->GetParticle(pdgCode);
                double mass = particleInfo ? particleInfo->Mass() : 0.1056; // Default to muon mass if lookup fails
                double energy = TMath::Sqrt(px * px + py * py + pz * pz + mass * mass);

                // 6. Create and return the TParticle object by value
                // TParticle(pdgCode, trackIndex, Mother, Daughter1, Daughter2, Px, Py, Pz, E, Vx, Vy, Vz, Time)
                int status = -1; // Status code, -1 for undefined
                // Set your custom performance generator ID (e.g., ID 42)
                TParticle generatedParticle(pdgCode, status, -1, -1, -1, -1, px, py, pz, energy, xyz[0], xyz[1], xyz[2], 0.0);
                generatedParticle.SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(generatedParticle.GetStatusCode(), 0).fullEncoding);
                generatedParticle.SetUniqueID(mGenID);
                if (pdgCode == 23) {
                    generatedParticle.SetBit(ParticleStatus::kToBeDone, false); // Force Z0 to be decayed by the transport
                } else {
                    generatedParticle.SetBit(ParticleStatus::kToBeDone, //
                                             o2::mcgenstatus::getHepMCStatusCode(generatedParticle.GetStatusCode()) == 1);
                }
                return generatedParticle;
            }

            // Particle configuration for ALICE O2 performance testing
            struct ParticleSpec
            {
                int pdgCode;
                float fraction; // Relative probability for probe statistics
                float pTScale;  // Scales pt
            };

            // Optimized for rare probes (J/psi, D0, jets) with flat distributions
            const std::vector<ParticleSpec> g_particle_specs = {
                // PDG  | Fraction | pTScale
                {22, 1.0f, 1.0f},    // Photon: High yield for PID/calo
                {13, 1.f, 1.0f},     // Muon: Cosmic override applied
                {-13, 1.f, 1.0f},    // Anti-muon
                {23, 0.1f, 10.0f},   // Z0: Rare,
                {310, 1.f, 1.0f},    // K0_s: Common hadron
                {421, 0.2f, 1.5f},   // D0
                {443, 0.1f, 5.0f},   // J/psi: Boosted for candle
                {3122, 0.5f, 1.0f},  // Lambda
                {-3122, 0.5f, 1.0f}, // Anti-Lambda
                {211, 1.0f, 1.0f},   // Pi+
                {-211, 1.0f, 1.0f},  // Pi-:
                //
                {21, 0.1f, 3.0f}, // Gluon: Jet proxy (status=11)
                {1, 0.1f, 3.0f},  // d quark: Jet proxy
                {-1, 0.1f, 3.0f}, // anti-d
                {2, 0.1f, 3.0f},  // u quark: Jet proxy
                {-2, 0.1f, 3.0f}, // anti-u
                {3, 0.1f, 5.0f},  // s quark: Strange
                {-3, 0.1f, 5.0f}, // anti-s
                {4, 0.1f, 5.0f},  // c quark: Heavy flavor
                {-4, 0.1f, 5.0f}, // anti-c
                {5, 0.1f, 8.0f},  // b quark: Very hard
                {-5, 0.1f, 8.0f}  // anti-b
            };

            // pT bounds: Max pT ~5 TeV (ALICE Pb-Pb energy)
            const float kMaxInvPt = 1.0f;      // Min pT = 1 GeV
            const float kBaseMinInvPt = 2e-4f; // Max pT = 5000 GeV (unscaled)

            // Check if particle is a parton (quark/gluon, status=11)
            bool isParton(int& pdgCode)
            {
                int absCode = TMath::Abs(pdgCode);
                return (absCode >= 1 && absCode <= 5) || absCode == 21;
            }

            // Generator for flat distributions in pT, eta for calibration
            TParticle generateParticle1()
            {
                TDatabasePDG *pdg = TDatabasePDG::Instance();
                // 1. Weighted Random Selection
                static float totalWeight = 0.0f;
                if (totalWeight == 0.0f)
                {
                    totalWeight = std::accumulate(g_particle_specs.begin(), g_particle_specs.end(), 0.0f,
                                                  [](float sum, const ParticleSpec &spec)
                                                  { return sum + spec.fraction; });
                }
                float randVal = gRandom->Rndm() * totalWeight;
                float cumulativeWeight = 0.0f;
                const ParticleSpec *selectedSpec = nullptr;
                for (const auto &spec : g_particle_specs)
                {
                    cumulativeWeight += spec.fraction;
                    if (randVal <= cumulativeWeight)
                    {
                        selectedSpec = &spec;
                        break;
                    }
                }
                if (!selectedSpec)
                    selectedSpec = &g_particle_specs.back();
                int pdgCode = selectedSpec->pdgCode;
                float pTScale = selectedSpec->pTScale;
                // 2. PDG Validation
                if (!pdg->GetParticle(pdgCode))
                {
                    if (pdg->GetParticle(-pdgCode))
                        pdgCode *= -1;
                    else
                    {
                        LOG(error) << "Error: PDG " << pdgCode << " not found. Using muon (13).\n";
                        pdgCode = 13;
                        pTScale = 1.0f;
                    }
                }
                // 3. Status: 11 for partons (jets), 1 for final-state
                int status = isParton(pdgCode) ? 11 : 1;
                // 4. Kinematics (flat 1/pT, max ~5000 GeV / pTScale)
                float min_inv_pt = kBaseMinInvPt / pTScale; // E.g., max pT=40,000 GeV for b quarks
                float inv_pt = (gRandom->Rndm() / pTScale) * (kMaxInvPt - min_inv_pt) + min_inv_pt;
                float pt = 1.0f / inv_pt;
                float phi = gRandom->Rndm() * 2.0f * TMath::Pi();
                float eta = gRandom->Rndm() * 3.0f - 1.5f; // ALICE TPC: -1.5 to 1.5
                // Vertex: Delta (embedding handles smearing)
                float xyz[3] = {0.0f, 0.0f, 0.0f};
                // 5. Cosmic Muon Override
                if (TMath::Abs(pdgCode) == 13)
                {
                    xyz[0] = (gRandom->Rndm() - 0.5f) * 300.0f;
                    xyz[1] = (gRandom->Rndm() - 0.5f) * 300.0f;
                    xyz[2] = 400.0f;
                    inv_pt = (gRandom->Rndm() + 0.01f) / pTScale; // Apply pTScale
                    pt = 1.0f / inv_pt;
                    eta = TMath::Max(-4.0, TMath::Min(4.0, gRandom->Gaus(0.0, 0.2)));
                    status = 1;
                }
                // 6. Momentum and Energy
                float pz = pt * TMath::SinH(eta);
                float px = pt * TMath::Cos(phi);
                float py = pt * TMath::Sin(phi);
                TParticlePDG *particleInfo = pdg->GetParticle(pdgCode);
                double mass = particleInfo ? particleInfo->Mass() : 0.1056;
                double energy = TMath::Sqrt(px * px + py * py + pz * pz + mass * mass);
                // 7. TParticle Creation (quarks/gluons need fragmentation in O2)
                TParticle generatedParticle(pdgCode, status, -1, -1, -1, -1, px, py, pz, energy, xyz[0], xyz[1], xyz[2], 0.0);
                generatedParticle.SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(generatedParticle.GetStatusCode(), 0).fullEncoding);
                generatedParticle.SetUniqueID(mGenID);
                if (pdgCode == 23) {
                    generatedParticle.SetBit(ParticleStatus::kToBeDone, false);
                    // Z0 will follow another decay procedure
                } else {
                    generatedParticle.SetBit(ParticleStatus::kToBeDone, //
                                             o2::mcgenstatus::getHepMCStatusCode(generatedParticle.GetStatusCode()) == 1);
                }
                return generatedParticle;
            }

            void initGenMap()
            {
                genMap[0] = [this]()
                { return generateParticle0(); };
                genMap[1] = [this]()
                { return generateParticle1(); };
            }

            std::vector<TParticle> decayZ0(TParticle &z0)
            {
                std::vector<TParticle> subparts;
                auto &event = mPythia->event;
                // Reset event record for new decay
                event.reset();
                // Add the Z0 particle to the event record
                // Arguments: id, status, mother1, mother2, daughter1, daughter2,
                //            col, acol, px, py, pz, e, m, scale, pol
                // Status code: 91 = incoming particles (needed for proper decay handling)
                int iZ0 = event.append(23, 91, 0, 0, 0, 0, 0, 0,
                                       z0.Px(), z0.Py(), z0.Pz(), z0.Energy(), z0.GetMass());
                // Set production vertex
                event[iZ0].vProd(z0.Vx(), z0.Vy(), z0.Vz(), 0.0);
                // Forcing decay by calling hadron level function
                if (!mPythia->forceHadronLevel())
                {
                    cout << "Warning: Z0 decay failed!" << endl;
                }
                for (int j = 0; j < event.size(); ++j)
                {
                    const Pythia8::Particle &p = event[j];
                    if (p.id() == 23) // PDG code for Z0
                    {
                        // Push Z0 itself
                        subparts.push_back(TParticle(p.id(), p.status(),
                                                     -1, -1, -1, -1,
                                                     p.px(), p.py(),
                                                     p.pz(), p.e(),
                                                     z0.Vx(), z0.Vy(), z0.Vz(), 0.0));
                        subparts.back().SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(p.status(), 0).fullEncoding);
                        subparts.back().SetUniqueID(mGenID);
                        subparts.back().SetBit(ParticleStatus::kToBeDone, false);
                        // Navigate through intermediate Z0s to find final decay products
                        int iZ0 = j;
                        while (event[iZ0].daughter1() != 0 &&
                               event[event[iZ0].daughter1()].id() == 23)
                        {
                            iZ0 = event[iZ0].daughter1();
                        }
                        // Recursively collect all final-state descendants
                        std::function<void(int)> collectAllDescendants = [&](int idx)
                        {
                            const Pythia8::Particle &particle = event[idx];
                            subparts.push_back(TParticle(particle.id(), particle.status(),
                                                         -1, -1, -1, -1,
                                                         particle.px(), particle.py(),
                                                         particle.pz(), particle.e(),
                                                         p.xProd(), p.yProd(), p.zProd(), p.tProd()));
                            subparts.back().SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(particle.status(), 0).fullEncoding);
                            subparts.back().SetUniqueID(mGenID + 1);
                            subparts.back().SetBit(ParticleStatus::kToBeDone,
                                                   o2::mcgenstatus::getHepMCStatusCode(subparts.back().GetStatusCode()) == 1);
                            // Not final-state, recurse through daughters
                            if (!particle.isFinal())
                            {
                                int d1 = particle.daughter1();
                                int d2 = particle.daughter2();
                                if (d1 > 0)
                                {
                                    for (int k = d1; k <= d2; ++k)
                                    {
                                        collectAllDescendants(k);
                                    }
                                }
                            }
                        };
                        // Start collecting from the final Z0
                        collectAllDescendants(iZ0);
                        break; // Found and processed the Z0
                    }
                }
                return subparts;
            }
        };

    } // namespace eventgen
} // namespace o2

// Performance test generator
// fraction == -1 enables the fixed number of signal particles per event (nsig)
// tag selects the generator type to be used
FairGenerator *
Generator_Performance(const float fraction = 0.03f, const unsigned short int nsig = 100, unsigned short int tag = 1)
{
    auto generator = new o2::eventgen::GenPerf(fraction, nsig, tag);
    return generator;
}