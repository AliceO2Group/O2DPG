#include <string>
#include <vector>
#include <filesystem>



void findRangeNotEmpty1D(TH1* h, double& min, double& max)
{
  auto axis = h->GetXaxis();
  min = axis->GetBinLowEdge(1);
  max = axis->GetBinUpEdge(axis->GetNbins());
  for (int i = 1; i <= axis->GetNbins(); i++) {
    if (h->GetBinContent(i) != 0) {
      min = axis->GetBinLowEdge(i);
      break;
    }
  }
  for (int i = axis->GetNbins(); i >= 1 ; i--) {
    if (h->GetBinContent(i) != 0) {
      max = axis->GetBinUpEdge(i);
      break;
    }
  }
}


TH1* makeFrameFromHistograms(TPad& pad, std::vector<TH1*> const& histograms, bool& shouldBeLog)
{
  // make a frame to fit all histograms
  // propose log10 scale in case some integrals differ by more than 2 orders of magnitude
  auto integralRef = histograms[0]->Integral();
  shouldBeLog = false;
  auto minY = histograms[0]->GetMinimum(0);
  double maxY = histograms[0]->GetMaximum();

  double minX;
  double maxX;
  findRangeNotEmpty1D(histograms[0], minX, maxX);

  // find minima and maxima
  for (int i = 1; i < histograms.size(); i++) {
    minY = std::min(histograms[i]->GetMinimum(0), minY);
    maxY = std::max(histograms[i]->GetMaximum(), maxY);

    double minXNext;
    double maxXNext;
    findRangeNotEmpty1D(histograms[i], minXNext, maxXNext);
    minX = std::min(minX, minXNext);
    maxX = std::max(maxX, maxXNext);

    auto integral = histograms[i]->Integral();
    if ((integralRef > 0 && integral / integralRef > 100) || (integral > 0 && integralRef / integral > 100)) {
      // decide whether to do a log plot
      shouldBeLog = true;
    }
  }

  // finalise the y-axis limits
  if (shouldBeLog) {
    auto margin = std::log10(maxY / minY);
    minY = minY / std::pow(10, margin * 0.1);
    maxY = maxY * std::pow(10, margin * 0.3);;
  } else {
    auto margin = 0.1 * (maxY - minY);
    maxY += 3 * margin;
    minY -= std::max(0., margin);
  }

  if (histograms[0]->GetXaxis()->IsAlphanumeric()) {
    auto alphanumericFrame = (TH1*)histograms[0]->Clone();
    alphanumericFrame->Reset("ICEMS");
    return alphanumericFrame;
  }

  return pad.DrawFrame(minX, minY, maxX, maxY);
}

// overlay 1D histograms
void overlay1D(std::vector<TH1*> hVec, std::vector<std::string> labelVec, TLegend* additionalLegend, std::string const& outputDir)
{
  TCanvas c("overlay", "", 800, 800);
  c.cd();

  TPad nominalPad("nominalPad", "nominalPad", 0, 0.3, 1., 1.);
  nominalPad.SetBottomMargin(0);
  TPad ratioPad("ratioPad", "ratioPad", 0, 0.05, 1. ,0.32);
  ratioPad.SetTopMargin(0);
  ratioPad.SetBottomMargin(0.2);

  nominalPad.Draw();
  ratioPad.Draw();

  const int colors[7] = {kRed + 2, kBlue - 4, kGreen + 3, kMagenta + 1, kCyan + 2, kOrange + 5, kYellow - 6};
  const int linestyles[6] = {1, 10, 2, 9, 8, 7};

  TLegend legendOverlay(0.65, 0.7, 0.9, 0.9);
  legendOverlay.SetFillStyle(0);
  legendOverlay.SetBorderSize(0);

  bool logY{};
  nominalPad.cd();
  auto frame = makeFrameFromHistograms(nominalPad, hVec, logY);
  frame->SetTitle(hVec[0]->GetTitle());
  auto yAxis = frame->GetYaxis();
  yAxis->ChangeLabel(1, -1, -1, -1, -1, -1, " ");
  yAxis->SetTitleFont(43);
  yAxis->SetTitleSize(20);
  yAxis->SetLabelFont(43);
  yAxis->SetLabelSize(20);
  yAxis->SetTitle(hVec[0]->GetYaxis()->GetTitle());
  auto xAxis = frame->GetXaxis();
  xAxis->SetLabelFont(43);
  xAxis->SetLabelSize(0);


  std::vector<TH1*> ratios;

  std::string emptyText;
  for (int i = 0; i < hVec.size(); i++) {
    auto& h = hVec[i];

    h->SetStats(0);
    h->SetLineStyle(linestyles[i % 6]);
    h->SetLineWidth(1);
    h->SetLineColor(colors[i % 7]);

    if (i > 0) {
      // no ratio for the first histogram (which would simply be 1)
      TH1* hRatio = (TH1*)h->Clone();
      hRatio->SetDirectory(0);
      hRatio->Divide(h, hVec[0], 1.0, 1.0, "B"); // error option?
      ratios.push_back(hRatio);
    }

    legendOverlay.AddEntry(h, labelVec[i].c_str());

    h->Draw("same E hist");
    if (h->GetEntries() == 0) {
      emptyText += labelVec[i] + ", ";
    }
  }

  if (logY) {
    nominalPad.SetLogy();
  }

  if (additionalLegend) {
    additionalLegend->SetBorderSize(0);
    additionalLegend->SetFillStyle(0);
    // To reposition the legend we need to: Draw, Update, set new coordinates, Modified
    additionalLegend->Draw("same");
    nominalPad.Update();
    additionalLegend->SetX1NDC(0.15);
    additionalLegend->SetY1NDC(0.7);
    additionalLegend->SetX2NDC(0.4);
    additionalLegend->SetY2NDC(0.9);
    nominalPad.Modified();
  }
  legendOverlay.Draw("same");

  if (!emptyText.empty()) {
    emptyText.pop_back();
    emptyText.pop_back();
    emptyText = std::string("EMPTY: ") + emptyText;
    TText *t1 = new TText(0.2, 0.5, emptyText.c_str());
    t1->SetNDC();
    t1->Draw();
  }

  ratioPad.cd();
  frame = makeFrameFromHistograms(ratioPad, ratios, logY);
  yAxis = frame->GetYaxis();
  yAxis->SetTitleFont(43);
  yAxis->SetTitleSize(20);
  yAxis->SetLabelFont(43);
  yAxis->SetLabelSize(20);
  yAxis->SetTitle("ratio");

  xAxis = frame->GetXaxis();
  xAxis->SetTitleFont(43);
  xAxis->SetTitleSize(20);
  xAxis->SetLabelFont(43);
  xAxis->SetLabelSize(20);
  xAxis->SetTitle(hVec[0]->GetXaxis()->GetTitle());

  for (int i = 0; i < ratios.size(); i++) {
    auto& h = ratios[i];
    h->Draw("same");
  }

  if (logY) {
    ratioPad.SetLogy();
  }

  auto savePath = outputDir + "/" + hVec[0]->GetName() + ".png";
  c.SaveAs(savePath.c_str());
  c.Close();

  for (auto& r : ratios) {
    delete r;
  }
}

// overlay 2D histograms
void overlay2D(std::vector<TH1*> hVec1, std::vector<std::string> labelVec, TLegend* legend, std::string const& outputDir)
{
  std::vector<TH2*> hVec;
  for (auto h : hVec1){
    hVec.push_back(dynamic_cast<TH2*>(h));
  }
  int nHistos = hVec.size();

  TCanvas c("overlay", "", 2400, 800 * (nHistos-1));
  c.Divide(3, nHistos - 1);
  c.cd(1);
  hVec[0]->SetTitle(hVec[0]->GetTitle() + TString("(" + labelVec[0] + ")"));
  hVec[0]->SetStats(0);
  hVec[0]->Draw("colz");

  if (hVec[0]->GetEntries() == 0) {
    TText *t1 = new TText(0.5, 0.5, "EMPTY");
    t1->SetNDC();
    t1->Draw();
  }

  std::vector<TH1*> ratios;

  for (int i = 1; i < nHistos; i++){
    auto hDiv = (TH2*)hVec[i]->Clone(Form("%s_ratio", hVec[i]->GetName()));
    hDiv->SetDirectory(0);
    ratios.push_back(hDiv);
    hDiv->SetTitle(hVec[i]->GetTitle() + TString("(" + labelVec[i] + "/"+labelVec[0]+")"));
    hDiv->SetStats(0);
    hDiv->Divide(hVec[0]);
    hVec[i]->SetTitle(hVec[i]->GetTitle() + TString("(" + labelVec[i] + ")"));
    hVec[i]->SetStats(0);

    c.cd(i * 3 - 1);
    hVec[i]->Draw("colz");
    if (hVec[i]->GetEntries() == 0) {
      TText *t1 = new TText(0.5, 0.5, "EMPTY");
      t1->SetNDC();
      t1->Draw();
    }

    c.cd(i * 3);
    hDiv->Draw("colz");
  }

  if (legend){
    c.cd(3);
    legend->SetTextSize(0.03);
    legend->SetTextFont(62);
    legend->Draw("same");
    gPad->Update();
    legend->SetX1NDC(0.4);
    legend->SetY1NDC(0.7);
    legend->SetX2NDC(0.89);
    legend->SetY2NDC(0.89);
    gPad->Modified();
  }

  auto savePath = outputDir + "/" + hVec[0]->GetName() + ".png";
  c.SaveAs(savePath.c_str());
  c.Close();

  for (auto& r : ratios) {
    delete r;
  }
}

// entry point for overlay plots from ReleaseValidation.C
void PlotOverlayAndRatio(std::vector<TH1*> hVec, std::vector<std::string> labelVec, std::string outputDir = "overlayPlots", TLegend* legendMetrics = nullptr)
{
  if (!std::filesystem::exists(outputDir)) {
    std::filesystem::create_directory(outputDir);
  }

  bool is2D = false;
  for (auto h : hVec){
  	if (dynamic_cast<TH3*>(h)){
  		 std::cerr << "Cannot yet overlay 3D histograms\nSkipping " << h->GetName() << "\n";
    return;
  	}
    if (dynamic_cast<TH2*>(h)){
    is2D = true;
    }
  }

  if (is2D){
    overlay2D(hVec, labelVec, legendMetrics, outputDir);
  }
  else {
    overlay1D(hVec, labelVec, legendMetrics, outputDir);
  }
}

// entry point for plotting only overlays
void PlotOverlays(initializer_list<std::string> fileNames_list, initializer_list<std::string> labelVec_list, std::string outputDir = "overlayPlots"){
  std::vector<std::string> fileNames(fileNames_list);
  std::vector<std::string> labelVec(labelVec_list);

  if (fileNames.size() > labelVec.size()){
    for (int i=labelVec.size();i<fileNames.size(); i++){
      labelVec.push_back("File"+std::to_string(i+1));
    }
  }

  std::vector<TFile*> files;
  for (auto& fileName : fileNames){
    TFile* thisFile = TFile::Open(fileName.c_str(), "READ");
    files.push_back(thisFile);
  }

  TIter next(files[0]->GetListOfKeys());
  TKey* key{};
  while ((key = static_cast<TKey*>(next()))) {
    std::vector<TH1*> hVec;
    hVec.push_back(static_cast<TH1*>(key->ReadObj()));
    auto oname = key->GetName();
    bool foundAll = true;
    for (int i=1; i<files.size();i++){
      auto hNew = static_cast<TH1*>(files[i]->Get(oname));
      if (!hNew) {
        // That could still happen in case we compare either comletely different file by accident or something has been changed/added/removed
        foundAll = false;
        std::cerr << "ERROR: Histogram " << oname << " not found in file " << fileNames[i].c_str() << "\n";
      }
      hVec.push_back(hNew);
    }
    if (foundAll){
      PlotOverlayAndRatio(hVec, labelVec, outputDir);
    }
    else {
      std::cerr << "ERROR: Histogram " << oname << " not found in all files\n";
      return;
    }
  }
}
