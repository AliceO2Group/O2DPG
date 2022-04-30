#ifndef EVT_TRANDOM_ENGINE_HH
#define EVT_TRANDOM_ENGINE_HH

R__LOAD_LIBRARY(EvtGen)
R__ADD_INCLUDE_PATH($EVTGEN_ROOT/include)

#include <TRandom.h>
#include "EvtGenBase/EvtRandomEngine.hh"

class EvtTRandomEngine : public EvtRandomEngine {
public:
  
  EvtTRandomEngine(){
    gRandom->SetSeed(0);
  }
  
  void setSeed(unsigned int seed){
    gRandom->SetSeed(seed);
  }

  virtual double random()
  {
    return gRandom->Rndm();
  }
};

#endif