R__LOAD_LIBRARY(libpythia6)

namespace o2
{
namespace eventgen
{

class O2_GeneratorParam : public GeneratorTGenerator
{

 public:
  O2_GeneratorParam() : GeneratorTGenerator("Param")
  {
    param = new GeneratorParam(10, new GeneratorParamMUONlib(), GeneratorParamMUONlib::kJpsiFamily, "Vogt PbPb");
    param->SetPtRange(0, 100);
    param->SetYRange(-1., +1.);
    param->SetDecayer(new TPythia6Decayer());
    param->SetForceDecay(kDiElectron);
    setTGenerator(param);
  };

  ~O2_GeneratorParam()
  {
    delete param;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    param->Init();
    return true;
  }

 private:
  GeneratorParam* param = nullptr;
};

} // namespace eventgen
} // namespace o2

FairGenerator*
  Get_O2_GeneratorParam()
{
  return new o2::eventgen::O2_GeneratorParam;
}
