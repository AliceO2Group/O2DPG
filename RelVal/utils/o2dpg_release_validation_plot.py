#!/usr/bin/env python3
#
# Definition common functionality

import sys
from os.path import join
from os import environ
import importlib.util
from itertools import product
import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import seaborn


O2DPG_ROOT = environ.get("O2DPG_ROOT")
spec = importlib.util.spec_from_file_location("o2dpg_release_validation_utils", join(O2DPG_ROOT, "RelVal", "utils", '.', 'o2dpg_release_validation_utils.py'))
o2dpg_release_validation_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o2dpg_release_validation_utils)
sys.modules["o2dpg_release_validation_utils"] = o2dpg_release_validation_utils
from o2dpg_release_validation_utils import count_interpretations

spec = importlib.util.spec_from_file_location("o2dpg_release_validation_plot_root", join(O2DPG_ROOT, "RelVal", "utils", '.', 'o2dpg_release_validation_plot_root.py'))
o2dpg_release_validation_plot_root = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o2dpg_release_validation_plot_root)
sys.modules["o2dpg_release_validation_plot_root"] = o2dpg_release_validation_plot_root
from o2dpg_release_validation_plot_root import plot_overlays_root, plot_overlays_root_no_rel_val

def plot_pie_charts(rel_val, interpretations, interpretation_colors, out_dir, title="", get_figure=False):

    print("==> Plot pie charts <==")
    for metric_name, test_name in product(rel_val.known_metrics, rel_val.known_test_names):
        figure, ax = plt.subplots(figsize=(20, 20))
        colors = []
        counts = []
        labels = []
        object_names, results = rel_val.get_result_per_metric_and_test(metric_name, test_name)

        if not len(object_names):
            continue

        for interpretation in interpretations:
            n_objects = len(object_names[count_interpretations(results, interpretation)])
            if not n_objects:
                continue
            counts.append(n_objects)
            colors.append(interpretation_colors[interpretation])
            labels.append(interpretation)

        ax.pie(counts, explode=[0.05 for _ in counts], labels=labels, autopct="%1.1f%%", startangle=90, textprops={"fontsize": 30}, colors=colors)
        ax.axis("equal")
        ax.axis("equal")

        figure.suptitle(f"{title} (metric: {metric_name}, test: {test_name})", fontsize=40)
        save_path = join(out_dir, f"pie_chart_{metric_name}_{test_name}.png")
        figure.savefig(save_path)
        if get_figure:
            return figure
        plt.close(figure)


def plot_summary_grid(rel_val, interpretations, interpretation_colors, output_dir, get_figure=False):

    print("==> Plot summary grid <==")

    interpretation_name_to_number = {v: i for i, v in enumerate(interpretations)}

    colors = [None] * len(interpretation_name_to_number)
    for name, color in interpretation_colors.items():
        colors[interpretation_name_to_number[name]] = color
    cmap = LinearSegmentedColormap.from_list("Custom", colors, len(colors))
    figures = []

    for nt in range(rel_val.number_of_tests):
        metric_names, object_names, results_matrix = rel_val.get_result_matrix_objects_metrics(nt)
        arr = np.full(results_matrix.shape, 0, dtype=int)
        arr_annot = np.full(results_matrix.shape, "", dtype=object)
        it = np.nditer(results_matrix, flags=['multi_index', "refs_ok"])
        for _ in it:
            result = results_matrix[it.multi_index]
            arr[it.multi_index] = interpretation_name_to_number[result.interpretation]
            if result.value is not None:
                annot = f"{result.value:.3f} (mean: {result.mean:.3f})"
                if result.n_sigmas is not None:
                    annot += f" (n_sigma: {result.n_sigmas:.3f})"
            else:
                annot = result.non_comparable_note

            arr_annot[it.multi_index] = annot

        figure, ax = plt.subplots(figsize=(20, 20))
        seaborn.heatmap(arr, ax=ax, cmap=cmap, vmin=-0.5, vmax=len(interpretations) - 0.5, yticklabels=object_names, xticklabels=metric_names, linewidths=0.5, annot=arr_annot, fmt="")
        cbar = ax.collections[0].colorbar
        cbar.set_ticks(range(len(colors)))
        cbar.set_ticklabels(interpretations)
        ax.set_title("Test summary [value (mean), (n_sigmas)]", fontsize=30)
        figure.tight_layout()

        if get_figure:
            figures.append(figure)
            continue

        output_path = join(output_dir, f"summary_{rel_val.get_test_name(nt)}.png")
        figure.savefig(output_path)
        plt.close(figure)

    if get_figure:
        return figures


def plot_compare_summaries(rel_vals, out_dir, *, labels=None, get_figure=False):
    """
    if labels is given, it needs to have the same length as summaries
    """

    print("==> Plot metric values <==")

    figures = []

    if not labels:
        labels = [f"summary_{i}" for i, _ in enumerate(rel_vals)]

    test_names = list(rel_vals[0].known_test_names)
    metric_names = list(rel_vals[0].known_metrics)
    for rel_val in rel_vals[1:]:
        test_names = list(set(test_names + list(rel_val.known_test_names)))
        metric_names = list(set(metric_names + list(rel_val.known_metrics)))

    for metric_name, test_name in product(metric_names, test_names):
        figure, ax = plt.subplots(figsize=(20, 20))
        plot_this = False
        for rel_val, label in zip(rel_vals, labels):
            object_names, results = rel_val.get_result_per_metric_and_test(metric_name, test_name)
            values = [result.value for result in results]
            means = [result.mean for result in results]
            if not values:
                continue
            plot_this = True
            ax.plot(object_names, values, label=f"values_{label}")
            ax.plot(object_names, means, label=f"test_means_{label}")
        if not plot_this:
            continue
        ax.legend(loc="best", fontsize=20)
        ax.tick_params("both", labelsize=20)
        ax.tick_params("x", rotation=90)

        figure.tight_layout()
        figure.savefig(join(out_dir, f"values_thresholds_{metric_name}_{test_name}.png"))
        if get_figure:
            figures.append(figure)
            continue
        plt.close(figure)
    if get_figure:
        return figures


def plot_overlays(rel_val, file_config_map1, file_config_map2, out_dir, plot_regex=None):
    print("==> Plot overlays <==")
    plot_overlays_root(rel_val, file_config_map1, file_config_map2, out_dir, plot_regex)


def plot_overlays_no_rel_val(file_configs, out_dir):
    print("==> Plot overlays <==")
    plot_overlays_root_no_rel_val(file_configs, out_dir)
