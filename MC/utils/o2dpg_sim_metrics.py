#!/usr/bin/env python3

import sys
from os.path import join, exists, basename
from os import makedirs
from copy import deepcopy
import argparse
import re
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib
import json
import numpy as np
import pandas as pd
import seaborn as sns

############################################################################
#                                                                          #
# script to inspect resources (CPU, mem and time) of a simulation workflow #
#                                                                          #
############################################################################

# Plot history and resource needs of several categories (sim, digi, reco) of simulation workflows: subcommand history
# usage: o2dpg_sim_metrics_df.py history [-h] -p [PIPELINES ...] [--output OUTPUT] [--filter-task FILTER_TASK] [--suffix SUFFIX]

# optional arguments:
#   -h, --help            show this help message and exit
#   -p [PIPELINES ...], --pipelines [PIPELINES ...]
#                         pipeline_metric files from o2_dpg_workflow_runner
#   --output OUTPUT       output_directory
#   --filter-task FILTER_TASK
#                         regex to filter only on certain task names in pipeline iterations
#   --suffix SUFFIX       a suffix put at the end of the output file names

# Compare resources of simulation workflows based on different values
# of e.g. centre-of-mass energy, number of events etc.: subcommand history
# usage: o2dpg_sim_metrics_df.py compare [-h] -p [PIPELINES ...] [--output OUTPUT] [--names [NAMES ...]] --feature {col,eCM,gen,ns,nb,j,cpu_limit,mem_limit}

# optional arguments:
#   -h, --help            show this help message and exit
#   -p [PIPELINES ...], --pipelines [PIPELINES ...]
#                         pipeline_metric files from o2_dpg_workflow_runner
#   --output OUTPUT       output_directory
#   --names [NAMES ...]   assign one custom name per pipeline
#   --feature {col,eCM,gen,ns,nb,j,cpu_limit,mem_limit}
#                         feature to be investigated

# Make a file that can be uploaded to influxDB with several metrics similar to what is computed by history
# usage: o2dpg_sim_metrics_df.py influx [-h] -p PIPELINE [--table-base TABLE_BASE] [--output OUTPUT] [--tags TAGS]

# optional arguments:
#   -h, --help            show this help message and exit
#   -p PIPELINE, --pipeline PIPELINE
#                         exactly one pipeline_metric file from o2_dpg_workflow_runner to prepare for InfluxDB
#   --table-base TABLE_BASE
#                         base name of InfluxDB table name
#   --output OUTPUT, -o OUTPUT
#                         output file name
#   --tags TAGS           key-value pairs, seperated by ";", for example: alidist=1234567;o2=7654321;tag=someTag

METRIC_NAME_CPU = "cpu"
METRIC_NAME_USS = "uss"
METRIC_NAME_PSS = "pss"
METRIC_NAME_TIME = "time"

# metrics that are extracted by the o2_dpg_workflow_runner and put in pipeline_metric*.log
METRICS = [METRIC_NAME_CPU, METRIC_NAME_USS, METRIC_NAME_PSS, METRIC_NAME_TIME]

# some features of MC runs, these can be extracted from the meta information
# use these when multiple pipelines are given and we want to extract comparison plots for those based on these features
# in principle, any argument from o2dpg_sim_workflow.py could be used, but for now let's limit to these
FEATURES = ["col", "eCM", "gen", "ns", "nb", "j", "cpu_limit", "mem_limit"]

# base categories to extract metrics for
CATEGORIES_RAW = ["sim", "digi", "reco", "pvfinder", "svfinder", "tpccluster", "match", "aod"]
CATEGORIES_REG = [re.compile(c, flags=re.IGNORECASE) for c in CATEGORIES_RAW]
CATEGORIES_EXCLUDE = ["", "QC", "", "", "", "QC", "QC", ""]


def get_parent_category(proposed):
  """
  Match a base category to a proposed sub-category
  """
  cat = [cr for cr, creg, ce in zip(CATEGORIES_RAW, CATEGORIES_REG, CATEGORIES_EXCLUDE) if creg.search(proposed) and (not ce or ce not in proposed)]
  if not cat:
    return None
  if len(cat) != 1:
    print(f"ERROR: Found more than 1 matching category")
    return None
  return cat[0]


def line_to_dict(l):
  """
  turn a single line read from a file to JSON and return as dict
  """
  l = l.strip().split()
  # the first column is the date, the second column is the time from the Python logger
  # NOTE replace "," with "." for milliseconds. Seems not to be valid ISO format for Python 3.9, however it is in Python 3.11)
  date_time = " ".join(l[:2]).replace(",", ".")
  seconds_since_epoch = datetime.fromisoformat(date_time).timestamp()
  # this is to remove the time and other fields from the logger
  l = " ".join(l[3:])
  # make it JSON readable
  l = l.replace("'", '"')
  l = l.replace("None", "null")
  l = l.replace("False", "false")
  l = l.replace("True", "true")

  try:
    d = json.loads(l)
    d[METRIC_NAME_TIME] = seconds_since_epoch
    return d
  except json.decoder.JSONDecodeError as e:
    # We just ignire this case
    # For instance, there might be lines like ***MEMORY LIMIT PASSED !!***
    pass
  return None


def convert_to_float_if_possible(value):
  """
  take any value and try to convert to float
  """
  if isinstance(value, bool):
    # do not cast booleans
    return value
  try:
    return float(value)
  except (TypeError, ValueError):
    pass
  return value


class Resources:
  """
  A wrapper class for resources

  holds resources as pandas dataframe as well as some other useful info
  """

  def __init__(self, pipeline_path=None):
    # this will be extended on-the-fly. However, we will add one more key, namely the timeframe, manually
    self.dict_for_df = {"timeframe": [], "category": []}
    self.meta = None
    self.df = None
    self.number_of_timeframes = None
    self.name = None

    if pipeline_path:
      self.extract_from_pipeline(pipeline_path)

  def __add__(self, other):
    """
    So that we can add Resource objects
    """
    res = Resources()
    res.df = pd.concat([self.df, other.df], ignore_index=True)
    res.number_of_timeframes = self.number_of_timeframes + other.number_of_timeframes
    return res

  def check(self):
    """
    Make sure dictionary is complete to be put in dataframe
    """
    length = None
    for key, rows in self.dict_for_df.items():
      if length is None:
        length = len(rows)
        continue
      if length != len(rows):
        print(f"Key {key} has different number of rows ({len(rows)}) than expected ({length})")
        return False
    return True

  def add_meta(self):
    """
    Add the rows for meta info
    """
    length = len(self.dict_for_df[list(self.dict_for_df.keys())[0]])
    for key, value in self.meta.items():
      self.dict_for_df[key] = [value] * length

  def convert_columns_to_float_if_possible(self):
    """
    make sure we have numbers where we can

    In the pipeline_metric, some might be there as strings
    """
    for rows in self.dict_for_df.values():
      for i, value in enumerate(rows):
        # if we can cast one, we assume we can cast all
        # if not, we end up with a mixed list of e.g. strings and numbers
        rows[i] = convert_to_float_if_possible(value)

  def clean_cpu(self):
    """
    Sometimes we have negative CPU values, set them to 0
    """
    if METRIC_NAME_CPU not in self.dict_for_df:
      return

    cpu_list = self.dict_for_df[METRIC_NAME_CPU]
    for i, value in enumerate(cpu_list):
      # if negative, set to 0; in addition, divide by 100 since we are counting number of CPUs while psutil is doing in %
      cpu_list[i] = max(0, value) / 100

  def compute_time_delta(self):
    """
    Convert absolute time to delta
    """
    times = self.dict_for_df[METRIC_NAME_TIME]
    task_names = self.dict_for_df["name"]
    timeframes = self.dict_for_df["timeframe"]
    # need the start times for each single task
    start = {}
    for i, (value, task_name, timeframe) in enumerate(zip(times, task_names, timeframes)):
      timeframe = int(timeframe)
      # compute time delta wrt minimum
      if task_name not in start:
        start[task_name] = []
      if len(start[task_name]) <= timeframe:
        start[task_name].extend([None] * (timeframe - len(start[task_name]) + 1))
      if start[task_name][timeframe] is None:
        start[task_name][timeframe] = value
      times[i] = value - start[task_name][timeframe]

  def put_in_df(self):
    """
    Wrapper to put the dictionary into a dataframe
    """
    if not self.dict_for_df:
      return

    self.df = pd.DataFrame(self.dict_for_df)
    self.dict_for_df = None

  def extract_number_of_timeframes(self):
    """
    wrapper to extract the number of timeframes
    """
    self.number_of_timeframes = max(self.df["timeframe"].values)

  def add_iteration(self, iteration):
    """
    Add one iteration to the dictionary

    Everything on the fly
    and
    derive the timeframe and parent category as well
    """
    for key, value in iteration.items():
      if key == "name":
        try:
          name_split = value.split("_")
          tf_i = int(name_split[-1])
          # we only want to have the name without timeframe suffix
          value = "_".join(name_split[:-1])
        except ValueError:
          tf_i = 0

        self.dict_for_df["timeframe"].append(tf_i)

        cat = get_parent_category(value)
        self.dict_for_df["category"].append(cat)

      if key not in self.dict_for_df:
        # extend on-the-fly
        self.dict_for_df[key] = []
      # append
      self.dict_for_df[key].append(value)

  def extract_from_pipeline(self, pipeline_path):
    """
    read in a pipeline_metric file and put everything into a dataframe
    """
    if not exists(pipeline_path):
      print(f"ERROR: pipeline_metrics file not found at {pipeline_path}")
      return False

    self.name = basename(pipeline_path)

    with open(pipeline_path, "r") as f:
      for l in f:
        d = line_to_dict(l)
        if not d:
          continue

        if "iter" in d:
          # That is an iteration, add it to the dictionary
          self.add_iteration(d)
          continue
        if not self.meta:
          # at this point, the only other line in the pipeline_metric is the meta info, so when we end up here, we know that it is meta info
          self.meta = {}
          # remove time from the meta info, that is only interesting for iterations and would overwrite those values
          del d[METRIC_NAME_TIME]
          for key, value in d.items():
            self.meta[key] = convert_to_float_if_possible(value)

    if not self.check():
      return False

    self.add_meta()
    self.convert_columns_to_float_if_possible()
    self.clean_cpu()
    self.compute_time_delta()
    self.put_in_df()
    self.extract_number_of_timeframes()


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


def make_histo(x, y, xlabel, ylabel, ax=None, cmap=None, norm=True, title=None, sort=True, **kwargs):
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

  # sort the x-tick names according to increasing y-values
  if sort:
    y = y.copy()
    x = [i for _, i in sorted(zip(y, x))]
    y.sort()

  if norm:
    total = sum(y)
    if total > 0:
      y = [i / total for i in y]

  colors = None
  if cmap:
    # make colors for even clearer visualisation
    step = 1. / len(y)
    colors = [cmap(i * step) for i, _ in enumerate(y)]

  ax.bar(x, y, color=colors, **kwargs)
  ax.set_xticks(range(len(x)))
  ax.set_xticklabels(x)
  ax.tick_params("both", labelsize=30)
  ax.tick_params("x", rotation=90)
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
  figure, axes = plt.subplots(1, 2, figsize=(40, 20))

  if not len(x) or not len(y):
    print("No data for plotting...")
    return

  title = kwargs.pop("title", None)
  scale = kwargs.pop("scale", 1.)
  y = [i * scale for i in y]
  make_histo(x, y, xlabel, ylabel, axes[0], norm=False, **kwargs)
  make_pie(x, y, axes[1], **kwargs)
  if title:
    figure.suptitle(title, fontsize=60)
  save_figure(figure, path)


def resources_per_iteration(resources, fields, task_filter=None, per_what=None):
  """
  Extract given fields from pipeline based on potential regex filter
  """
  df = resources.df
  if task_filter:
    # filter on task names (can for instance also contain "|" for "or")
    df = df[df["name"].str.contains(task_filter)]

  iterations = df["iter"].unique()
  start = int(min(iterations))
  end = int(max(iterations))

  # each sub-list yields the corresponding resource value per iteration
  # iterations in pipeline_metric start at 1
  values = [[0] * (end - start + 1) for _ in fields]

  # make it definitely a list (e.g. in case it is a tuple)
  fields = list(fields)
  # columns to be selected
  columns = fields.copy()

  if per_what:
    what_values = df[per_what].dropna().unique()
    columns.append(per_what)
    values = {tn: deepcopy(values) for tn in what_values}

  for i in iterations:
    list_index = i - start
    df_skim = df.query(f"iter == {i}")[columns]
    if not len(df_skim):
      continue
    for j, field in enumerate(fields):
      if per_what:
        for _, row in df_skim.iterrows():
          per_what_value = row[per_what]
          if not per_what_value:
            continue
          values[per_what_value][j][int(list_index)] += row[field]
        continue
      values[j][int(list_index)] = sum(df_skim[field].values)

  return list(range(start, end + 1)), values


def plot_resource_history(json_pipelines, out_dir, filter=None, suffix=""):
  """
  Plotting resource history

  Provide min, max and average in addition,
  particularly useful when investigating changes of resources needed by workflow
  """
  suffix = f"_{suffix}" if suffix else ""

  # the metrics we want to extract
  metrics = (METRIC_NAME_PSS, METRIC_NAME_USS, METRIC_NAME_CPU)
  # corresponding y-axsi labels
  y_labels = ("PSS [MB]", "USS [MB]", "CPU efficiency [%]")
  figures = []
  axes = []
  for _ in metrics:
    # collecting the figures and axes to plot
    figure, ax = make_default_figure()
    figures.append(figure)
    axes.append(ax)

  # names for legends
  names = []

  # collect to plot them together in another overlay plot
  averages = [[] for _ in metrics]
  mins = [[] for _ in metrics]
  maxs = [[] for _ in metrics]

  # to have different styles for resources from different pipelines, for better visual presentation
  linestyles = ["solid", "dashed", "dashdot"]

  for jp_i, jp in enumerate(json_pipelines):

    name = jp.name
    n_cpu = jp.meta["cpu_limit"]
    iterations, iterations_y = resources_per_iteration(jp, metrics, filter)

    names.append(f"{jp_i}_{name}")

    ls = linestyles[jp_i%len(linestyles)]

    for index, it_y in enumerate(iterations_y):
      if index == 2:
        # for CPU efficiency we need to scale to CPU limit; multiply by 100 to get in %
        it_y = [it / n_cpu * 100 for it in it_y]

      average = np.mean(it_y)
      averages[index].append(average)
      mins[index].append(min(it_y))
      maxs[index].append(max(it_y))

      make_plot(iterations, it_y, "sampling iterations", y_labels[index], axes[index], label=f"{name} (Avg: {average:.2f})", ls=ls, linewidth=3)

  for fig, ax, me in zip(figures, axes, metrics):
    ax.legend(loc="best", fontsize=30)
    save_figure(fig, join(out_dir, f"{me}_vs_iterations{suffix}.png"))

  if len(json_pipelines) > 1:
    for av, mi, ma, y_label, me in zip(averages, mins, maxs, y_labels, metrics):
      # this overlays minima, maxima and averages
      figure, ax = make_default_figure()
      make_plot(names, av, "pipeline names", y_label, ax, label="average", ms=30, marker="o", lw=0)
      make_plot(names, mi, "pipeline names", y_label, ax, label="min", ms=30, marker="v", lw=0)
      make_plot(names, ma, "pipeline names", y_label, ax, label="max", ms=30, marker="P", lw=0)
      ax.tick_params("x", rotation=90)
      ax.legend(loc="best", fontsize=30)
      save_figure(figure, join(out_dir, f"{me}_min_max_average{suffix}.png"))


def plot_resource_history_stacked(res, out_dir, per_what):
  """
  Plotting resource history

  Provide min, max and average in addition,
  particularly useful when investigating changes of resources needed by workflow
  """

  # the metrics we want to extract
  metrics = (METRIC_NAME_PSS, METRIC_NAME_USS, METRIC_NAME_CPU)
  # corresponding y-axsi labels
  y_labels = ("PSS [MB]", "USS [MB]", "CPU efficiency [%]")
  figures = []
  axes = []
  for _ in metrics:
    # collecting the figures and axes to plot
    figure, ax = make_default_figure(figsize=(60, 20))
    figures.append(figure)
    axes.append(ax)

  n_cpu = res.meta["cpu_limit"]
  iterations, iterations_y = resources_per_iteration(res, metrics, per_what=per_what)

  # only print every modulo iteration on the x-axis
  modulo = 10**(max(0, len(str(len(iterations))) - 2))
  # for better visibility add hatches to bars
  hatches = ["/", "|", "-", "+", "*", "x"]

  def get_last_appearance(it_y):
    """
    convenience function to find last non-zero value and return index
    """
    for index, y in reversed(list(enumerate(it_y))):
      if y:
        return index
    return 0

  for metric_index, _ in enumerate(metrics):
     # checkpoints to be added
    last_appearance = [""] * len(iterations)
    # add current to stack
    bottom = [0] * len(iterations)
    per_what_values = list(iterations_y.keys())
    per_what_values.sort()
    for hatch_index, per_what_value, in enumerate(per_what_values):
      it_y = iterations_y[per_what_value][metric_index]
      if metric_index == 2:
        # for CPU efficiency we need to scale to CPU limit; multiply by 100 to get in %
        it_y = [it / n_cpu * 100 for it in it_y]
      # find out where it finished to attach to legend label
      last_appearance = iterations[get_last_appearance(it_y)]
      make_histo([i for i, _ in enumerate(it_y)], it_y, "sampling iterations", y_labels[metric_index], axes[metric_index], label=f"{per_what_value} (finished at {last_appearance})", bottom=bottom, sort=False, norm=False, hatch=hatches[hatch_index%len(hatches)])

      # stack on top
      bottom = [b + y for b, y in zip(bottom, it_y)]

    axes[metric_index].legend(bbox_to_anchor=(0., 1.02, 1., .102), loc='lower left', ncols=5, mode="expand", borderaxespad=0., fontsize=30, title=per_what, title_fontsize=40)
    axes[metric_index].set_xticklabels([it if not ((it - 1) % modulo) else None for it in iterations])
    figure.suptitle(y_labels[metric_index], fontsize=50)
    save_figure(figures[metric_index], join(out_dir, f"{metrics[metric_index]}_{per_what}_history_stacked.png"))


def get_resources_per_category(res):
  """
  Sum up the maximum resource needs of each task in their category
  """
  df = res.df[["name", "category", "timeframe"] + METRICS]
  # get the categories
  catgeories = [cat for cat in df["category"].unique() if cat is not None]
  resources_per_category = {metric: [0] * len(catgeories) for metric in METRICS}
  for i, cat in enumerate(catgeories):
    # skim down to category
    df_category = df.query(f"category == '{cat}'")
    task_names = df_category["name"].unique()
    for tn in task_names:
      # skim down to particular name and from this get the maximum
      df_name = df_category.query(f"name == '{tn}'")
      for key, current_res in resources_per_category.items():
        # extracted value is added to this category; for now, we statically extract the maximum
        current_res[i] += max(df_name[key].values)

  return catgeories, resources_per_category


def get_resources_per_task_within_category(res, category=None):
  """
  Select one category and get resources from in there
  """
  df = res.df
  if category:
    df = res.df.query(f"category == '{category}'")[["name"] + METRICS]
  task_names = df["name"].unique()
  resources_per_task = {metric: [0] * len(task_names) for metric in METRICS}
  for i, tn in enumerate(task_names):
    # skim down to particular name and from this get the maximum
    df_name = df.query(f"name == '{tn}'")
    for key, current_res in resources_per_task.items():
        # extracted value is added to this category
        current_res[i] = max(df_name[key].values)

  return task_names, resources_per_task


def extract_resources(pipelines):
    """
    Convenience wrapper for resource extraction
    """
    # Collect all metrics we got, here we want to have the median from all the iterations
    return [Resources(p) for p in pipelines]


def history(args):
  """
  Entrypoint for history

  Depending on a given feature (e.g. centre-of-mass energy or number of events), extract all different feature values
  and compare the resources.
  """
  """
  Create various plots for resource history as well as bar and pie charts for summary
  """
  resources = extract_resources(args.pipelines)

  out_dir = args.output
  if not exists(out_dir):
    makedirs(out_dir)

  # plot the history off all our resources
  plot_resource_history(resources, out_dir, args.filter_task, args.suffix)

  # a unified color map
  cmap = matplotlib.cm.get_cmap("coolwarm")

  for res in resources:
    name = res.name

    # save in sub-directory per analysed pipeline
    out_dir = join(args.output, f"{name}_dir")
    if not exists(out_dir):
      makedirs(out_dir)

    # make stacked bar charts over iterations
    # per task
    plot_resource_history_stacked(res, out_dir, per_what="name")
    # per timeframe
    plot_resource_history_stacked(res, out_dir, per_what="timeframe")
    # per category
    plot_resource_history_stacked(res, out_dir, per_what="category")

    # the following bar chart show the maximum resource needs for each task over all iterations

    # per category
    categories, resources_per_category = get_resources_per_category(res)
    plot_histo_and_pie(categories, resources_per_category[METRIC_NAME_TIME], "category", "$\sum_{i\in\{\mathrm{tasks}\}_\mathrm{category}} \mathrm{walltime}_i\,\,[s]$", join(out_dir, f"walltimes_categories.png"), cmap=cmap, title="TIME")
    plot_histo_and_pie(categories, resources_per_category[METRIC_NAME_CPU], "category", "$\sum_{i\in\{\mathrm{tasks}\}_\mathrm{category}} \#\mathrm{CPU}_i$", join(out_dir, f"cpu_categories.png"), cmap=cmap, title="CPU")
    plot_histo_and_pie(categories, resources_per_category[METRIC_NAME_USS], "category", "$\sum_{i\in\{\mathrm{tasks}\}_\mathrm{category}} \mathrm{USS}_i /\,\,[MB]$", join(out_dir, f"uss_categories.png"), cmap=cmap, title="USS")
    plot_histo_and_pie(categories, resources_per_category[METRIC_NAME_PSS], "category", "$\sum_{i\in\{\mathrm{tasks}\}_\mathrm{category}} \mathrm{PSS}_i\,\,[MB]$", join(out_dir, f"pss_categories.png"), cmap=cmap, title="PSS")

    # per single task
    task_names, resources_per_task = get_resources_per_task_within_category(res)
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_TIME], "task", "$\mathrm{walltime}\,\,[s]$", join(out_dir, f"walltimes_tasks.png"), cmap=cmap, title="TIME")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_CPU], "task", "$\#\mathrm{CPU}$", join(out_dir, f"cpu_tasks.png"), cmap=cmap, title="CPU")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_USS], "task", "$\mathrm{USS}\,\,[MB]$", join(out_dir, f"uss_tasks.png"), cmap=cmap, title="USS")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_PSS], "task", "$\mathrm{PSS}\,\,[MB]$", join(out_dir, f"pss_tasks.png"), cmap=cmap, title="PSS")

    # per task within digi category
    task_names, resources_per_task = get_resources_per_task_within_category(res, "digi")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_TIME], "task", "$\mathrm{walltime}\,\,[s]$", join(out_dir, f"walltimes_tasks_digi.png"), cmap=cmap, title="TIME (digi)")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_CPU], "task", "$\#\mathrm{CPU}$", join(out_dir, f"cpu_tasks_digi.png"), cmap=cmap, title="CPU (digi)")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_USS], "task", "$\mathrm{USS}\,\,[MB]$", join(out_dir, f"uss_tasks_digi.png"), cmap=cmap, title="USS (digi)")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_PSS], "task", "$\mathrm{PSS}\,\,[MB]$", join(out_dir, f"pss_tasks_digi.png"), cmap=cmap, title="PSS (digi)")

    # per task within reco category
    task_names, resources_per_task = get_resources_per_task_within_category(res, "reco")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_TIME], "task", "$\mathrm{walltime}\,\,[s]$", join(out_dir, f"walltimes_tasks_reco.png"), cmap=cmap, title="TIME (reco)")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_CPU], "task", "$\#\mathrm{CPU}$", join(out_dir, f"cpu_tasks_reco.png"), cmap=cmap, title="CPU (reco)")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_USS], "task", "$\mathrm{USS}\,\,[MB]$", join(out_dir, f"uss_tasks_reco.png"), cmap=cmap, title="USS (reco)")
    plot_histo_and_pie(task_names, resources_per_task[METRIC_NAME_PSS], "task", "$\mathrm{PSS}\,\,[MB]$", join(out_dir, f"pss_tasks_reco.png"), cmap=cmap, title="PSS (reco)")

  return 0


def compare(args):
  """
  Entrypoint for compare

  Depending on a given feature (e.g. centre-of-mass energy or number of events), extract all different feature values
  and compare the resources.
  """
  # add up all resources
  resources_single = extract_resources(args.pipelines)
  resources = resources_single[0]
  for m in resources_single[1:]:
    resources += m

  # from now on we work on the dataframe, skim it already to what we need
  df_full = resources.df[["name", "timeframe", "col", args.feature] + METRICS]

  def plot_resources_versus_tasks(df, metric, feature, y_label, save_path, title=None, add_to_legend=None, select=None):
    """
    Put resources versus tasks
    """
    if select:
      # filter on query if any
      df = df.query(select)

    # get the unique task names
    task_names = df["name"].unique()
    # get unique values for feature
    feature_values = [str(v) for v in df[feature].unique()]
    # collect values per task
    task_values = {v: [] for v in feature_values}

    fig, ax = plt.subplots(figsize=(40, 30))
    # loop through different markers
    markers = ["o", "v", "P"]

    for i, feat in enumerate(feature_values):
      for task in task_names:
        df_filt = df.query(f"{feature} == {feat} and name == \'{task}\'")
        if not len(df_filt):
          val_append = None
        else:
          # extract maximum
          val_append = max(df_filt[metric].values)
        task_values[feat].append(val_append)
      label = f"{feature}: {feat}"
      if add_to_legend:
        label = f"{label}, {add_to_legend}"
      ax.plot(task_names, task_values[feat], label=label, lw=0, ms=30, marker=markers[i%len(markers)])

    ax.set_xlabel("tasks", fontsize=40)
    ax.set_ylabel(y_label, fontsize=40)
    ax.legend(loc="best", fontsize=40)

    ax.tick_params(labelsize=40)
    ax.tick_params("x", rotation=90)
    if title:
      # add user title if given
      fig.suptitle(title, fontsize=60)
    # adjust, save and close
    save_figure(fig, save_path)

  if not exists(args.output):
    makedirs(args.output)
  plot_resources_versus_tasks(df_full, METRIC_NAME_CPU, args.feature, "# CPU", join(args.output, f"{args.feature}_cpu.png"), "system: pp", select="col == \'pp\'")
  plot_resources_versus_tasks(df_full, METRIC_NAME_USS, args.feature, "USS [GB]", join(args.output, f"{args.feature}_uss.png"), "system: pp", select="col == \'pp\'")
  plot_resources_versus_tasks(df_full, METRIC_NAME_PSS, args.feature, "PSS [GB]", join(args.output, f"{args.feature}_pss.png"), "system: pp", select="col == \'pp\'")
  plot_resources_versus_tasks(df_full, METRIC_NAME_TIME, args.feature, "time [s]", join(args.output, f"{args.feature}_time.png"), "system: pp", select="col == \'pp\'")


def influx(args):
  """
  Entrypoint for influx

  Make a text file that can be uploaded to InfluxDB
  """
  # collect the tags given by the user
  tags = {}
  if args.tags:
    pairs = args.tags.split(";")
    for p in pairs:
      key_val = p.split("=")
      if len(key_val) != 2:
        print(f"WARNING: Found invalid key-value pair {p}, skip")
        continue
      tags[key_val[0]] = key_val[1]

  # load the pipeline
  resources = Resources(args.pipeline)
  n_cpu = resources.meta["cpu_limit"]

  # add the number of timeframes to the tags
  tags["ntfs"] = resources.number_of_timeframes
  tags = ",".join([f"{k}={v}" for k, v in tags.items()])
  if tags:
    # put a leading comma
    tags = "," + tags

  # get the history for metrics of interest
  _, iterations_y = resources_per_iteration(resources, METRICS)

  categories, values = get_resources_per_category(resources)
  with open(args.output, "w") as f:
    for metric_id, metric_name in enumerate(METRICS):
      # this is the final table name for resources accumulated in categories
      tab_name = f"{args.table_base}_workflows_{metric_name}"
      # start assembling the string for the influx file to be uploaded
      db_string = f"{tab_name}{tags}"
      # accumulate the total resources for this metric
      total = 0
      # resource measurements go into the fields and are separated from the tags by a whitespace
      fields = []
      for cat, val in zip(categories, values[metric_name]):
        fields.append(f"{cat}={val}")
        total += val
      # join fields by comma...
      fields = ",".join(fields)
      # ...add to the string and write to file
      db_string += f" {fields},total={total}"
      f.write(f"{db_string}\n")

      if metric_name == METRIC_NAME_TIME:
        # don't do the following for time; makes no sense here to use min, max and average
        continue

      # table name for resources per CPU
      tab_name = f"{args.table_base}_workflows_{metric_name}_per_cpu"
      # normalise resources to number of CPU
      iterations = [it / n_cpu for it in iterations_y[metric_id]]
      # assemble string for influx and write to file
      db_string = f"{tab_name}{tags} minimum={min(iterations)},maximum={max(iterations)},average={sum(iterations) / len(iterations)}"
      f.write(f"{db_string}\n")

  return 0


def main():

  parser = argparse.ArgumentParser(description="Metrics evaluation of O2 simulation workflow")
  sub_parsers = parser.add_subparsers(dest="command")

  plot_parser = sub_parsers.add_parser("history", help="Plot (multiple) metrcis from extracted metrics JSON file(s)")
  plot_parser.set_defaults(func=history)
  plot_parser.add_argument("-p", "--pipelines", nargs="*", help="pipeline_metric files from o2_dpg_workflow_runner", required=True)
  plot_parser.add_argument("--output", help="output_directory", default="resource_history")
  plot_parser.add_argument("--filter-task", dest="filter_task", help="regex to filter only on certain task names in pipeline iterations")
  plot_parser.add_argument("--suffix", help="a suffix put at the end of the output file names")

  plot_comparison_parser = sub_parsers.add_parser("compare", help="Compare resources from pipeline_metric file")
  plot_comparison_parser.set_defaults(func=compare)
  plot_comparison_parser.add_argument("-p", "--pipelines", nargs="*", help="pipeline_metric files from o2_dpg_workflow_runner", required=True)
  plot_comparison_parser.add_argument("--output", help="output_directory", default="resource_comparison")
  plot_comparison_parser.add_argument("--names", nargs="*", help="assign one custom name per pipeline")
  plot_comparison_parser.add_argument("--feature", help="feature to be investigated", required=True, choices=FEATURES)

  influx_parser = sub_parsers.add_parser("influx", help="Derive a format which can be sent to InfluxDB")
  influx_parser.set_defaults(func=influx)
  influx_parser.add_argument("-p", "--pipeline", help="exactly one pipeline_metric file from o2_dpg_workflow_runner to prepare for InfluxDB", required=True)
  influx_parser.add_argument("--table-base", dest="table_base", help="base name of InfluxDB table name", default="O2DPG_MC")
  influx_parser.add_argument("--output", "-o", help="output file name", default="metrics_influxDB.dat")
  influx_parser.add_argument("--tags", help="key-value pairs, seperated by \";\", for example: alidist=1234567;o2=7654321;tag=someTag")

  args = parser.parse_args()
  return args.func(args)

if __name__ == "__main__":
  sys.exit(main())
