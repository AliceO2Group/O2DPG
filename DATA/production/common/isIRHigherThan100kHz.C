#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "CCDB/BasicCCDBManager.h"
#include "CommonDataFormat/InteractionRecord.h"
#include "CCDB/CcdbApi.h"
#include "CCDB/BasicCCDBManager.h"
#include "DataFormatsCTP/Scalers.h"
#include "DataFormatsCTP/Configuration.h"
#endif
using namespace o2::ctp;
const double orbitDuration = 88.924596234; // us

void writeIRtoFile(int isIRhigherThan100kHz);

void isIRHigherThan100kHz(int run = 527057, bool debug = false) {

  LOGP(info, "Checking IR");
  if (run < 523141) {
    // LHC22c, d, e, f
    LOGP(info, "Run number < 523141 --> we are in 22c, d, e, or f, so IR is < 100 kHz");
    writeIRtoFile(0);
    return;
  }
  
  o2::ccdb::CcdbApi ccdb_api;
  auto& ccdb_inst = o2::ccdb::BasicCCDBManager::instance();
  ccdb_inst.setURL("https://alice-ccdb.cern.ch");
  ccdb_api.init("https://alice-ccdb.cern.ch");
  // access SOR and EOR timestamps
  std::map<string, string> headers, metadata;
  headers = ccdb_api.retrieveHeaders(Form("RCT/Info/RunInformation/%i", run), metadata, -1);
  int64_t tsSOR = atol(headers["SOR"].c_str()); // ms
  int64_t tsEOR = atol(headers["EOR"].c_str()); // ms
  LOGP(info, "tsSOR={} ms, tsEOR={} ms", tsSOR, tsEOR);

  // Extract CTP info
  std::map<std::string, std::string> metadataCTP;
  metadataCTP["runNumber"] = Form("%d",run);
  ccdb_inst.setFatalWhenNull(false);
  o2::ctp::CTPRunScalers* scl = ccdb_inst.getSpecific<o2::ctp::CTPRunScalers>("CTP/Calib/Scalers", tsSOR, metadataCTP);
  if (!scl) {
    LOGP(info, "CTP/Calib/Scalers object does not exist in production CCDB, trying test CCDB");
    ccdb_inst.setURL("http://ccdb-test.cern.ch:8080");
    scl = ccdb_inst.getSpecific<o2::ctp::CTPRunScalers>("CTP/Calib/Scalers", tsSOR, metadata);
    if (!scl) {
      LOGP(info, "Cannot get IR for run {} neither from production nor test CCDB, writing -1", run);
      writeIRtoFile(-1);
      return;
    }
  }

  scl->convertRawToO2();
  std::vector<CTPScalerRecordO2> mScalerRecordO2 = scl->getScalerRecordO2();
  int n = mScalerRecordO2.size();
  double ir = 0;
  if (n != 0) {
    std::int64_t totScalers = 0;
    std::vector<int64_t> vOrbit;
    std::vector<int64_t> vScaler;
    int i = 0;
    for (auto& record : mScalerRecordO2){
      if (debug) {
	record.printStream(std::cout);
      }
      std::vector<CTPScalerO2>& scalers = record.scalers;
      o2::InteractionRecord& intRecord = record.intRecord;
      vOrbit.push_back(intRecord.orbit);
      if (debug) {
	LOGP(info, "{} orbit = {} scalers = {}", i, intRecord.orbit, scalers[0].lmBefore);
      }
      vScaler.push_back(scalers[0].lmBefore); // use scalers for class 0 (usually TVX). TODO: extract info on class id from trigger config
      totScalers += scalers[0].lmBefore;
      ++i;
    }

    int64_t duration = (vOrbit.back() - vOrbit.front()) * orbitDuration * 1e-6; // s
    ir = double(vScaler.back() - vScaler.front()) / duration;
    LOGP(info, "run {}: orbit.back = {}, orbit.front = {}, duration = {} s, scalers = {}, IR = {} Hz", run, vOrbit.back(), vOrbit.front(), duration, vScaler.back() - vScaler.front(), ir);
  }

  if (ir < 100000) {
    LOGP(info, "IR < 100 kHz");
    writeIRtoFile(0);
    return;
  }
  LOGP(info, "IR > 100 kHz");
  writeIRtoFile(1);
  return;
}

void writeIRtoFile(int isIRhigherThan100kHz) {
  ofstream fp("IR.txt");
  fp << isIRhigherThan100kHz << endl;
  fp.close();
}
