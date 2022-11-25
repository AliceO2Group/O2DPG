#!/usr/bin/env python3

import sys
from os.path import join, exists, basename, dirname
from os import makedirs
from math import ceil
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

# Plot CPU, mem and time of a simulation workflow: subcommand plot-metrics
#
# usage: o2dpg_sim_metrics.py plot-metrics [-h] -p [PIPELINES ...] [--metrics-summary] [--cpu-eff] [--mem-usage] [--output OUTPUT] [--filter FILTER]

# options:
#   -h, --help            show this help message and exit
#   -p [PIPELINES ...], --pipelines [PIPELINES ...]
#                         pipeline_metric files from o2_dpg_workflow_runner
#   --metrics-summary     create the metrics summary
#   --cpu-eff             run only cpu efficiency evaluation
#   --mem-usage           run mem usage evaluation
#   --output OUTPUT       output_directory
#   --filter FILTER       regex to filter only on certain names in pipeline iterations
#
#
# make a new resource estimate based on previous runs
#
# usage: o2dpg_sim_metrics.py resource-estimate [-h] -p [PIPELINES ...] [--which [{mem,cpu} ...]] [--take {average,max,min}] [--output OUTPUT]

# options:
#   -h, --help            show this help message and exit
#   -p [PIPELINES ...], --pipelines [PIPELINES ...]
#                         pipeline_metric files from o2_dpg_workflow_runner
#   --which [{mem,cpu} ...]
#                         which resources to derive for estimate (cpu or mem or both)
#   --take {average,max,min}
#                         how to combine multiple pipeline_metric files
#   --output OUTPUT, -o OUTPUT
#                         JSON file with resource estimates to be passed to o2_dpg_workflow_runner
#
#
# make a text file which can be parsed by influxDB to visualise metrics
#
# usage: o2dpg_sim_metrics.py influx [-h] -p PIPELINE [--table-base TABLE_BASE] [--output OUTPUT] [--tags TAGS]

# options:
#   -h, --help            show this help message and exit
#   -p PIPELINE, --pipeline PIPELINE
#                         exactly one pipeline_metric file from o2_dpg_workflow_runner to prepare for InfluxDB
#   --table-base TABLE_BASE
#                         base name of InfluxDB table name
#   --output OUTPUT, -o OUTPUT
#                         output file name
#   --tags TAGS           key-value pairs, seperated by ";", for example: alidist=1234567;o2=7654321;tag=someTag


# metrics to be extracted
MET_TO_IND = {"time": 0, "cpu": 1, "uss": 2, "pss": 3}

# base categories to extract metrics for
CATEGORIES_RAW = ["sim", "digi", "reco", "pvfinder", "svfinder", "tpccluster", "match", "aod"]
CATEGORIES_REG = [re.compile(c, flags=re.IGNORECASE) for c in CATEGORIES_RAW]
CATEGORIES_EXCLUDE = ["", "QC", "", "", "", "QC", "QC", ""]

# detectors to extract metrics for
DETECTORS = ["rest", "ITS", "TOF", "EMC", "TRD", "PHS", "FT0", "HMP", "MFT", "FDD", "FV0", "MCH", "MID", "CPV", "ZDC", "TPC"]

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
  if not len(files):
    print("WARNING: Cannot derive number of timeframes, set it to 1")
    return 1
  return len(files)


def extract_time_single(path):
  with open(path, "r") as f:
    for l in f:
      if "walltime" in l:
        return float(l.strip().split()[-1])


def get_parent_category(proposed):
  """
  Match a base category to a proposed sub-category
  """
  cat = [cr for cr, creg, ce in zip(CATEGORIES_RAW, CATEGORIES_REG, CATEGORIES_EXCLUDE) if creg.search(proposed) and (not ce or ce not in proposed)]
  if not cat:
    #print(f"{proposed} not falling in one of the categories of interest")
    return None
  if len(cat) != 1:
    print(f"ERROR: Found more than 1 matching category")
    print(cat)
    return None
  return cat[0]


def jsonise_pipeline(path):
  if not exists(path):
      print(f"ERROR: pipeline_metrics file not found at {path}")
      return None

  # start with memory and CPU and construct the full dictionaries step-by-step
  json_pipeline = {"name": basename(path), "metric_name_to_index": MET_TO_IND, "iterations": []} 
  iterations = json_pipeline["iterations"]
  metrics_map = {}
  json_pipeline["summary"] = metrics_map
  with open(path, "r") as f:
    for l in f:
      l = l.strip().split()
      l = " ".join(l[3:])
      # make it JSON readable
      l = l.replace("'", '"')
      l = l.replace("None", "null")
      try:
        d = json.loads(l)
      except json.decoder.JSONDecodeError:
        # We just ignire this case
        # For instance, there might be lines like ***MEMORY LIMIT PASSED !!***
        continue
      if "iter" in d:
        iterations.append(d)
        name = d["name"]
        if name not in metrics_map:
            metrics_map[name] = [0] * len(MET_TO_IND)
        for metric in ["uss", "pss", "cpu"]:
          ind = MET_TO_IND[metric]
          # we are dealing here with multiple iterations for the same sub category due to the way the metrics monitoring works
          # let's take the maximum to be conservavtive
          metrics_map[name][ind] = max(metrics_map[name][ind], d[metric])

      elif "meta" not in json_pipeline and "mem_limit" in d:
        json_pipeline["meta"] = d

  # protect against potential str values there
  json_pipeline["meta"]["cpu_limit"] = float(json_pipeline["meta"]["cpu_limit"])
  json_pipeline["meta"]["mem_limit"] = float(json_pipeline["meta"]["mem_limit"])

  # add the number of timeframes
  ntfs = number_of_timeframes(dirname(path))
  json_pipeline["tags"] = {"ntfs": ntfs}

  files = find_files(dirname(path), "*.log_time", 1)
  if not files:
    return json_pipeline

  for f in files:
    # name from time log file
    name = f.split("/")[-1]
    name = re.sub("\.log_time$", "", name)
    time = extract_time_single(f)
    if name not in metrics_map:
      print(f"WARNING: Name {name} was not found while extracting times, probably that task was faster before at least one iteration could be monitored ({time}s)")
      metrics_map[name] = [0] * len(MET_TO_IND)
    metrics_map[name][0] = time

  return json_pipeline


def arrange_into_categories(json_pipeline):

    metrics_map = {}

    for cat_sub, metrics in json_pipeline["summary"].items():
        cat = get_parent_category(cat_sub)
        if not cat:
            # no parent category found
            continue
        if cat not in metrics_map:
            metrics_map[cat] = {}
        if cat_sub not in metrics_map[cat]:
            metrics_map[cat][cat_sub] = metrics
        if "sum" not in metrics_map[cat]:
            metrics_map[cat]["sum"] = [0.] * len(MET_TO_IND)

        for i in range(0, 4):
            metrics_map[cat]["sum"][i] += metrics_map[cat][cat_sub][i]

    return metrics_map


def make_default_figure(ax=None, **fig_args):
  """Make a default figure with one axes

  args:
    ax: matplorlib.pyplot.Axes (optional)
  """
  if ax is None:
    fig_args["figsize"] = fig_args.get("figsize", (20, 20))
    return plt.subplots(**fig_args)
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

  if not len(x) or not len(y):
    print("No data for plotting...")
    return figure, ax

  y = y.copy()
  x = [i for _, i in sorted(zip(y, x))]
  y.sort()
  if norm:
    total = sum(y)
    if total > 0:
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


def make_plot(x, y, xlabel, ylabel, ax=None, **kwargs):
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

  if not len(x) or not len(y):
    print("No data for plotting...")
    return figure, ax

  ax.plot(x, y, **kwargs)
  ax.tick_params("both", labelsize=30)
  ax.tick_params("x", rotation=45)
  ax.set_xlabel(xlabel, fontsize=30)
  ax.set_ylabel(ylabel, fontsize=30)

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

  if not len(labels) or not len(y):
    print("No data for plotting...")
    return figure, ax

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

  if not len(x) or not len(y):
    print("No data for plotting...")
    return

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


def extract_from_pipeline(json_pipeline, fields, filter=None):
  """
  Extract given fields from pipeline based on potential regex filter
  """
  iterations_y = [[] for _ in fields]
  iterations_x = [[] for _ in fields]
  for it in json_pipeline["iterations"]:
      if not check_regex(it["name"], filter):
        continue
      for j, f in enumerate(fields):
        this_iteration = iterations_y[j]
        if len(this_iteration) < it["iter"]:
          iterations_x[j].append(it["iter"] - 1)
          this_iteration.extend([0] * (it["iter"] - len(this_iteration)))
        this_iteration[it["iter"] - 1] += float(it[f])
  for i, it_x in enumerate(iterations_x):
    iterations_y[i] = [iterations_y[i][x] for x in it_x]
  return json_pipeline["name"], iterations_x, iterations_y


def make_for_influxDB(json_pipeline, tags, table_base_name, save_path):
  """
  Make metric files to be sent to InfluxDB for monitoring on Grafana
  """
  n_cpu = json_pipeline["meta"]["cpu_limit"]
  tags = ",".join([f"{k}={v}" for k, v in json_pipeline.get("tags", {}).items()])
  if tags:
    tags = f",{tags}"
  metrics = arrange_into_categories(json_pipeline)
  with open(save_path, "w") as f:
    for metric_name, metric_id in MET_TO_IND.items():
      tab_name = f"{table_base_name}_workflows_{metric_name}"
      db_string = f"{tab_name}{tags}"
      total = 0
      # fields are separated from the tags by a whitespace
      fields = []
      for cat, val in metrics.items():
        fields.append(f"{cat}={val['sum'][metric_id]}")
        total += val["sum"][metric_id]
      fields = ",".join(fields)
      db_string += f" {fields},total={total}"
      f.write(f"{db_string}\n")

      if metric_id == 0:
        # don't do the following for time
        continue
      _, _, iterations_y = extract_from_pipeline(json_pipeline, (metric_name,))
      tab_name = f"{table_base_name}_workflows_{metric_name}_per_cpu"
      iterations = [it / n_cpu if metric_id == 1 else it for it in iterations_y[0]]
      # now we need to make the string for influx DB
      db_string = f"{tab_name}{tags} minimum={min(iterations)},maximum={max(iterations)},average={sum(iterations) / len(iterations)}"
      f.write(f"{db_string}\n")

  return 0


def check_regex(to_check, filter):
  """
  Quickly check if to_check holds against regex filter
  """
  if not filter:
    return True
  return bool(re.search(filter, to_check))


def plot_mem_usage(json_pipelines, out_dir, filter=None, *, only_agerage=False):
  """
  Plotting the memory usage as a function of iterations
  Provide min, max and average in addition, particularly useful when investigating changes of resources needed by workflow
  """
  figure_pss, ax_pss = make_default_figure()
  figure_uss, ax_uss = make_default_figure()
  names = []
  averages_pss = []
  averages_uss = []
  min_pss = []
  max_pss = []
  min_uss = []
  max_uss = []

  linestyles = ["solid", "dashed", "dashdot"]
  for jp_i, jp in enumerate(json_pipelines):
    name, iterations_x, iterations_y = extract_from_pipeline(jp, ("pss", "uss"), filter)
    if not iterations_y[0] or not iterations_y[1]:
      continue
    names.append(f"{jp_i}_{name}")
    average_pss = sum(iterations_y[0]) / len(iterations_y[0])
    average_uss = sum(iterations_y[1]) / len(iterations_y[1])
    averages_pss.append(average_pss)
    averages_uss.append(average_uss)
    min_pss.append(min(iterations_y[0]))
    max_pss.append(max(iterations_y[0]))
    min_uss.append(min(iterations_y[1]))
    max_uss.append(max(iterations_y[1]))

    ls = linestyles[jp_i%len(linestyles)]

    make_plot(iterations_x[0], iterations_y[0], "sampling iterations", "PSS [MB]", ax_pss, label=name, ls=ls)
    make_plot(iterations_x[1], iterations_y[1], "sampling iterations", "USS [MB]", ax_uss, label=name, ls=ls)
    ax_pss.axhline(average_pss, color=ax_pss.lines[-1].get_color(), linestyle=ls)
    ax_pss.text(0, average_pss, f"Average: {average_pss:.2f} MB", fontsize=30)
    ax_uss.axhline(average_uss, color=ax_uss.lines[-1].get_color(), linestyle=ls)
    ax_uss.text(0, average_uss, f"Average: {average_uss:.2f} MB", fontsize=30)

  ax_pss.legend(loc="best")
  ax_uss.legend(loc="best")

  save_figure(figure_pss, join(out_dir, f"pss_vs_iterations.png"))
  save_figure(figure_uss, join(out_dir, f"uss_vs_iterations.png"))

  if len(json_pipelines) > 1:
    figure, ax = make_default_figure()
    make_plot(names, averages_pss, "pipeline names", "PSS [MB]", ax, label="average", ls=linestyles[0])
    make_plot(names, min_pss, "pipeline names", "PSS [MB]", ax, label="min", ls=linestyles[1])
    make_plot(names, max_pss, "pipeline names", "PSS [MB]", ax, label="max", ls=linestyles[2])
    ax.tick_params("x", rotation=90)
    ax.legend(loc="best", fontsize=20)
    save_figure(figure, join(out_dir, f"pss_min_max_average.png"))
    figure, ax = make_default_figure()
    make_plot(names, averages_uss, "pipeline names", "USS [MB]", ax, label="average", ls=linestyles[0])
    make_plot(names, min_uss, "pipeline names", "USS [MB]", ax, label="min", ls=linestyles[1])
    make_plot(names, max_uss, "pipeline names", "USS [MB]", ax, label="max", ls=linestyles[2])
    ax.tick_params("x", rotation=90)
    ax.legend(loc="best", fontsize=20)
    save_figure(figure, join(out_dir, f"uss_min_max_average.png"))


def plot_cpu_eff(json_pipelines, out_dir, filter=None):
  """
  Plotting the memory usage as a function of iterations
  Provide min, max and average in addition, particularly useful when investigating changes of resources needed by workflow
  """
  names = []
  averages = []
  mins = []
  maxs = []
  figure, ax = make_default_figure()
  linestyles = ["solid", "dashed", "dashdot"]
  for jp_i, jp in enumerate(json_pipelines):
    name, iterations_x, iterations_y = extract_from_pipeline(jp, ("cpu",), filter)
    ls = linestyles[jp_i%len(linestyles)]
    n_cpu = jp["meta"]["cpu_limit"]
    iterations = [it / n_cpu for it in iterations_y[0]]
    if not iterations:
      continue
    names.append(f"{jp_i}_{name}")
    average = sum(iterations) / len(iterations)
    mins.append(min(iterations))
    maxs.append(max(iterations))
    averages.append(average)

    make_plot(iterations_x[0], iterations, "sampling iterations", "CPU efficiency [%]", ax, label=name, ls=ls)
    ax.axhline(average, color=ax.lines[-1].get_color(), linestyle=ls)
    ax.text(0, average, f"Average: {average:.2f} [%]", fontsize=30)

  ax.legend(loc="best")
  save_figure(figure, join(out_dir, f"cpu_efficiency_vs_iterations.png"))

  if len(json_pipelines) > 1:
    figure, ax = make_default_figure()
    make_plot(names, averages, "pipeline names", "CPU efficiency [%]", ax, label="average", ls=linestyles[0])
    make_plot(names, mins, "pipeline names", "CPU efficiency [%]", ax, label="minimum", ls=linestyles[1])
    make_plot(names, maxs, "pipeline names", "CPU efficiency [%]", ax, label="maximum", ls=linestyles[2])
    ax.tick_params("x", rotation=90)
    ax.legend(loc="best", fontsize=20)
    save_figure(figure, join(out_dir, f"cpu_efficiency_min_max_average.png"))


def plot(args):
    if not args.metrics_summary and not args.cpu and not args.mem:
        # if nothing is given explicitly, do everything
        args.metrics_summary, args.cpu, args.mem = (True, True, True)
    
    out_dir = args.output
    if not exists(out_dir):
      makedirs(out_dir)
    
    metrics_maps = []
    metrics_maps_categories = []

    # collect pipeline names for which no times could be extracted
    no_times = []
    
    for m in args.pipelines:
        metrics_maps.append(jsonise_pipeline(m))
        metrics_maps_categories.append(arrange_into_categories(metrics_maps[-1]))

    if args.metrics_summary:
      # a unified color map
      cmap = matplotlib.cm.get_cmap("coolwarm")
      
      for mm, mmc in zip(metrics_maps, metrics_maps_categories):
        cats = []
        vals = [[] for _ in range(4)]
        for cat, val in mmc.items():
          cats.append(cat)
          for i, _ in enumerate(vals):
            vals[i].append(val["sum"][i])
        if any(vals[0]):
          plot_histo_and_pie(cats, vals[0], "sim category", "$\sum_{i\in\mathrm{tasks}} \mathrm{walltime}_i\,[s]$", join(out_dir, f"walltimes_{mm['name']}.png"), cmap=cmap, title="TIME (per TF)", scale=1./mm["tags"]["ntfs"])
        else:
          no_times.append(mm["name"])
        plot_histo_and_pie(cats, vals[1], "sim category", "$\sum_{i\in\mathrm{tasks}} \mathrm{CPU}_i\,[\%]$", join(out_dir, f"cpu_{mm['name']}.png"), cmap=cmap, title="CPU (per TF)", scale=1./mm["tags"]["ntfs"])
        plot_histo_and_pie(cats, vals[2], "sim category", "$\sum_{i\in\mathrm{tasks}} \mathrm{USS}_i\,[MB]$", join(out_dir, f"uss_{mm['name']}.png"), cmap=cmap, title="USS (per TF)", scale=1./mm["tags"]["ntfs"])
        plot_histo_and_pie(cats, vals[3], "sim category", "$\sum_{i\in\mathrm{tasks}} \mathrm{PSS}_i\,[MB]$", join(out_dir, f"pss_{mm['name']}.png"), cmap=cmap, title="PSS (per TF)", scale=1./mm["tags"]["ntfs"])

        # Make pie charts for digit and reco
        if any(vals[0]):
          plot_any(make_pie, join(out_dir, f"digi_time_{mm['name']}.png"), *filter_metric_per_detector(mmc, "digi", "time"), cmap=cmap, title="Time digitization")
          plot_any(make_pie, join(out_dir, f"reco_time_{mm['name']}.png"), *filter_metric_per_detector(mmc, "reco", "time"), cmap=cmap, title="Time econstruction")
        plot_any(make_pie, join(out_dir, f"digi_cpu_{mm['name']}.png"), *filter_metric_per_detector(mmc, "digi", "cpu"), cmap=cmap, title="CPU digitzation")
        plot_any(make_pie, join(out_dir, f"reco_cpu_{mm['name']}.png"), *filter_metric_per_detector(mmc, "reco", "cpu"), cmap=cmap, title="CPU reconstruction")

      if no_times:
        print("WARNING: For the following pipelines, no times could be extracted:")
        for nt in no_times:
          print(f"  {nt}")

    if args.mem:
      plot_mem_usage(metrics_maps, out_dir, args.filter)
    if args.cpu:
      plot_cpu_eff(metrics_maps, out_dir, args.filter)

    return 0


def influx(args):
  
  json_pipeline = jsonise_pipeline(args.pipeline)
  if args.tags:
        pairs = args.tags.split(";")
        for p in pairs:
            key_val = p.split("=")
            if len(key_val) != 2:
                print(f"WARNING: Found invalid key-value pair {p}, skip")
                continue
            json_pipeline["tags"][key_val[0]] = key_val[1]

  return make_for_influxDB(json_pipeline, json_pipeline["tags"], args.table_base, args.output)


def resources(args):

    # Collect all metrics we got
    json_pipelines = [jsonise_pipeline(m) for m in args.pipelines]
    # We will finally use the intersection of task names
    intersection = [m for m in json_pipelines[0]["summary"]]
    # union is built as a cross check, TODO, could be used to identify very fast tasks as well
    union = [m for m in json_pipelines[0]["summary"]]
    # collect number of timeframes for each metrics file
    ntfs = [json_pipelines[-1]["tags"]["ntfs"]]

    for jp in json_pipelines[1:]:
        intersection = list(set(intersection) & set([m for m in jp["summary"]]))
        union = list(set(intersection) | set([m for m in jp["summary"]]))
        ntfs.append(jp["tags"]["ntfs"])

    if len(intersection) != len(union):
        print("WARNING: Input metrics seem to be different, union and intersection do not have the same length, using intersection. This can however happen when some tasks finish super fast")

    # quick helper to remove TF suffices
    def unique_names_wo_tf_suffix(name, tasks_per_tf_, tasks_no_tf_):
        name_split = name.split("_")
        try:
            # assume "_<int>" to reflect a TF suffix
            tf = int(name_split[-1])
            name = "_".join(name_split[:-1])
            tasks_per_tf_.append(name)
        except ValueError:
            tasks_no_tf_.append(name)

    tasks_per_tf = []
    tasks_no_tf = []

    for name in intersection:
        unique_names_wo_tf_suffix(name, tasks_per_tf, tasks_no_tf)
    # We treat every tf the same, none of those is special, so strip TF suffices and get unique list of names
    tasks_per_tf = list(set(tasks_per_tf))

    # what to do in case there were multiple metrics files given as input
    derive_func = {"average": lambda l: sum(l) / len(l),
                   "min": min,
                   "max": max}[args.take]
    # Collect here
    resources_map = {t: {} for t in tasks_per_tf + tasks_no_tf}
    # now let's only take what we are interested in
    metrics = [jp["summary"] for jp in json_pipelines]
    # for convenience
    scaling_map = {"mem": lambda x: int(x), "cpu": lambda x: ceil(x * 0.01)}
    # for the workflows we specify mem and cpu, in the metrics we have pss/uss and cpu
    metrics_name_map = {"mem": "uss", "cpu": "cpu"}

    for w in args.which:
        met_ind = MET_TO_IND[metrics_name_map[w]]
        scale = scaling_map[w]
        for tptf in tasks_per_tf:
            values = []
            for met, n in zip(metrics, ntfs):
                this_value = 0
                for i in range(1, n + 1):
                    key = f"{tptf}_{i}"
                    # It could happen that a task is missing in a certain TF, e.g. when it went through fast enough to not leave a trace in pipeline iterations
                    if key not in met:
                        continue
                    # now do per TF in current metrics, here we always take the max for now ==> conservative
                    this_value = max(met[key][met_ind], this_value)
                values.append(this_value)
            resources_map[tptf][w] = scale(derive_func(values))

        for tntf in tasks_no_tf:
            resources_map[tntf][w] = scale(derive_func([met[tntf][met_ind] for met in metrics]))

    # finally save to JSON
    with open(args.output, "w") as f:
        json.dump(resources_map, f, indent=2)


def main():

  parser = argparse.ArgumentParser(description="Metrics evaluation of O2 simulation workflow")
  sub_parsers = parser.add_subparsers(dest="command")

  plot_parser = sub_parsers.add_parser("plot-metrics", help="Plot (multiple) metrcis from extracted metrics JSON file(s)")
  plot_parser.set_defaults(func=plot)
  plot_parser.add_argument("-p", "--pipelines", nargs="*", help="pipeline_metric files from o2_dpg_workflow_runner", required=True)
  plot_parser.add_argument("--metrics-summary", dest="metrics_summary", action="store_true", help="create the metrics summary")
  plot_parser.add_argument("--cpu", dest="cpu", action="store_true", help="run only cpu efficiency evaluation")
  plot_parser.add_argument("--mem", dest="mem", action="store_true", help="run mem usage evaluation")
  plot_parser.add_argument("--output", help="output_directory", default="metrics_summary")
  plot_parser.add_argument("--filter", help="regex to filter only on certain names in pipeline iterations")

  influx_parser = sub_parsers.add_parser("influx", help="Derive a format which can be sent to InfluxDB")
  influx_parser.set_defaults(func=influx)
  influx_parser.add_argument("-p", "--pipeline", help="exactly one pipeline_metric file from o2_dpg_workflow_runner to prepare for InfluxDB", required=True)
  influx_parser.add_argument("--table-base", dest="table_base", help="base name of InfluxDB table name", default="O2DPG_MC")
  influx_parser.add_argument("--output", "-o", help="output file name", default="metrics_influxDB.dat")
  influx_parser.add_argument("--tags", help="key-value pairs, seperated by \";\", for example: alidist=1234567;o2=7654321;tag=someTag")

  resource_parser = sub_parsers.add_parser("resource-estimate", help="Derive resource estimate from metrics to be passed to workflow runner")
  resource_parser.set_defaults(func=resources)
  resource_parser.add_argument("-p", "--pipelines", nargs="*", help="pipeline_metric files from o2_dpg_workflow_runner", required=True)
  resource_parser.add_argument("--which", help="which resources to derive for estimate (cpu or mem or both)", nargs="*", choices=["mem", "cpu"], default=["mem", "cpu"])
  resource_parser.add_argument("--take", help="how to combine multiple pipeline_metric files", default="average", choices=["average", "max", "min"])
  resource_parser.add_argument("--output", "-o", help="JSON file with resource estimates to be passed to o2_dpg_workflow_runner", default="resource_estimates.json")

  args = parser.parse_args()
  return args.func(args)

if __name__ == "__main__":
  sys.exit(main())
