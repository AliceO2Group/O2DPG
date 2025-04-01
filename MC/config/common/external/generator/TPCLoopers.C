#include <onnxruntime_cxx_api.h>
#include <iostream>
#include <vector>
#include <fstream>
#include <rapidjson/document.h>
#include <TMatrixT.h>

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
        for (int i = 0; i < 10; ++i)
        {
            if (i < 8)
                output.push_back(input[i] * (normal_max[i] - normal_min[i]) + normal_min[i]);
            else
                output.push_back(input[i] * outlier_scale[i - 8] + outlier_center[i - 8]);
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
    ONNXGenerator(const std::string &model_path)
        : env(ORT_LOGGING_LEVEL_WARNING, "ONNXGenerator"), session(env, model_path.c_str(), Ort::SessionOptions{})
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
        std::vector<double> output;
        for (int i = 0; i < 10; ++i)
        {
            output.push_back(output_data[i]);
        }

        return output;
    }

private:
    Ort::Env env;
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
    GenTPCLoopers(std::string model = "tpcloopmodel.onnx", std::string poisson = "poisson.csv", std::string scaler = "scaler.json")
    {
        // Checking if the model file exists and it's not empty
        std::ifstream model_file(model);
        if (!model_file.is_open() || model_file.peek() == std::ifstream::traits_type::eof())
        {
            LOG(fatal) << "Error: Model file is empty or does not exist!";
        }
        // Checking if the scaler file exists and it's not empty
        std::ifstream scaler_file(scaler);
        if (!scaler_file.is_open() || scaler_file.peek() == std::ifstream::traits_type::eof())
        {
            LOG(fatal) << "Error: Scaler file is empty or does not exist!";
        }
        // Checking if the poisson file exists and it's not empty
        if (poisson != "")
        {
            std::ifstream poisson_file(poisson);
            if (!poisson_file.is_open() || poisson_file.peek() == std::ifstream::traits_type::eof())
            {
                LOG(fatal) << "Error: Poisson file is empty or does not exist!";
                exit(1);
            } else {
                poisson_file >> mPoisson[0] >> mPoisson[1] >> mPoisson[2];
                poisson_file.close();
                mPoissonSet = true;
            }

        }
        mONNX = std::make_unique<ONNXGenerator>(model);
        mScaler = std::make_unique<Scaler>();
        mScaler->load(scaler);
        Generator::setTimeUnit(1.0);
        Generator::setPositionUnit(1.0);
    }
    
    Bool_t generateEvent() override
    {   
        // Clear the vector of pairs
        mGenPairs.clear();
        // Set number of loopers if poissonian params are available
        if (mPoissonSet)
        {
            mNLoopers = PoissonPairs();
        }
        // Generate pairs of loopers
        for (int i = 0; i < mNLoopers; ++i)
        {
            std::vector<double> pair = mONNX->generate_sample();
            // Apply the inverse transformation using the scaler
            std::vector<double> transformed_pair = mScaler->inverse_transform(pair);
            mGenPairs.push_back(transformed_pair);
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

    void SetNLoopers(short int nsig)
    {
        if(mPoissonSet) {
            LOG(warn) << "Poissonian parameters correctly set, ignoring SetNLoopers.";
        } else {
            mNLoopers = nsig;
        }
    }

    private:
        std::unique_ptr<ONNXGenerator> mONNX = nullptr;
        std::unique_ptr<Scaler> mScaler = nullptr;
        double mPoisson[3] = {0.0, 0.0, 0.0}; // Mu, Min and Max of Poissonian
        std::vector<std::vector<double>> mGenPairs;
        short int mNLoopers = -1;
        bool mPoissonSet = false;
        // Poissonian random number generator
        TRandom3 mRandGen;
        // Masses of the electrons and positrons
        TDatabasePDG *mPDG = TDatabasePDG::Instance();
        double mMass_e = mPDG->GetParticle(11)->Mass();
        double mMass_p = mPDG->GetParticle(-11)->Mass();
};

} // namespace eventgen
} // namespace o2

FairGenerator *
    Generator_TPCLoopers(std::string model = "tpcloopmodel.onnx", std::string poisson = "poisson.csv", std::string scaler = "scaler.json", short int nloopers = 1)
{
    // Expand all environment paths
    model = gSystem->ExpandPathName(model.c_str());
    poisson = gSystem->ExpandPathName(poisson.c_str());
    scaler = gSystem->ExpandPathName(scaler.c_str());
    auto generator = new o2::eventgen::GenTPCLoopers(model, poisson, scaler);
    generator->SetNLoopers(nloopers);
    return generator;
}