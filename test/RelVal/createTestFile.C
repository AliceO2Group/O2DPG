void createTestFile(std::string const& filename)
{
    TFile file(filename.c_str(), "RECREATE");

    // a histogram that is always the same
    TH1F h1("step", "", 10, 0, 10);
    for (int i = 1; i < h1.GetNbinsX() + 1; i++) {
        h1.SetBinContent(i, i);
    }
    // a Gaussian (randomly filled)
    TH1F h2("gauss", "", 100, -3, 3);
    gRandom->SetSeed();
    h2.FillRandom("gaus", 10000, gRandom);

    h1.Write();
    h2.Write();

    file.Close();
}
