/// \author R+Preghenella - July 2020

/// This Pythia8 UserHooks can veto the processing at parton level.
/// The partonic event is scanned searching for a q-qbar mother
/// with at least one of the c quarks produced withing a fiducial
/// window around midrapidity that can be specified by the user.

#include "Pythia8/Pythia.h"

class UserHooks_qqbar : public Pythia8::UserHooks
{
  
 public:
  UserHooks_qqbar() = default;
  ~UserHooks_qqbar() = default;
  bool canVetoPartonLevel() override { return true; };
  bool doVetoPartonLevel(const Pythia8::Event& event) override {
    // search for c-cbar mother with at least one c at midrapidity
    for (int ipa = 0; ipa < event.size(); ++ipa) {
      auto daughterList = event[ipa].daughterList();
      bool hasc = false, hascbar = false, atSelectedY = false;
      for (auto ida : daughterList) {
	if (event[ida].id() == mPDG) hasc = true;
	if (event[ida].id() == -mPDG) hascbar = true;
	if ( (event[ida].y() > mRapidityMin) && (event[ida].y() < mRapidityMax) ) atSelectedY = true;
      }
      if (hasc && hascbar && atSelectedY)
	return false; // found it, do not veto event
    }
    return true; // did not find it, veto event
  };

  void setPDG(int val) { mPDG = val; };
  void setRapidity(double valMin, double valMax) { mRapidityMin = valMin; mRapidityMax = valMax; };
  
private:

  int mPDG = 4;
  double mRapidityMin = -1.5;
  double mRapidityMax = 1.5;
  
};

Pythia8::UserHooks*
  pythia8_userhooks_ccbar(double rapidityMin = -1.5, double rapidityMax=1.5)
{
  auto hooks = new UserHooks_qqbar();
  hooks->setPDG(4);
  hooks->setRapidity(rapidityMin,rapidityMax);
  return hooks;
}

Pythia8::UserHooks*
  pythia8_userhooks_bbbar(double rapidityMin = -1.5, double rapidityMax = 1.5)
{
  auto hooks = new UserHooks_qqbar();
  hooks->setPDG(5);
  hooks->setRapidity(rapidityMin,rapidityMax);
  return hooks;
}

