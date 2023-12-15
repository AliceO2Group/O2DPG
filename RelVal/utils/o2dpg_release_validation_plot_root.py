#!/usr/bin/env python3
#
# Definition common functionality

from os.path import join, exists
from os import remove
from math import log10, pow
import re

from ctypes import c_char_p
from ROOT import gSystem, TFile, TCanvas, TPad, TLegend, TH2, TH3, TText, TPaveText, kWhite, kRed, kBlue, kGreen, kMagenta, kCyan, kOrange, kYellow, TProfile


def style_histograms(histograms):
    if isinstance(histograms[0], (TH2, TH3)):
        return
    colors = (kRed + 2, kBlue - 4, kGreen + 3, kMagenta + 1, kCyan + 2, kOrange + 5, kYellow - 6)
    linestyles = (1, 10, 2, 9, 8, 7)

    for i, h in enumerate(histograms):
        h.SetLineStyle(linestyles[i % len(linestyles)])
        h.SetLineColor(colors[i % len(colors)])
        h.SetLineWidth(1)

def findRangeNotEmpty1D(histogram):
    axis = histogram.GetXaxis()
    minX = axis.GetBinLowEdge(1)
    maxX = axis.GetBinUpEdge(axis.GetNbins())

    for i in range(1, axis.GetNbins() + 1):
        # go from left to right to find the first non-empty bin
        if histogram.GetBinContent(i) != 0:
            minX = axis.GetBinLowEdge(i)
            break

    for i in range(axis.GetNbins(), 0, -1):
        # go from right to left to find the last non-empty bin
        if histogram.GetBinContent(i) != 0:
            maxX = axis.GetBinUpEdge(i)
            break

    return minX, maxX


def adjust_axis_text(axis, label_size, title_size):
    axis.SetLabelFont(43)
    axis.SetTitleFont(43)
    axis.SetLabelSize(label_size)
    axis.SetTitleSize(title_size)


def make_frame(pad, histograms):
    integralRef = histograms[0].Integral()
    shouldBeLog = False
    minY = histograms[0].GetMinimum(0)
    maxY = histograms[0].GetMaximum()

    minX, maxX = findRangeNotEmpty1D(histograms[0])

    # find minima and maxima
    for h in histograms[1:]:
        minY = min(h.GetMinimum(0), minY)
        maxY = max(h.GetMaximum(), maxY)

        minXNext, maxXNext = findRangeNotEmpty1D(h)
        minX = min(minX, minXNext)
        maxX = max(maxX, maxXNext)

        integral = h.Integral()
        if (integralRef > 0 and integral / integralRef > 100) or (integral > 0 and integralRef / integral > 100):
            # decide whether to do a log plot
            shouldBeLog = True

    # finalise the y-axis limits
    if shouldBeLog:
        margin = log10(maxY / minY)
        minY = minY / pow(10, margin * 0.1)
        maxY = maxY * pow(10, margin * 0.3)
    else:
        margin = 0.2 * (maxY - minY)
        maxY += 3 * margin
        minY -= max(0., margin)

    if histograms[0].GetXaxis().IsAlphanumeric():
        alphanumericFrame = histograms[0].Clone()
        alphanumericFrame.Reset("ICEMS")
        return alphanumericFrame, shouldBeLog

    frame = pad.DrawFrame(minX, minY, maxX, maxY, histograms[0].GetYaxis().GetTitle())

    return frame, shouldBeLog


def plot_single_overlay_1d(histograms, more_objects, out_path, *args):

    ratios = []
    denominator = histograms[0]
    if isinstance(denominator, TProfile):
        return
    for h in histograms[1:]:
        ratio = h.Clone()
        ratio.SetDirectory(0)
        ratio.Divide(h, denominator, 1, 1, "B")
        ratios.append(ratio)

    c = TCanvas("overlay", "", 800, 800)
    c.cd()

    nominalPad = TPad("nominalPad", "nominalPad", 0, 0.3, 1., 1.)
    nominalPad.SetBottomMargin(0)
    ratioPad = TPad("ratioPad", "ratioPad", 0, 0.05, 1. ,0.32)
    ratioPad.SetTopMargin(0)
    ratioPad.SetBottomMargin(0.2)

    nominalPad.Draw()
    ratioPad.Draw()

    nominalPad.cd()
    nominalFrame, logY = make_frame(nominalPad, histograms)
    yAxis = nominalFrame.GetYaxis()
    yAxis.ChangeLabel(1, -1, -1, -1, -1, -1, " ")

    adjust_axis_text(yAxis, 20, 20)
    adjust_axis_text(nominalFrame.GetXaxis(), 0, 0)
    nominalFrame.Draw("*")
    for h in histograms:
        h.Draw("same E hist")
    for mo in more_objects:
        mo.Draw("same")

    if logY:
        nominalPad.SetLogy()

    ratioPad.cd()
    ratioFrame, logY = make_frame(ratioPad, ratios)
    axis = ratioFrame.GetXaxis()
    axis.SetTitle(histograms[0].GetXaxis().GetTitle())
    adjust_axis_text(axis, 20, 20)
    axis = ratioFrame.GetYaxis()
    axis.SetTitle("ratio")
    adjust_axis_text(axis, 20, 20)

    ratioFrame.Draw("*")
    for ratio in ratios:
        ratio.Draw("same")
    if logY:
        ratioFrame.SetLogy()

    c.SaveAs(out_path)
    c.Close()


def plot_single_overlay_2d(histograms, more_objects, out_path, labels=None):

    n_histograms = len(histograms)
    if not labels:
        labels = [f"label_{i}" for i in range(n_histograms)]

    c = TCanvas("overlay", "", 2400, 800 * (n_histograms-1))
    c.Divide(3, n_histograms - 1)
    c.cd(1)
    histograms[0].SetTitle(histograms[0].GetTitle() + f"({labels[0]})")
    histograms[0].SetStats(0);
    histograms[0].Draw("colz");

    keep_elements = []
    if histograms[0].GetEntries() == 0:
        t1 = TText(0.5, 0.5, "EMPTY")
        keep_elements.append(t1)
        t1.SetNDC()
        t1.Draw()

    ratios = []

    for i, h in enumerate(histograms[1:], start=1):
        ratio = h.Clone()
        ratio.SetDirectory(0)
        ratios.append(ratio)
        ratio.SetTitle(f"{h.GetTitle()} ({labels[i]} / {labels[0]})")
        ratio.SetStats(0)
        ratio.Divide(histograms[0])
        h.SetStats(0)
        h.SetTitle(f"{h.GetTitle()} ({labels[i]})")

        c.cd(i * 3 - 1)
        h.Draw("colz")
        if h.GetEntries() == 0:
            t1 = TText(0.5, 0.5, "EMPTY")
            t1.SetNDC()
            t1.Draw()
            keep_elements.append(t1)

        c.cd(i * 3)
        ratio.Draw("colz")

    c.cd(3)
    for mo in more_objects:
        mo.Draw("same")

    c.SaveAs(out_path)
    c.Close()


def plot_overlays_root(rel_val, file_config_map1, file_config_map2, out_dir, plot_regex=None):


    file1 = TFile(file_config_map1["path"], "READ")
    file2 = TFile(file_config_map2["path"], "READ")

    label1 = file_config_map1["label"]
    label2 = file_config_map2["label"]

    plot_log_file = join(out_dir, "overlay_plotting.log")
    if exists(plot_log_file):
        remove(plot_log_file)

    for object_name, metrics, results in rel_val.yield_metrics_results_per_object():
        if plot_regex is not None and not re.search(object_name, plot_regex):
            continue

        metric_legend_entries = {}
        for metric, result in zip(metrics, results):
            if metric.name not in metric_legend_entries:
                value = "NONE" if not metric.comparable else f"{metric.value}"
                metric_legend_entries[metric.name] = value
            if result is None:
                continue
            metric_legend_entries[metric.name] += f", {result.interpretation}"

        h1 = file1.Get(object_name)
        h2 = file2.Get(object_name)

        more_objects = []
        plot_func = plot_single_overlay_2d
        metrics_box = TPaveText(0.15, 0.7, 0.4, 0.9, "brNDC")
        metrics_box.SetTextFont(43)
        metrics_box.SetTextSize(20)
        metrics_box.SetBorderSize(0)
        more_objects.append(metrics_box)
        if not isinstance(h1, (TH2, TH3)):
            plot_func = plot_single_overlay_1d
            metrics_box.SetFillStyle(0)
            style_histograms([h1, h2])
            legend_labels = TLegend(0.65, 0.7, 0.9, 0.9)
            legend_labels.SetFillStyle(0)
            legend_labels.SetBorderSize(0)
            legend_labels.SetTextFont(43)
            legend_labels.SetTextSize(20)
            legend_labels.AddEntry(h1, label1)
            legend_labels.AddEntry(h2, label2)
            more_objects.append(legend_labels)
        else:
            metrics_box.SetFillColor(kWhite)

        legend_metrics = TLegend(0.15, 0.7, 0.4, 0.9)
        legend_metrics.SetBorderSize(0)
        legend_metrics.SetFillStyle(0)
        for key, value in metric_legend_entries.items():
            metrics_box.AddText(f"{key} = {value}")

        out_path = join(out_dir, f"{object_name}.png")
        gSystem.RedirectOutput(join(out_dir, "overlay_plotting.log"), "a")
        plot_func([h1, h2], more_objects, out_path, [label1, label2])
        gSystem.RedirectOutput(c_char_p(0))

    print(f"INFO: Log file for overlay plotting at {plot_log_file}")


def plot_overlays_root_no_rel_val(file_configs, out_dir):
    gSystem.RedirectOutput(join(out_dir, "overlay_plotting.log"), "w")

    all_names = []
    labels = []
    files = []
    names_per_file = []
    for fc in file_configs:
        all_names.extend(fc["objects"])
        labels.append(fc["label"])
        names_per_file.append(fc["objects"])
        files.append(TFile(fc["path"], "READ"))

    all_names = list(set(all_names))
    for name in all_names:
        histograms = []
        current_labels = []

        for object_names, label, f in zip(labels, files):
            if name not in object_names:
                continue
            histograms.append(f.Get(name))
            current_labels.append(label)

        if not histograms:
            continue

        more_objects = []
        plot_func = plot_single_overlay_2d
        if not isinstance(histograms[0], (TH2, TH3)):
            plot_func = plot_single_overlay_1d
            style_histograms(histograms)
            legend_labels = TLegend(0.65, 0.7, 0.9, 0.9)
            legend_labels.SetFillStyle(0)
            legend_labels.SetBorderSize(0)
            legend_labels.SetTextFont(43)
            legend_labels.SetTextSize(20)
            for h, cl in zip(histograms, current_labels):
                legend_labels.AddEntry(h, cl)
            more_objects.append(legend_labels)

        out_path = join(out_dir, f"{name}.png")
        plot_func(histograms, more_objects, out_path, labels)

    gSystem.RedirectOutput(c_char_p(0))
