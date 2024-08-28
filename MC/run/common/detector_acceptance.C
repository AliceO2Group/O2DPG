#include <TMath.h>

/// =================================================
/// \file detector_acceptance.C

/// \brief Define particle acceptance cuts for predefined detectors and detector combinations
///
/// Define particle acceptance cuts for predefined detectors and detector combinations.
/// Current acceptances defined based con the calorimeters and their combinations.
///
/// \author Gustavo Conesa Balbastre (LPSC-IN2P3-CNRS)
/// =================================================

enum EDetectorAcceptance_t {
  kAcceptance_FullDetector,
  kAcceptance_EMCPHSDMC,
  kAcceptance_EMCDMC,
  kAcceptance_PHSDMC,
  kAcceptance_EMC,
  kAcceptance_DMC,
  kAcceptance_PHS,
  kAcceptance_FOC
};

/// Open selection, minimum particle eta cut.
//
bool full(Float_t phi, Float_t eta)
{
  if (TMath::Abs(eta) < 1.5)
    return true;
  else
    return false;
}

/// Check if particle is in EMCal.
//
bool emcal(Float_t phi, Float_t eta)
{
  if (phi > 80. * TMath::DegToRad() &&
      phi < 187. * TMath::DegToRad() &&
      TMath::Abs(eta) < 0.7)
    return true;
  else
    return false;
}

/// Check if particle is in DCal.
//
bool dcal(Float_t phi, Float_t eta)
{
  Bool_t fullSM = false;
  Bool_t thirdSM = false;

  if (phi > 260. * TMath::DegToRad() &&
      phi < 320. * TMath::DegToRad() &&
      TMath::Abs(eta) > 0.22 &&
      TMath::Abs(eta) < 0.7)
    fullSM = true;

  if (phi > 320. * TMath::DegToRad() &&
      phi < 327. * TMath::DegToRad() &&
      TMath::Abs(eta) < 0.7)
    thirdSM = true;

  if (fullSM || thirdSM)
    return true;
  else
    return false;
}

/// Check if particle is in PHOS.
//
bool phos(Float_t phi, Float_t eta)
{
  if (phi > 250 * TMath::DegToRad() &&
      phi < 320 * TMath::DegToRad() &&
      TMath::Abs(eta) < 0.13)
    return true;
  else
    return false;
}

/// Check if particle is in any of the lower central barrel calorimeters:
/// EMCal or DCal.
//
bool emcal_dcal(Float_t phi, Float_t eta)
{
  if (emcal(phi, eta))
    return true;
  else if (dcal(phi, eta))
    return true;
  else
    return false;
}

/// Check if particle is in any of the lower central barrel calorimeters:
/// PHOS or DCal.
//
bool dcal_phos(Float_t phi, Float_t eta)
{
  if (dcal(phi, eta))
    return true;
  else if (phos(phi, eta))
    return true;
  else
    return false;
}

/// Check if particle is in any of the central barrel calorimeters:
/// PHOS, DCal or EMCal.
//
bool barrel_calorimeters(Float_t phi, Float_t eta)
{
  if (emcal(phi, eta))
    return true;
  else if (dcal(phi, eta))
    return true;
  else if (phos(phi, eta))
    return true;
  else
    return false;
}


/// Check if particle is in FOCAL
bool focal(Float_t phi, Float_t eta){
  return (eta > 3.4 && eta < 5.8);
}

/// \return True if particle in desired acceptance.
///
/// \param acceptance : Detector acceptance to be checked.
/// \param phi : Particle phi angle in radians.
/// \param eta : Particle eta angle.
//
bool detector_acceptance(Int_t acceptance, Float_t phi, Float_t eta)
{
  switch (acceptance) {
    case kAcceptance_FullDetector:
      return full(phi, eta);
      break;
    case kAcceptance_EMC:
      return emcal(phi, eta);
      break;
    case kAcceptance_PHS:
      return phos(phi, eta);
      break;
    case kAcceptance_DMC:
      return dcal(phi, eta);
      break;
    case kAcceptance_PHSDMC:
      return dcal_phos(phi, eta);
      break;
    case kAcceptance_EMCDMC:
      return emcal_dcal(phi, eta);
      break;
    case kAcceptance_EMCPHSDMC:
      return barrel_calorimeters(phi, eta);
      break;
    case kAcceptance_FOC:
      return focal(phi, eta);
  }

  return false;
}
