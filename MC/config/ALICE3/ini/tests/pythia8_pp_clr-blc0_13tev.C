int External()
{
  std::string path{"o2sim_Kine.root"};

  TFile file(path.c_str(), "read");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << std::endl;
    return 1;
  }

  TTree* tree = (TTree*)file.Get("o2sim");

  if (!tree) {
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }

  return 0;
}
