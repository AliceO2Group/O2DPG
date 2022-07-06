#include <cmath>
#include <fmt/format.h>
#include <string_view>
#include <fstream>

#include "TSystem.h"

#include "CCDB/CcdbApi.h"
#include "DataFormatsTPC/LtrCalibData.h"
#include "TPCBase/ParameterGas.h"

float getTPCvdrift(int run, std::string_view ltrUrl = "http://alice-ccdb.cern.ch")
{
  o2::ccdb::CcdbApi c;
  c.init("http://alice-ccdb.cern.ch");
  std::map<std::string, std::string> headers, metadataRCT, metadata, mm;
  headers = c.retrieveHeaders(fmt::format("RCT/Info/RunInformation/{}", run), metadataRCT, -1);
  printf("\nLooking for vdrift for run %d\n", run);
  const auto sor = std::stol(headers["SOR"].data());

  const auto defaultDriftV = o2::tpc::ParameterGas::Instance().DriftV;

  std::string_view calibType = "TPC/Calib/LaserTracks";
  //
  // query present run up to +-3days
  const auto queryInterval = 3l * 24l * 60l * 60l * 1000l;
  const auto queryString = fmt::format("curl -H \"If-Not-Before: {}\" -H \"If-Not-After: {}\" -H \"Accept: application/json\" {}/browse/{}", sor - queryInterval, sor + queryInterval, ltrUrl.data(), calibType.data());
  fmt::print("Query: {}\n", queryString);
  const auto queryResultTString = gSystem->GetFromPipe(queryString.data());
  std::string queryResult(queryResultTString);

  // find closest entry in time
  long minDist = 9999999999999;
  long minTime = sor;
  size_t pos = 0;
  const std::string_view searchString("validFrom");
  while ((pos = queryResult.find(searchString.data(), pos)) < queryResult.size()) {
    const auto startPosTime = queryResult.find(":", pos) + 1;
    const auto endPosTime = queryResult.find(",", pos);
    const auto startValidity = std::atol(queryResult.substr(startPosTime, endPosTime - startPosTime).data());
    fmt::print("add object {}\n", startValidity);
    if (std::abs(startValidity - sor) < minDist) {
      minTime = startValidity;
      minDist = std::abs(startValidity - sor);
    }
    pos = endPosTime;
  }
  fmt::print("{} closest to {} is at {}\n", calibType, sor, minTime);

  //
  // Get object closest to present run and return the drfit veloctiy calibration factor
  c.init(ltrUrl.data());
  const auto ltrCalib = c.retrieveFromTFileAny<o2::tpc::LtrCalibData>(calibType.data(), metadata, minTime); /// timestamp in the run of interest
  const auto corr = ltrCalib->getDriftVCorrection();
  const float vcorr = defaultDriftV / corr;
  printf("vdrift = %f\n", vcorr);

  ofstream fp("vdrift.txt");
  fp << vcorr << endl;
  fp.close();

  return vcorr;
}
