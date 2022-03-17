#!/usr/bin/env python3

import sys
from os.path import join, exists, basename, dirname, abspath
from os import makedirs
import argparse
import re
from glob import glob
import matplotlib.pyplot as plt
import matplotlib
import json


################################################################
#                                                              #
# script to exctract and plot metrics of a simulation workflow #
#                                                              #
################################################################

# example usage
# o2dpg_sim_metrics.py --path <path/to/pipeline_metrics.log> -o <output/directory>
#
# calculates and plots
# 1. overall CPU efficiency (--cpu-eff)
# 2. metrics of different simulation categories (--metrics-summary)
# in addition it can create a file which can be uploaded to InfluxDB for further usage, e.g. Grafana (--influxdb-file)

# metrics to be extracted
MET_TO_IND = {"time": 0, "cpu": 1, "uss": 2, "pss": 3}

# base categories to extract metrics for
CATEGORIES_RAW = ["sim", "digi", "reco", "pvfinder", "svfinder", "tpccluster", "match", "aod"]
CATEGORIES_REG = [re.compile(c, flags=re.IGNORECASE) for c in CATEGORIES_RAW]
CATEGORIES_EXCLUDE = ["", "QC", "", "", "", "QC", "QC", ""]

# detectors to extract metrics for
DETECTORS = ["ITS", "TOF", "EMC", "TRD", "PHS", "FT0", "HMP", "MFT", "FDD", "FV0", "MCH", "MID", "CPV", "ZDC", "TPC"]

def find_files(path, search, depth=0):
  files = []
  for d in range(depth + 1):
    wildcards = "/*" * d
    path_search = path + wildcards + f"/{search}"
    files.extend(glob(path_search))
  return files


def number_of_timeframes(path):
  """
  Derive number of timeframes from what is found in path
  """
  files = find_files(path, "tf*")
  return max(len(files), 1)


def extract_time_single(path):
  with open(path, "r") as f:
    for l in f:
      if "walltime" in l:
        return float(l.strip().split()[-1])


def match_category(proposed):
  """
  Match a base category to a proposed sub-category
  """
  cat = [cr for cr, creg, ce in zip(CATEGORIES_RAW, CATEGORIES_REG, CATEGORIES_EXCLUDE) if creg.search(proposed) and (not ce or ce not in proposed)]
  if not cat:
    #print(f"{proposed} not falling in one of the categories of interest")
    return None, None
  if len(cat) != 1:
    print(f"ERROR: Found more than 1 matching category")
    print(cat)
    return None, None
  return cat[0], proposed


def extract_cpu_usage(pipeline_metrics):
  iterations = []
  for pm in pipeline_metrics:
    if len(iterations) < pm["iter"]:
      # NOTE that iterations start at 1 and NOT at 0
      iterations.extend([0] * (pm["iter"] - len(iterations)))
    iterations[pm["iter"] - 1] += pm["cpu"]
  return iterations


def make_cat_map(pipeline_path):
  """
  Extract and calculate metrcis and CPU efficiency from pipeline_metrics (which was created by the o2_workflow_runner)
  """
  # start with memory and CPU and construct the full dictionaries step-by-step
  current_pipeline = {"name": basename(pipeline_path), "metrics": {}} 
  current_pipeline_metrics = []
  with open(pipeline_path, "r") as f:
    for l in f:
      l = l.strip().split()
      l = " ".join(l[3:])
      # make it JSON readable
      l = l.replace("'", '"')
      l = l.replace("None", "null")
      d = json.loads(l)
      if "iter" in d:
        current_pipeline_metrics.append(d)
      elif "meta" not in current_pipeline and "mem_limit" in d:
        current_pipeline["meta"] = d

  cpu_limit = current_pipeline["meta"]["cpu_limit"]
  # scale by constraint number of CPUs
  current_pipeline["cpu_efficiencies"] = [e / cpu_limit for e in extract_cpu_usage(current_pipeline_metrics)]

  metrics_map = {}
  for mm in current_pipeline_metrics:
    name = mm["name"]
    cat, cat_sub = match_category(name)
    if not cat:
      continue
    if cat not in metrics_map:
      metrics_map[cat] = {}
    if cat_sub not in metrics_map[cat]:
      metrics_map[cat][cat_sub] = [0.] * len(MET_TO_IND)
    if "sum" not in metrics_map[cat]:
      metrics_map[cat]["sum"] = [0.] * len(MET_TO_IND)
    for metric in ["uss", "pss", "cpu"]:
      ind = MET_TO_IND[metric]
      # we are dealing here with multiple iterations for the same sub category due to the way the metrics monitoring works
      # let's take the maximum to be conservavtive
      metrics_map[cat][cat_sub][ind] = max(metrics_map[cat][cat_sub][ind], mm[metric])
  for i in range(1, 4):
    for cat, sub_cat in metrics_map.items():
      for sc, val in sub_cat.items():
        if sc == "sum":
          # not add the sum to the sum
          continue
        sub_cat["sum"][i] += val[i]

  # add walltimes
  files = find_files(dirname(pipeline_path), "*.log_time", 1)
  if not files:
    print(f"No files found in {path}")
    return None
  for f in files:
    # find category
    cat_f = f.split("/")[-1]
    cat_f = re.sub("\.log_time$", "", cat_f)
    cat, cat_sub = match_category(cat_f)
    if not cat:
      continue
    if cat not in metrics_map:
      continue
    if cat_sub not in metrics_map[cat]:
      continue
    walltime = extract_time_single(f)
    metrics_map[cat]["sum"][0] += walltime
    metrics_map[cat][cat_sub][0] = walltime

  current_pipeline["metrics"] = metrics_map

  return current_pipeline


def make_default_figure(ax=None):
  """Make a default figure with one axes

  args:
    ax: matplorlib.pyplot.Axes (optional)
  """
  if ax is None:
    return plt.subplots(figsize=(20, 20))
  else:
    return ax.get_figure, ax


def save_figure(figure, path):
  """
  Wrap last steps of figure creation, tight_layout, saving and closing

  args:
    figure: matplotlib.pyplot.Figure
      figure to be saved
    path: str
      where to save
  """
  figure.tight_layout()
  figure.savefig(path, bbox_inches="tight")
  plt.close(figure)


def make_histo(x, y, xlabel, ylabel, ax=None, cmap=None, norm=True, title=None, **kwargs):
  """
  Make a histogram

  args:
    x, y: iterables
      x- and y-axis values
    xlabel, ylable: str
      labels to be put on x- and y-axis
    ax: matplorlib.pyplot.Axes (optional)
      axes where to plot the histogram
    cmap: matplotlib.cmap
      color the pieces according to their size
    norm: bool
      whether or not normalising to histogram's sum
    title:
      title to be put for figure
  """
  figure, ax = make_default_figure(ax)

  y = y.copy()
  x = [i for _, i in sorted(zip(y, x))]
  y.sort()
  if norm:
    total = sum(y)
    y = [i / total for i in y]
  colors = None
  if cmap:
    step = 1. / len(y)
    colors = [cmap(i * step) for i, _ in enumerate(y)]
  ax.bar(x, y, color=colors)
  ax.set_xticks(range(len(x)))
  ax.set_xticklabels(x)
  ax.tick_params("both", labelsize=30)
  ax.tick_params("x", rotation=45)
  ax.set_xlabel(xlabel, fontsize=30)
  ax.set_ylabel(ylabel, fontsize=30)

  if title:
    figure.suptitle(title, fontsize=40)

  return figure, ax


def make_plot(x, y, xlabel, ylabel, ax=None, title=None, **kwargs):
  """
  Make a histogram

  args:
    x, y: iterables
      x- and y-axis values
    xlabel, ylable: str
      labels to be put on x- and y-axis
    ax: matplorlib.pyplot.Axes (optional)
      axes where to plot the histogram
    cmap: matplotlib.cmap
      color the pieces according to their size
    norm: bool
      whether or not normalising to histogram's sum
    title:
      title to be put for figure
  """
  figure, ax = make_default_figure(ax)

  ax.plot(x, y)
  ax.tick_params("both", labelsize=30)
  ax.tick_params("x", rotation=45)
  ax.set_xlabel(xlabel, fontsize=30)
  ax.set_ylabel(ylabel, fontsize=30)

  if title:
    figure.suptitle(title, fontsize=40)

  return figure, ax


def make_pie(labels, y, ax=None, cmap=None, title=None, **kwargs):
  """
  Make a pie chart

  args:
    labels: iterable of str
      labels to be put per piece
    y: iterable
      relative size of piece
    cmap: matplotlib.cmap
      color the pieces according to their size
    title: str
      title to be put for figure
  """
  figure, ax = make_default_figure(ax)
  y = y.copy()
  labels = [l for _, l in sorted(zip(y, labels))]
  y.sort()
  colors = None
  if cmap:
    step = 1. / len(y)
    colors = [cmap(i * step) for i, _ in enumerate(y)]
  explode = [0.05 for _ in y]
  ax.pie(y, explode=explode, labels=labels, autopct="%1.1f%%", startangle=90, textprops={"fontsize": 30}, colors=colors)
  ax.axis("equal")

  if title:
    figure.suptitle(title, fontsize=40)

  return figure, ax


def plot_histo_and_pie(x, y, xlabel, ylabel, path, **kwargs):
  """
  Plot 3 axes:
  1. absolute values
  2. relative values
  3. same as 2. but pie chart

  args:
    x, y: iterables
      x- and y-axis values
    xlabel, ylable: str
      labels to be put on x- and y-axis
    path: str
      where to be saved
    kwargs: dict
      title: str
        title to be put for figure
      scale: float
        scale before plotting
  """
  figure, axes = plt.subplots(1, 3, figsize=(60, 20))
  title = kwargs.pop("title", None)
  scale = kwargs.pop("scale", 1.)
  y = [i * scale for i in y]
  make_histo(x, y, xlabel, ylabel, axes[0], norm=False, **kwargs)
  make_histo(x, y, xlabel, f"{ylabel}, relative", axes[1], norm=True, **kwargs)
  make_pie(x, y, axes[2], **kwargs)
  if title:
    figure.suptitle(title, fontsize=60)
  save_figure(figure, path)


def plot_any(make_func, path, *args, **kwargs):
  figure, ax = make_func(*args, **kwargs)
  save_figure(figure, path)


def accumulate(metric_map, regex, metric):
  """accumulate where keys satisfy someregex
  """
  s = 0.
  found = False
  met_id = MET_TO_IND[metric]
  for k, v in metric_map.items():
    if regex.search(k):
      s += v[met_id]
      found = True
  return s if found else None


def filter_metric_per_detector(metrics, cat, metric):
  """
  Filter a main category per detector
  args:
    metrics: dict
      full metric dictionary of all metrics per category and detector
    cat: str
      category name
    metric: str
      metric's name to be extracted
  """
  if cat not in metrics:
    print(f"Categoy {cat} not in map...")
    return

  labels_raw = [f"{d}{cat}" for d in DETECTORS]
  labels_search = [re.compile(l, flags=re.IGNORECASE) for l in labels_raw]
  acc_list = []
  labels = []
  for lr, ls in zip(labels_raw, labels_search):
    acc = accumulate(metrics[cat], ls, metric)
    if acc is None:
      continue
    labels.append(lr)
    acc_list.append(acc)

  total = sum(acc_list)
  acc_list = [a / total * 100. for a in acc_list]
  return labels, acc_list


def make_for_influxDB(full_map, table_base_name, save_path):
  """
  Make metric files to be sent to InfluxDB for monitoring on Grafana
  """
  tags = full_map["tags"]
  metrics = full_map["metrics"]
  with open(save_path, "w") as f:
    for metric_name, metric_id in MET_TO_IND.items():
      tab_name = f"{table_base_name}_workflows_{metric_name}"
      fields = ",".join([f"{k}={v}" for k, v in tags.items()])
      db_string = f"{tab_name},{fields}"
      total = 0
      for cat, val in metrics.items():
        db_string += f",{cat}={val['sum'][metric_id]}"
        total += val["sum"][metric_id]
      db_string += f",total={total}"
      f.write(f"{db_string}\n")


def run(args):
  """
  Top level run function
  """
  if not args.metrics_summary and not args.influxdb_file and not args.cpu_eff:
    # if nothing is given explicitly, do everything
    args.metrics_summary, args.influxdb_file, args.cpu_eff = (True, True, True)

  # organise paths
  full_path = abspath(args.path)
  if not exists(full_path):
    print(f"ERROR: pipeline_metrics file not found at {full_path}")
    return 1
  dir_path = dirname(full_path)

  # extract metrics for this pipeline
  save_map = make_cat_map(full_path)
  if not save_map:
    return 1

  # create the common output directory
  out_dir = join(dir_path, args.output)
  if not exists(out_dir):
    makedirs(out_dir)

  # add the number of timeframes
  ntfs = number_of_timeframes(dir_path)
  save_map["tags"] = {"ntfs": ntfs}

  # Add some more tags specified by the user
  if args.tags:
    pairs = args.tags.split(";")
    for p in pairs:
      key_val = p.split("=")
      if len(key_val) != 2:
        print(f"ERROR: Found invalid key-value pair {p}")
        continue
      save_map["tags"][key_val[0]] = key_val[1]

  if args.influxdb_file:
    # make file to send to influxDB
    make_for_influxDB(save_map, args.influxdb_table_base, join(out_dir, "metrics_influxDB.dat"))

  if args.metrics_summary:
    # all metrics to one JSON
    json_path = join(out_dir, "metrics.json")
    with open(json_path, "w") as f:
      json.dump(save_map, f, indent=2)

    # get only the metrics here
    metrics = save_map["metrics"]

    # a unified color map
    cmap = matplotlib.cm.get_cmap("coolwarm")

    cats = []
    vals = [[] for _ in range(4)]
    for cat, val in metrics.items():
      cats.append(cat)
      vals[0].append(val["sum"][0])
      vals[1].append(val["sum"][1])
      vals[2].append(val["sum"][2])
      vals[3].append(val["sum"][3])
    plot_histo_and_pie(cats, vals[0], "sim category", "walltime [s]", join(out_dir, "walltimes.png"), cmap=cmap, title="TIME (per TF)", scale=1./ntfs)
    plot_histo_and_pie(cats, vals[1], "sim category", "CPU [%]", join(out_dir, "cpu.png"), cmap=cmap, title="CPU (per TF)", scale=1./ntfs)
    plot_histo_and_pie(cats, vals[2], "sim category", "USS [MB]", join(out_dir, "uss.png"), cmap=cmap, title="USS (per TF)", scale=1./ntfs)
    plot_histo_and_pie(cats, vals[3], "sim category", "PSS [MB]", join(out_dir, "pss.png"), cmap=cmap, title="PSS (per TF)", scale=1./ntfs)

    # Make pie charts for digit and reco
    plot_any(make_pie, join(out_dir, "digi_time.png"), *filter_metric_per_detector(metrics, "digi", "time"), cmap=cmap, title="Time digitization")
    plot_any(make_pie, join(out_dir, "reco_time.png"), *filter_metric_per_detector(metrics, "reco", "time"), cmap=cmap, title="Time econstruction")
    plot_any(make_pie, join(out_dir, "digi_cpu.png"), *filter_metric_per_detector(metrics, "digi", "cpu"), cmap=cmap, title="CPU digitzation")
    plot_any(make_pie, join(out_dir, "reco_cpu.png"), *filter_metric_per_detector(metrics, "reco", "cpu"), cmap=cmap, title="CPU reconstruction")

  if args.cpu_eff:
    effs = save_map["cpu_efficiencies"]
    if effs:
      pipeline_name = basename(full_path)
      cpu_limit = save_map["meta"]["cpu_limit"]
      effs = [e / cpu_limit for e in effs]
      figure, ax = make_plot(range(len(effs)), effs, "sampling iteration", "CPU efficiency [%]", title=pipeline_name)
      global_eff = sum(effs) / len(effs)
      ax.axhline(global_eff, color="black")
      ax.text(0, global_eff, f"Overall efficiency: {global_eff:.2f} %", fontsize=30)
      save_figure(figure, join(out_dir, f"cpu_efficiency_{pipeline_name}.png"))

  return 0


def main():

  parser = argparse.ArgumentParser(description="Metrics evaluation of O2 simulation workflow")
  parser.add_argument("--path", help="path to pipeline_metrics file to be evaluated", required=True)
  parser.add_argument("--tags", help="key-value pairs, seperated by ;, example: alidist=1234567;o2=7654321;tag=someTag")
  parser.add_argument("--metrics-summary", dest="metrics_summary", action="store_true", help="create the metrics summary")
  parser.add_argument("--cpu-eff", dest="cpu_eff", action="store_true", help="run only cpu efficiency evaluation")
  parser.add_argument("--influxdb-file", dest="influxdb_file", action="store_true", help="prepare a file to be uploaded to InfluxDB")
  parser.add_argument("--influxdb-table-base", dest="influxdb_table_base", help="base name of InfluxDB table name", default="O2DPG_MC")
  parser.add_argument("--output", help="output_directory", default="metrics_summary")

  args = parser.parse_args()
  return run(args)

if __name__ == "__main__":
  sys.exit(main())
