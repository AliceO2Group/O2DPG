#include <onnxruntime_cxx_api.h>
#include <iostream>
#include <vector>
#include <fstream>
#include <rapidjson/document.h>
#include "CCDB/CCDBTimeStampUtils.h"
#include "CCDB/CcdbApi.h"

// Static Ort::Env instance for multiple onnx model loading
static Ort::Env global_env(ORT_LOGGING_LEVEL_WARNING, "GlobalEnv");

// This class is responsible for loading the scaler parameters from a JSON file
// and applying the inverse transformation to the generated data.
struct Scaler
{
    std::vector<double> normal_min;
    std::vector<double> normal_max;
    std::vector<double> outlier_center;
    std::vector<double> outlier_scale;

    void load(const std::string &filename)
    {
        std::ifstream file(filename);
        if (!file.is_open())
        {
            throw std::runtime_error("Error: Could not open scaler file!");
        }

        std::string json_str((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        file.close();

        rapidjson::Document doc;
        doc.Parse(json_str.c_str());

        if (doc.HasParseError())
        {
            throw std::runtime_error("Error: JSON parsing failed!");
        }

        normal_min = jsonArrayToVector(doc["normal"]["min"]);
        normal_max = jsonArrayToVector(doc["normal"]["max"]);
        outlier_center = jsonArrayToVector(doc["outlier"]["center"]);
        outlier_scale = jsonArrayToVector(doc["outlier"]["scale"]);
    }

    std::vector<double> inverse_transform(const std::vector<double> &input)
    {
        std::vector<double> output;
        for (int i = 0; i < input.size(); ++i)
        {
            if (i < input.size() - 2)
                output.push_back(input[i] * (normal_max[i] - normal_min[i]) + normal_min[i]);
            else
                output.push_back(input[i] * outlier_scale[i - (input.size() - 2)] + outlier_center[i - (input.size() - 2)]);
        }

        return output;
    }

private:
    std::vector<double> jsonArrayToVector(const rapidjson::Value &jsonArray)
    {
        std::vector<double> vec;
        for (int i = 0; i < jsonArray.Size(); ++i)
        {
            vec.push_back(jsonArray[i].GetDouble());
        }
        return vec;
    }
};

// This class loads the ONNX model and generates samples using it.
class ONNXGenerator
{
public:
    ONNXGenerator(Ort::Env &shared_env, const std::string &model_path)
        : env(shared_env), session(env, model_path.c_str(), Ort::SessionOptions{})
    {
        // Create session options
        Ort::SessionOptions session_options;
        session = Ort::Session(env, model_path.c_str(), session_options);
    }

    std::vector<double> generate_sample()
    {
        Ort::AllocatorWithDefaultOptions allocator;

        // Generate a latent vector (z)
        std::vector<float> z(100);
        for (auto &v : z)
            v = rand_gen.Gaus(0.0, 1.0);

        // Prepare input tensor
        std::vector<int64_t> input_shape = {1, 100};
        // Get memory information
        Ort::MemoryInfo memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

        // Create input tensor correctly
        Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
            memory_info, z.data(), z.size(), input_shape.data(), input_shape.size());
        // Run inference
        const char *input_names[] = {"z"};
        const char *output_names[] = {"output"};
        auto output_tensors = session.Run(Ort::RunOptions{nullptr}, input_names, &input_tensor, 1, output_names, 1);

        // Extract output
        float *output_data = output_tensors.front().GetTensorMutableData<float>();
        // Get the size of the output tensor
        auto output_tensor_info = output_tensors.front().GetTensorTypeAndShapeInfo();
        size_t output_data_size = output_tensor_info.GetElementCount(); // Total number of elements in the tensor
        std::vector<double> output;
        for (int i = 0; i < output_data_size; ++i)
        {
            output.push_back(output_data[i]);
        }

        return output;
    }

private:
    Ort::Env &env;
    Ort::Session session;
    TRandom3 rand_gen;
};

namespace o2
{
namespace eventgen
{

class GenTPCLoopers : public Generator
{
    public:
        GenTPCLoopers(std::string model_pairs = "tpcloopmodel.onnx", std::string model_compton = "tpcloopmodelcompton.onnx",
                      std::string poisson = "poisson.csv", std::string gauss = "gauss.csv", std::string scaler_pair = "scaler_pair.json",
                      std::string scaler_compton = "scaler_compton.json")
        {
            // Checking if the model files exist and are not empty
            std::ifstream model_file[2];
            model_file[0].open(model_pairs);
            model_file[1].open(model_compton);
            if (!model_file[0].is_open() || model_file[0].peek() == std::ifstream::traits_type::eof())
            {
                LOG(fatal) << "Error: Pairs model file is empty or does not exist!";
                exit(1);
            }
            if (!model_file[1].is_open() || model_file[1].peek() == std::ifstream::traits_type::eof())
            {
                LOG(fatal) << "Error: Compton model file is empty or does not exist!";
                exit(1);
            }
            model_file[0].close();
            model_file[1].close();
            // Checking if the scaler files exist and are not empty
            std::ifstream scaler_file[2];
            scaler_file[0].open(scaler_pair);
            scaler_file[1].open(scaler_compton);
            if (!scaler_file[0].is_open() || scaler_file[0].peek() == std::ifstream::traits_type::eof())
            {
                LOG(fatal) << "Error: Pairs scaler file is empty or does not exist!";
                exit(1);
            }
            if (!scaler_file[1].is_open() || scaler_file[1].peek() == std::ifstream::traits_type::eof())
            {
                LOG(fatal) << "Error: Compton scaler file is empty or does not exist!";
                exit(1);
            }
            scaler_file[0].close();
            scaler_file[1].close();
            // Checking if the poisson file exists and it's not empty
            if (poisson != "")
            {
                std::ifstream poisson_file(poisson);
                if (!poisson_file.is_open() || poisson_file.peek() == std::ifstream::traits_type::eof())
                {
                    LOG(fatal) << "Error: Poisson file is empty or does not exist!";
                    exit(1);
                }
                else
                {
                    poisson_file >> mPoisson[0] >> mPoisson[1] >> mPoisson[2];
                    poisson_file.close();
                    mPoissonSet = true;
                }
            }
            // Checking if the gauss file exists and it's not empty
            if (gauss != "")
            {
                std::ifstream gauss_file(gauss);
                if (!gauss_file.is_open() || gauss_file.peek() == std::ifstream::traits_type::eof())
                {
                    LOG(fatal) << "Error: Gauss file is empty or does not exist!";
                    exit(1);
                }
                else
                {
                    gauss_file >> mGauss[0] >> mGauss[1] >> mGauss[2] >> mGauss[3];
                    gauss_file.close();
                    mGaussSet = true;
                }
            }
            mONNX_pair = std::make_unique<ONNXGenerator>(global_env, model_pairs);
            mScaler_pair = std::make_unique<Scaler>();
            mScaler_pair->load(scaler_pair);
            mONNX_compton = std::make_unique<ONNXGenerator>(global_env, model_compton);
            mScaler_compton = std::make_unique<Scaler>();
            mScaler_compton->load(scaler_compton);
            Generator::setTimeUnit(1.0);
            Generator::setPositionUnit(1.0);
        }
    
        Bool_t generateEvent() override
        {   
            // Clear the vector of pairs
            mGenPairs.clear();
            // Clear the vector of compton electrons
            mGenElectrons.clear();
            // Set number of loopers if poissonian params are available
            if (mPoissonSet)
            {
                mNLoopersPairs = static_cast<short int>(std::round(mMultiplier[0] * PoissonPairs()));
            }
            if (mGaussSet)
            {
                mNLoopersCompton = static_cast<short int>(std::round(mMultiplier[1] * GaussianElectrons()));
            }
            // Generate pairs
            for (int i = 0; i < mNLoopersPairs; ++i)
            {
                std::vector<double> pair = mONNX_pair->generate_sample();
                // Apply the inverse transformation using the scaler
                std::vector<double> transformed_pair = mScaler_pair->inverse_transform(pair);
                mGenPairs.push_back(transformed_pair);
            }
            // Generate compton electrons
            for (int i = 0; i < mNLoopersCompton; ++i)
            {
                std::vector<double> electron = mONNX_compton->generate_sample();
                // Apply the inverse transformation using the scaler
                std::vector<double> transformed_electron = mScaler_compton->inverse_transform(electron);
                mGenElectrons.push_back(transformed_electron);
            }
            return true;
        }

        Bool_t importParticles() override
        {
            // Get looper pairs from the event
            for (auto &pair : mGenPairs)
            {
                double px_e, py_e, pz_e, px_p, py_p, pz_p;
                double vx, vy, vz, time;
                double e_etot, p_etot;
                px_e = pair[0];
                py_e = pair[1];
                pz_e = pair[2];
                px_p = pair[3];
                py_p = pair[4];
                pz_p = pair[5];
                vx = pair[6];
                vy = pair[7];
                vz = pair[8];
                time = pair[9];
                e_etot = TMath::Sqrt(px_e * px_e + py_e * py_e + pz_e * pz_e + mMass_e * mMass_e);
                p_etot = TMath::Sqrt(px_p * px_p + py_p * py_p + pz_p * pz_p + mMass_p * mMass_p);
                // Push the electron
                TParticle electron(11, 1, -1, -1, -1, -1, px_e, py_e, pz_e, e_etot, vx, vy, vz, time / 1e9);
                electron.SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(electron.GetStatusCode(), 0).fullEncoding);
                electron.SetBit(ParticleStatus::kToBeDone, //
                                o2::mcgenstatus::getHepMCStatusCode(electron.GetStatusCode()) == 1);
                mParticles.push_back(electron);
                // Push the positron
                TParticle positron(-11, 1, -1, -1, -1, -1, px_p, py_p, pz_p, p_etot, vx, vy, vz, time / 1e9);
                positron.SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(positron.GetStatusCode(), 0).fullEncoding);
                positron.SetBit(ParticleStatus::kToBeDone, //
                                o2::mcgenstatus::getHepMCStatusCode(positron.GetStatusCode()) == 1);
                mParticles.push_back(positron);
            }
            // Get compton electrons from the event
            for (auto &compton : mGenElectrons)
            {
                double px, py, pz;
                double vx, vy, vz, time;
                double etot;
                px = compton[0];
                py = compton[1];
                pz = compton[2];
                vx = compton[3];
                vy = compton[4];
                vz = compton[5];
                time = compton[6];
                etot = TMath::Sqrt(px * px + py * py + pz * pz + mMass_e * mMass_e);
                // Push the electron
                TParticle electron(11, 1, -1, -1, -1, -1, px, py, pz, etot, vx, vy, vz, time / 1e9);
                electron.SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(electron.GetStatusCode(), 0).fullEncoding);
                electron.SetBit(ParticleStatus::kToBeDone, //
                                o2::mcgenstatus::getHepMCStatusCode(electron.GetStatusCode()) == 1);
                mParticles.push_back(electron);
            }

            return true;
        }

        short int PoissonPairs()
        {
            short int poissonValue;
            do
            {
                // Generate a Poisson-distributed random number with mean mPoisson[0]
                poissonValue = mRandGen.Poisson(mPoisson[0]);
            } while (poissonValue < mPoisson[1] || poissonValue > mPoisson[2]); // Regenerate if out of range

            return poissonValue;
        }

        short int GaussianElectrons()
        {
            short int gaussValue;
            do
            {
                // Generate a Normal-distributed random number with mean mGass[0] and stddev mGauss[1]
                gaussValue = mRandGen.Gaus(mGauss[0], mGauss[1]);
            } while (gaussValue < mGauss[2] || gaussValue > mGauss[3]); // Regenerate if out of range

            return gaussValue;
        }

        void SetNLoopers(short int &nsig_pair, short int &nsig_compton)
        {
            if(mPoissonSet) {
                LOG(info) << "Poissonian parameters correctly loaded.";
            } else {
                mNLoopersPairs = nsig_pair;
            }
            if(mGaussSet) {
                LOG(info) << "Gaussian parameters correctly loaded.";
            } else {
                mNLoopersCompton = nsig_compton;
            }
        }

        void SetMultiplier(std::array<float, 2> &mult)
        {
            // Multipliers will work only if the poissonian and gaussian parameters are set
            // otherwise they will be ignored
            if (mult[0] < 0 || mult[1] < 0)
            {
                LOG(fatal) << "Error: Multiplier values must be non-negative!";
                exit(1);
            } else {
                LOG(info) << "Multiplier values set to: Pair = " << mult[0] << ", Compton = " << mult[1];
                mMultiplier[0] = mult[0];
                mMultiplier[1] = mult[1];
            }
        }

    private:
        std::unique_ptr<ONNXGenerator> mONNX_pair = nullptr;
        std::unique_ptr<ONNXGenerator> mONNX_compton = nullptr;
        std::unique_ptr<Scaler> mScaler_pair = nullptr;
        std::unique_ptr<Scaler> mScaler_compton = nullptr;
        double mPoisson[3] = {0.0, 0.0, 0.0}; // Mu, Min and Max of Poissonian
        double mGauss[4] = {0.0, 0.0, 0.0, 0.0}; // Mean, Std, Min, Max
        std::vector<std::vector<double>> mGenPairs;
        std::vector<std::vector<double>> mGenElectrons;
        short int mNLoopersPairs = -1;
        short int mNLoopersCompton = -1;
        std::array<float, 2> mMultiplier = {1., 1.};
        bool mPoissonSet = false;
        bool mGaussSet = false;
        // Random number generator
        TRandom3 mRandGen;
        // Masses of the electrons and positrons
        TDatabasePDG *mPDG = TDatabasePDG::Instance();
        double mMass_e = mPDG->GetParticle(11)->Mass();
        double mMass_p = mPDG->GetParticle(-11)->Mass();
};

} // namespace eventgen
} // namespace o2

// ONNX model files can be local, on AliEn or in the ALICE CCDB.
// For local and alien files it is mandatory to provide the filenames, for the CCDB instead the
// path to the object in the CCDB is sufficient. The model files will be downloaded locally.
// Example of CCDB path: "ccdb://Users/n/name/test"
// Example of alien path: "alien:///alice/cern.ch/user/n/name/test/test.onnx"
FairGenerator *
    Generator_TPCLoopers(std::string model_pairs = "tpcloopmodel.onnx", std::string model_compton = "tpcloopmodelcompton.onnx",
                         std::string poisson = "poisson.csv", std::string gauss = "gauss.csv", std::string scaler_pair = "scaler_pair.json",
                         std::string scaler_compton = "scaler_compton.json", std::array<float, 2> mult = {1., 1.}, short int nloopers_pairs = 1,
                         short int nloopers_compton = 1)
{
    // Expand all environment paths
    model_pairs = gSystem->ExpandPathName(model_pairs.c_str());
    model_compton = gSystem->ExpandPathName(model_compton.c_str());
    poisson = gSystem->ExpandPathName(poisson.c_str());
    gauss = gSystem->ExpandPathName(gauss.c_str());
    scaler_pair = gSystem->ExpandPathName(scaler_pair.c_str());
    scaler_compton = gSystem->ExpandPathName(scaler_compton.c_str());
    const std::array<std::string, 2> models = {model_pairs, model_compton};
    const std::array<std::string, 2> local_names = {"WGANpair.onnx", "WGANcompton.onnx"};
    const std::array<bool, 2> isAlien = {models[0].starts_with("alien://"), models[1].starts_with("alien://")};
    const std::array<bool, 2> isCCDB = {models[0].starts_with("ccdb://"), models[1].starts_with("ccdb://")};
    if (std::any_of(isAlien.begin(), isAlien.end(), [](bool v) { return v; }))
    {
        if (!gGrid) {
            TGrid::Connect("alien://");
            if (!gGrid) {
                LOG(fatal) << "AliEn connection failed, check token.";
                exit(1);
            }
        }
        for (size_t i = 0; i < models.size(); ++i)
        {
            if (isAlien[i] && !TFile::Cp(models[i].c_str(), local_names[i].c_str()))
            {
                LOG(fatal) << "Error: Model file " << models[i] << " does not exist!";
                exit(1);
            }
        }
    }
    if (std::any_of(isCCDB.begin(), isCCDB.end(), [](bool v) { return v; }))
    {
        o2::ccdb::CcdbApi ccdb_api;
        ccdb_api.init("http://alice-ccdb.cern.ch");
        for (size_t i = 0; i < models.size(); ++i)
        {
            if (isCCDB[i])
            {
                auto model_path = models[i].substr(7); // Remove "ccdb://"
                // Treat filename if provided in the CCDB path
                auto extension = model_path.find(".onnx");
                if (extension != std::string::npos)
                {
                    auto last_slash = model_path.find_last_of('/');
                    model_path = model_path.substr(0, last_slash);
                }
                std::map<std::string, std::string> filter;
                if(!ccdb_api.retrieveBlob(model_path, "./" , filter, o2::ccdb::getCurrentTimestamp(), false, local_names[i].c_str()))
                {
                    LOG(fatal) << "Error: issues in retrieving " << model_path << " from CCDB!";
                    exit(1);
                }
            }
        }
    }
    model_pairs = isAlien[0] || isCCDB[0] ? local_names[0] : model_pairs;
    model_compton = isAlien[1] || isCCDB[1] ? local_names[1] : model_compton;
    auto generator = new o2::eventgen::GenTPCLoopers(model_pairs, model_compton, poisson, gauss, scaler_pair, scaler_compton);
    generator->SetNLoopers(nloopers_pairs, nloopers_compton);
    generator->SetMultiplier(mult);
    return generator;
}