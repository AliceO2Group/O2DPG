#include <map>
#include "TPCBase/ParameterGas.h"
#include "CCDB/CcdbApi.h"
#include "DataFormatsTPC/LtrCalibData.h"

float getTPCvdrift(int run, bool useCCDB) {

  o2::ccdb::CcdbApi c;
  c.init("http://alice-ccdb.cern.ch");
  long sor = 0;

  std::map<int, uint64_t> laserTimeStamp;
  laserTimeStamp[517035] = 1653640509000;
  laserTimeStamp[517037] = 1653641691000;
  laserTimeStamp[517039] = 1653643160000;
  laserTimeStamp[517040] = 1653644143000;
  laserTimeStamp[517041] = 1653646640000;
  laserTimeStamp[517043] = 1653649528000;
  laserTimeStamp[517044] = 1653650947000;
  laserTimeStamp[517120] = 1653726400000;
  laserTimeStamp[517124] = 1653728126000;
  laserTimeStamp[517132] = 1653730328000;
  laserTimeStamp[517136] = 1653732051000;
  laserTimeStamp[517141] = 1653735268000;
  laserTimeStamp[517144] = 1653738882000;
  laserTimeStamp[517205] = 1653808408000;
  laserTimeStamp[517214] = 1653811673000;
  laserTimeStamp[517216] = 1653812811000;
  laserTimeStamp[517218] = 1653815109000;
  laserTimeStamp[517219] = 1653815730000;
  laserTimeStamp[517220] = 1653816476000;
  laserTimeStamp[517222] = 1653817433000;
  laserTimeStamp[517224] = 1653822183000;
  laserTimeStamp[517616] = 1654242788000;
  laserTimeStamp[517618] = 1654244395000;
  laserTimeStamp[517619] = 1654245241000;
  laserTimeStamp[517620] = 1654246805000;
  laserTimeStamp[517622] = 1654252675000;
  laserTimeStamp[517623] = 1654253383000;
  //laserTimeStamp[517676] = ; // bad run anyway
  laserTimeStamp[517677] = 1654305282000;
  laserTimeStamp[517678] = 1654307618000;
  laserTimeStamp[517679] = 1654310481000;
  laserTimeStamp[517684] = 1654314428000;
  laserTimeStamp[517685] = 1654315256000;
  laserTimeStamp[517689] = 1654324732000;
  laserTimeStamp[517690] = 1654325594000;
  laserTimeStamp[517692] = 1654332609000;
  laserTimeStamp[517693] = 1654333304000;
  laserTimeStamp[517735] = 1654409869000;
  laserTimeStamp[517736] = 1654410373000;
  laserTimeStamp[517737] = 1654410885000;
  laserTimeStamp[517748] = 1654415651000;
  laserTimeStamp[517750] = 1654420434000;
  laserTimeStamp[517751] = 1654421682000;
  laserTimeStamp[517753] = 1654426894000;
  laserTimeStamp[517758] = 1654432984000;
  laserTimeStamp[517767] = 1654441645000;
  laserTimeStamp[518541] = 1655115072000;
  laserTimeStamp[518542] = 1655116790000;
  laserTimeStamp[518543] = 1655117484000;
  laserTimeStamp[518546] = 1655119611000;
  laserTimeStamp[518547] = 1655122585000;

  std::map<std::string, std::string> headers, metadataRCT, metadata;
  if (useCCDB) {
    headers = c.retrieveHeaders(Form("RCT/Info/RunInformation/%i", run), metadataRCT, -1);
    printf("\nLooking for vdrift for run %d\n", run); 
    sor = stol(headers["SOR"].c_str());
  }
  else {
    const auto& sorEl = laserTimeStamp.find(run);
    if (sorEl == laserTimeStamp.end()) {
      std::cout << "Run not found in map to determine laser timestamp!" << "\n";
      return -999999999; // should be crazy enough to result in issues in reco output
    }
    sor = sorEl->second;
  }
  
  o2::ccdb::CcdbApi ctest;
  ctest.init("http://ccdb-test.cern.ch:8080");
  o2::tpc::LtrCalibData* ltrCalib = ctest.retrieveFromTFileAny<o2::tpc::LtrCalibData>("TPC/Calib/LaserTracks", metadata, sor);   /// timestamp in the run of interest
  auto corr = ltrCalib->getDriftVCorrection();
  float vcorr = o2::tpc::ParameterGas::Instance().DriftV / corr;
  printf("vdrift = %f\n", vcorr);
  const char* vcorrStr = std::to_string(vcorr).c_str();

  ofstream vdriftFile;
  vdriftFile.open("vdrift.txt");
  vdriftFile << vcorr;
  vdriftFile.close();
  
  return vcorr;

}


