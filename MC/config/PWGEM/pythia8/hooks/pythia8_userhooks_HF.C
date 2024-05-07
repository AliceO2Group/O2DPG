#include "Pythia8/Pythia.h"

class UserHooks_HF : public Pythia8::UserHooks
{

 public:
  UserHooks_HF() = default;
  ~UserHooks_HF() = default;
  bool canVetoPartonLevel() override { return true; };
  bool doVetoPartonLevel(const Pythia8::Event& event) override
  {
    for (int ipa = 0; ipa < event.size(); ++ipa) {
      auto daughterList = event[ipa].daughterList();
      bool hasQ1 = false;
      bool hasQ1bar = false;
      bool hasQ2 = false;
      bool hasQ2bar = false;
      for (auto ida : daughterList) {
        if (event[ida].id() == mPDG1)
          hasQ1 = true;
        if (event[ida].id() == -mPDG1)
          hasQ1bar = true;
        if (event[ida].id() == mPDG2)
          hasQ2 = true;
        if (event[ida].id() == -mPDG2)
          hasQ2bar = true;
      }
      if ( (hasQ1 && hasQ1bar) || (hasQ2 && hasQ2bar) )
        return false; // do not veto event
    }
    return true; // veto event
  };

  void setPDG(int pdg1, int pdg2) { mPDG1 = pdg1; mPDG2 = pdg2 };

 private:
  int mPDG1 = 4;
  int mPDG2 = 5;
};

Pythia8::UserHooks*
  pythia8_userhooks_ccbar()
{
  auto hooks = new UserHooks_HF();
  hooks->setPDG(4, 4);
  return hooks;
}

Pythia8::UserHooks*
  pythia8_userhooks_bbbar()
{
  auto hooks = new UserHooks_HF();
  hooks->setPDG(5, 5);
  return hooks;
}

Pythia8::UserHooks*
  pythia8_userhooks_ccbar_or_bbbar()
{
  auto hooks = new UserHooks_HF();
  hooks->setPDG(4, 5);
  return hooks;
}
