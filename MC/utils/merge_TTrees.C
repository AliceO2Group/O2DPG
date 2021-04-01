// A helper to "vertically" merge the set of (distinct) branches of 2 trees
// into a single common (non-friended) tree in a new file.
//
// This is using RDataFrame mechanics as suggested by the ROOT team.
// TODO: generalize to abirtrary list of files.
void merge_TTrees(std::string f1, std::string f2, std::string treename, std::string outname) {
  TFile file(f1.c_str(), "OPEN");
  auto t1=(TTree*)file.Get(treename.c_str());
  t1->AddFriend(treename.c_str(), f2.c_str());
  ROOT::RDataFrame df(*t1);
  df.Snapshot(treename.c_str(), outname.c_str(), ".*");
}
