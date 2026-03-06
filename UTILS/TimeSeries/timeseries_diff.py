"""timeseries_diff.py
import sys,os; sys.path.insert(1, os.environ[f"O2DPG"]+"/UTILS/TimeSeries");
from  timeseries_diff  import *

Utility helpers for time‑series comparison scripts.
keeping their ROOT files alive.
"""

import os
import pathlib
from typing import List, Tuple, Optional

import ROOT  # PyROOT

# ---------------------------------------------------------------------------
# Helper: open many ROOT files and keep them alive
# ---------------------------------------------------------------------------

def read_time_series(listfile: str = "o2_timeseries_tpc.list",treename: str = "timeSeries",) -> List[Tuple[ROOT.TFile, Optional[ROOT.TTree]]]:
    """Read *listfile* containing one ROOT path per line and return a list
    of ``(TFile, TTree | None)`` tuples.
    The TFile objects are **kept open** (and returned) so the TTrees remain
    valid for the caller.  Blank lines and lines starting with "#" are
    ignored.  Environment variables in paths are expanded.
    Parameters
    ----------
    listfile : str
        Text file with ROOT filenames.
    treename : str, default "timeSeries"
        Name of the tree to retrieve from each file.
    Returns
    -------
    list of tuples
        ``[(f1, tree1), (f2, tree2), ...]`` where *tree* is ``None`` if
        the file or tree could not be opened.
    """
    files_and_trees: List[Tuple[ROOT.TFile, Optional[ROOT.TTree]]] = []

    with open(listfile, "r") as fh:
        paths = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]

    for raw_path in paths:
        path = os.path.expandvars(raw_path)
        if not pathlib.Path(path).is_file():
            print(f"[read_time_series] warning: file not found -> {path}")
            files_and_trees.append((None, None))
            continue
        try:
            froot = ROOT.TFile.Open(path)
            if not froot or froot.IsZombie():
                raise RuntimeError("file could not be opened")
            tree = froot.Get(treename)
            if not tree:
                print(f"[read_time_series] warning: tree '{treename}' missing in {path}")
            files_and_trees.append((froot, tree))
        except Exception as e:
            print(f"[read_time_series] error: cannot open {path}: {e}")
            files_and_trees.append((None, None))

    return files_and_trees

def makeAliases(trees):
    for tree in trees: tree[1].AddFriend(trees[0][1],"F")


def setStyle():
    ROOT.gStyle.SetOptStat(0)
    ROOT.gStyle.SetOptTitle(0)
    ROOT.gStyle.SetPalette(ROOT.kRainBow)
    ROOT.gStyle.SetPaintTextFormat(".2f")
    ROOT.gStyle.SetTextFont(42)
    ROOT.gStyle.SetTextSize(0.04)
    ROOT.gROOT.ForceStyle()
    ROOT.gROOT.SetBatch(True)






# ---------------------------------------------------------------------------
# make_ratios ----------------------------------------------------------------
# ---------------------------------------------------------------------------

def make_ratios(trees: list, outdir: str  = "fig", pdf_name: str = "ratios.pdf") -> ROOT.TCanvas:
    """Create ratio plots  *log(var/F.var) vs Iteration$*  for each input tree.
    * A PNG for every variable / tree is saved to *outdir*
    * All canvases are also appended to a multi‑page PDF *pdf_name*
    * Vertical guide‑lines mark the logical regions (isector, itgl, iqpt, occu)

    """
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    pdf_path = outdir / pdf_name

    # ------- style / helpers ----------------------------------------------
    ROOT.gStyle.SetOptTitle(1)
    canvas = ROOT.TCanvas("c_ratio", "ratio plots", 1200, 600)
    lab    = ROOT.TLatex()
    lab.SetTextSize(0.04)

    # vertical guides in **user** x‑coordinates (Iteration$ axis: 0–128)
    vlines   = [0, 54, 84, 104, 127]
    vnames   = ["isector", "itgl", "iqpt", "occupancy"]
    vcolors  = [ROOT.kRed+1, ROOT.kBlue+1, ROOT.kGreen+2, ROOT.kMagenta+1]
    setups=["ref","apass2_closure-test-zAcc.GausSmooth_test3_streamer","apass2_closure-test-zAcc.GausSmooth_test4_streamer","apass2_closure-test-zAcc.GausSmooth_test2_streamer"]
    # variables to compare ---------------------------------------------------
    vars_ = [
        "mTSITSTPC.mTPCChi2A",  "mTSITSTPC.mTPCChi2C",
        "mTSTPC.mDCAr_A_NTracks", "mTSTPC.mDCAr_C_NTracks",
        "mTSTPC.mTPCNClA",       "mTSTPC.mTPCNClC",
        "mITSTPCAll.mITSTPC_A_MatchEff", "mITSTPCAll.mITSTPC_C_MatchEff",
        "mdEdxQMax.mLogdEdx_A_RMS","mdEdxQMax.mLogdEdx_C_RMS",
        "mdEdxQMax.mLogdEdx_A_IROC_RMS","mdEdxQMax.mLogdEdx_C_IROC_RMS"
    ]
    cut = "mTSITSTPC.mDCAr_A_NTracks > 200"

    # open PDF ---------------------------------------------------------------
    canvas.Print(f"{pdf_path}[")  # begin multipage

    for setup_index, (_, tree) in enumerate(trees[1:], start=1):
        if not tree:
            continue
        for var in vars_:
            expr = f"log({var}/F.{var}):Iteration$"
            # 2‑D density histogram
            tree.Draw(f"{expr}>>his(128,0,128,50,-0.05,0.05)", cut, "colz")
            # profile overlay
            tree.Draw(f"{expr}>>hp(128,0,128)", cut, "profsame")
            pad = ROOT.gPad
            ymin, ymax = -0.05, 0.05
            # keep references so ROOT does not garbage‑collect the guides
            guides: list[ROOT.TLine] = []
            for x, txt, col in zip(vlines, vnames, vcolors):
                # skip lines outside current x‑range (safety when reusing canvas)
                if x < 0 or x > 128:continue
                # 1) vertical line in **user** coordinates
                ln = ROOT.TLine(x, ymin, x, ymax)
                ln.SetLineColor(col)
                ln.SetLineStyle(2)
                ln.SetLineWidth(5)
                ln.Draw()
                guides.append(ln)
                # 2) text in NDC (pad‑relative) for stable position
                x_ndc = pad.XtoPad(x)          # already NDC 0‑1
                lab.SetTextColor(col)
                lab.DrawLatex(x + 0.02, 0.03, txt)

            # label of the setup on top‑left
            lab.SetTextColor(ROOT.kMagenta+2)
            lab.DrawLatex(0.15, 0.05, f"Setup {setups[setup_index]}")
            canvas.Modified(); canvas.Update()

            # ----------------------------------------------------------------
            tag = var.split('.')[-1]
            canvas.SaveAs(str(outdir / f"ratio_{setup_index}_{tag}.png"))
            canvas.Print(str(pdf_path))           # add page

            # prevent ROOT from deleting the guides before next Draw()
            for ln in guides:
                pad.GetListOfPrimitives().Remove(ln)

    canvas.Print(f"{pdf_path}]")  # close multipage
    return canvas
