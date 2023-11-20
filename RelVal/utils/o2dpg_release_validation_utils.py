#!/usr/bin/env python3
#
# Definition of common functionality

import re
from os.path import join, exists, isdir
from itertools import product
from subprocess import Popen, PIPE, STDOUT
from shlex import split
import json
import numpy as np


def remove_outliers(data, m=6.):
    """
    Helper to remove outliers from a list of floats
    """
    if not data:
        return None, None
    data = np.array(data)
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d / (mdev if mdev else 1.)
    print(s)
    return data[s < m], data[s >= m]


def default_evaluation(limits):
    """
    Return a lambda f(value) -> bool

    Indicates pass/fail (True/False) for a given value
    """
    if limits[0] is None and limits[1] is None:
        return lambda x: None
    if limits[0] is not None and limits[1] is None:
        return lambda x: x > limits[0]
    if limits[0] is None and limits[1] is not None:
        return lambda x: x < limits[1]
    return lambda x: limits[0] < x < limits[1]


def compute_limits(mean, std):
    """
    Compute numerical limits for a given mean and std
    """
    if mean is None or std is None:
        return (None, None)
    low, high = (std[0], std[1])
    if low is not None and high is None:
        return ((mean - low), None)
    if low is None and high is not None:
        return (None, (mean + high))
    return ((mean - low), (mean + high))


class Result:
    """
    Holds some result values after testing a metric value against corresponding limits

    This is the smallest granularity that we will have in the end
    """
    FLAG_UNKNOWN = 0
    FLAG_PASSED = 1
    FLAG_FAILED = 2

    def __init__(self, name=None, value=None, result_flag=FLAG_UNKNOWN, n_sigmas=None, mean=None, interpretation=None, non_comparable_note=None, in_dict=None):
        self.name = name
        self.value = value
        self.result_flag = result_flag
        self.n_sigmas = n_sigmas
        self.mean = mean
        self.interpretation = interpretation
        self.non_comparable_note = non_comparable_note
        if in_dict is not None:
            self.from_dict(in_dict)

    def as_dict(self):
        return {"result_name": self.name,
                "value": self.value,
                "result_flag": self.result_flag,
                "n_sigmas": self.n_sigmas,
                "mean": self.mean,
                "interpretation": self.interpretation,
                "non_comparable_note": self.non_comparable_note}

    def from_dict(self, in_dict):
        self.name = in_dict["result_name"]
        self.value = in_dict["value"]
        self.result_flag = in_dict["result_flag"]
        self.n_sigmas = in_dict["n_sigmas"]
        self.mean = in_dict["mean"]
        self.interpretation = in_dict["interpretation"]
        self.non_comparable_note = in_dict["non_comparable_note"]


class Metric:
    def __init__(self, object_name=None, name=None, value=None, proposed_threshold=None, comparable=None, lower_is_better=None, non_comparable_note=None, in_dict=None):
        self.object_name = object_name
        self.name = name
        self.value = value
        self.comparable = comparable
        self.proposed_threshold = proposed_threshold
        self.lower_is_better = lower_is_better
        self.non_comparable_note = non_comparable_note
        if in_dict is not None:
            self.from_dict(in_dict)

    def as_dict(self):
        return {"object_name": self.object_name,
                "metric_name": self.name,
                "value": self.value,
                "comparable": self.comparable,
                "proposed_threshold": self.proposed_threshold,
                "lower_is_better": self.lower_is_better,
                "non_comparable_note": self.non_comparable_note}

    def from_dict(self, in_dict):
        self.object_name = in_dict["object_name"]
        self.name = in_dict["metric_name"]
        self.value = in_dict["value"]
        self.comparable = in_dict["comparable"]
        self.proposed_threshold = in_dict["proposed_threshold"]
        self.lower_is_better = in_dict["lower_is_better"]
        self.non_comparable_note = in_dict["non_comparable_note"]


class TestLimits:
    """
    Combines functionality to hold limits, test against values and constructing Result objects
    """
    def __init__(self, name, mean=None, std=None, test_function=default_evaluation):
        self.name = name
        self.mean = mean
        self.std = std
        self.limits = compute_limits(mean, std)
        self.test_function = test_function(self.limits)

    def set_test_function(self, test_function):
        """
        Set a test function that, based on limits,
        returns a lambda function to evaluate pass/fail for a given value
        """
        self.test_function = test_function(self.limits)

    def test(self, metric):
        """
        Evaluate a value and return Result object
        """
        value = metric.value

        if value is None:
            return Result(self.name, non_comparable_note=metric.non_comparable_note)
        if not self.test_function or self.mean is None:
            return Result(self.name, value, non_comparable_note=metric.non_comparable_note)
        n_sigmas = self.std[int(value > self.mean)]
        if n_sigmas == 0:
            n_sigmas = None
        elif n_sigmas is not None:
            n_sigmas = abs(self.mean - value) / n_sigmas if n_sigmas != 0 else 0

        # NOTE Here we want the test_function to directly return the test flag
        test_flag = self.test_function(value)
        if test_flag:
            test_flag = Result.FLAG_PASSED
        elif test_flag is None:
            test_flag = Result.FLAG_UNKNOWN
        else:
            test_flag = Result.FLAG_FAILED
        return Result(self.name, value, test_flag, n_sigmas, self.mean, non_comparable_note=metric.non_comparable_note)


class Evaluator:

    def __init__(self):
        self.object_names = []
        self.metric_names = []
        self.test_names = []
        self.tests = []
        self.mask_any = None

    def add_limits(self, object_name, metric_name, test_limits):
        self.object_names.append(object_name)
        self.metric_names.append(metric_name)
        self.test_names.append(test_limits.name)
        self.tests.append(test_limits)

    def initialise(self):
        self.object_names = np.array(self.object_names, dtype=str)
        self.metric_names = np.array(self.metric_names, dtype=str)
        self.test_names = np.array(self.test_names, dtype=str)
        self.tests = np.array(self.tests, dtype=TestLimits)

        # fill up tests
        # The following guarantees that we have all metrics and all tests for the object names
        # NOTE Probably there is a more elegant way?!
        test_names_known = np.unique(self.test_names)
        metric_names_known = np.unique(self.metric_names)
        object_names_known = np.unique(self.object_names)

        object_names_to_add = []
        metric_names_to_add = []
        test_names_to_add = []

        for object_name, metric_name in product(object_names_known, metric_names_known):
            mask = (self.object_names == object_name) & (self.metric_names == metric_name)
            if not np.any(mask):
                object_names_to_add.extend([object_name] * len(test_names_known))
                metric_names_to_add.extend([metric_name] * len(test_names_known))
                test_names_to_add.extend(test_names_known)
                continue
            present_test_names = self.test_names[mask]
            test_names_not_present = test_names_known[~np.isin(present_test_names, test_names_known)]
            test_names_to_add.extend(test_names_not_present)
            metric_names_to_add.extend([metric_name] * len(test_names_not_present))
            object_names_to_add.extend([object_name] * len(test_names_not_present))

        self.object_names = np.array(np.append(self.object_names, object_names_to_add))
        self.metric_names = np.array(np.append(self.metric_names, metric_names_to_add))
        self.test_names = np.array(np.append(self.test_names, test_names_to_add))
        self.tests = np.array(np.append(self.tests, [TestLimits(tnta) for tnta in test_names_to_add]))

        self.mask_any = np.full(self.test_names.shape, True)

    def test(self, metrics):
        """
        We expect all arguments to have the same length
        They must not be None
        """

        # get all tests registered for the given arguments
        results = []
        return_metrics_idx = []

        # probably there is a better way
        for idx, metric in enumerate(metrics):
            mask = (self.object_names == metric.object_name) & (self.metric_names == metric.name)
            if not np.any(mask):
                continue
            for t in self.tests[mask]:
                return_metrics_idx.append(idx)
                results.append(t.test(metric))

        return np.array(return_metrics_idx, dtype=int), np.array(results, dtype=Result)


class RelVal:

    KEY_OBJECTS = "objects"
    KEY_OBJECT_NAME = "object_name"
    KEY_ANNOTATIONS = "annotations"

    def __init__(self):
        # metric names that should be considered (if empty, all)
        self.include_metrics = []
        self.exclude_metrics = []
        # lists of regex to include/exclude objects by name
        self.include_patterns = None
        self.exclude_patterns = None

        # collecting everything we have; all of the following will have the same length in the end
        self.object_names = None
        self.metric_names = None
        # metric objects
        self.metrics = None

        # object and metric names known to this RelVal
        self.known_objects = None
        self.known_metrics = None

        # collecting all results; all of the following will have the same length in the end
        self.results = None
        # indices to refer to self.object_names, self.metric_names and self.metrics
        self.results_to_metrics_idx = None
        self.known_test_names = None

        # to store some annotations
        self.annotations = None

    def enable_metrics(self, metrics):
        if not metrics:
            return
        for metric in metrics:
            if metric in self.include_metrics:
                continue
            self.include_metrics.append(metric)

    def disable_metrics(self, metrics):
        if not metrics:
            return
        for metric in metrics:
            if metric in self.exclude_metrics:
                continue
            self.exclude_metrics.append(metric)

    def consider_metric(self, metric_name):
        """
        whether or not a certain metric should be taken into account
        """
        if self.exclude_metrics and metric_name in self.exclude_metrics:
            return False
        if not self.include_metrics or metric_name in self.include_metrics:
            return True
        return False

    def set_object_name_patterns(self, include_patterns, exclude_patterns):
        """
        Load include patterns to be used for regex comparison
        """
        def load_this_patterns(patterns):
            if not patterns or not patterns[0].startswith("@"):
                return patterns
            with open(patterns[0][1:], "r") as f:
                return f.read().splitlines()

        self.include_patterns = load_this_patterns(include_patterns)
        self.exclude_patterns = load_this_patterns(exclude_patterns)

    def consider_object(self, object_name):
        """
        check a name against a list of regex to decide whether or not it should be included
        """
        if not self.include_patterns and not self.exclude_patterns:
            return True

        if self.include_patterns:
            for ip in self.include_patterns:
                if re.search(ip, object_name):
                    return True
            return False

        # we can only reach this point if there are no include_patterns
        # that, in turn, means that there are exclude_patterns, cause otherwise
        # we would have returned in the very beginning
        for ip in self.exclude_patterns:
            if re.search(ip, object_name):
                return False
        return True

    @staticmethod
    def read(path_or_dict):
        """
        convenience wrapper to read metrics/results from JSON or a dictionary
        """
        if isinstance(path_or_dict, dict):
            return path_or_dict
        with open(path_or_dict, "r") as f:
            return json.load(f)

    def add_metric(self, metric):
        """
        Add a metric
        """
        object_name = metric.object_name
        if not self.consider_object(object_name) or not self.consider_metric(metric.name):
            return False
        self.object_names.append(object_name)
        self.metric_names.append(metric.name)
        self.metrics.append(metric)
        return True

    def add_result(self, metric_idx, result):
        metric = self.metrics[metric_idx]
        object_name = metric.object_name
        if not self.consider_object(object_name) or not self.consider_metric(metric.name):
            return
        self.results_to_metrics_idx.append(metric_idx)
        self.results.append(result)

    def load(self, summaries_to_test):

        self.annotations = []
        self.object_names = []
        self.metric_names = []
        self.metrics = []
        self.results_to_metrics_idx = []
        self.results = []

        for summary_to_test in summaries_to_test:
            summary_to_test = self.read(summary_to_test)
            if annotations := summary_to_test.get(RelVal.KEY_ANNOTATIONS, None):
                self.annotations.append(annotations)
            for line in summary_to_test[RelVal.KEY_OBJECTS]:
                metric = Metric(in_dict=line)
                if not self.add_metric(metric):
                    continue

                if "result_name" in line:
                    # NOTE We could think about not duplicating metrics.
                    #      Because there is the same metric for each of the corresponding test results
                    self.add_result(len(self.metrics) - 1, Result(in_dict=line))

        self.known_objects = np.unique(self.object_names)
        self.known_metrics = np.unique(self.metric_names)

        self.object_names = np.array(self.object_names, dtype=str)
        self.metric_names = np.array(self.metric_names, dtype=str)
        self.metrics = np.array(self.metrics, dtype=Metric)
        self.any_mask = np.full(self.object_names.shape, True)

        # at this point results are still a list
        self.results_to_metrics_idx = np.array(self.results_to_metrics_idx, dtype=int) if self.results else None
        self.test_names_results = np.array([r.name for r in self.results]) if self.results else None
        self.known_test_names = np.unique(self.test_names_results) if self.results else None
        self.result_filter_mask = np.full(self.known_test_names.shape, True)  if self.results else None
        self.results = np.array(self.results, dtype=Result) if self.results else None

    def get_metrics(self, object_name=None, metric_name=None):
        """
        extract all metrics matching a given object_name or metric_name

        Args:
            object_name: str or None
                the object name to look for; if None, any object_name is taken into account
            metric_name: str or None
                the metric name to look for; if None, any metric_name is taken into account

        NOTE that at the moment, metrics can only be searched by a single string of object or metric name.
             It is not possible to match multiple for now...
        """
        mask = self.any_mask if object_name is None else np.isin(self.object_names, object_name)
        mask = mask & (self.any_mask if metric_name is None else np.isin(self.metric_names, metric_name))
        return self.object_names[mask], self.metric_names[mask], self.metrics[mask]

    def apply(self, evaluator):
        """
        Apply loaded tests
        """
        # Now, we need to remove the duplicates in object_names and metric_names as well as remove the corresponding duplicates of metrics
        if self.results is not None:
            object_metric_names = np.vstack((self.object_names, self.metric_names)).T
            _, idx = np.unique(object_metric_names, return_index=True, axis=0)
            self.metrics = self.metrics[idx]
            self.object_names = self.object_names[idx]
            self.metric_names = self.metric_names[idx]
            self.any_mask = np.full(self.object_names.shape, True)

        self.results_to_metrics_idx, self.results = evaluator.test(self.metrics)
        self.test_names_results = np.array([r.name for r in self.results])
        self.known_test_names = np.unique(self.test_names_results)
        self.result_filter_mask = np.full(self.known_test_names.shape, True)

    def interpret(self, interpret_func):
        for metric_idx, result in zip(self.results_to_metrics_idx, self.results):
            interpret_func(result, self.metrics[metric_idx])

    def filter_results(self, filter_func):
        if self.results is None:
            return
        self.result_filter_mask = [filter_func(result) for result in self.results]

    def query_results(self, query_func=None):
        mask = np.array([query_func is None or query_func(result) for result in enumerate(self.results)])
        mask = mask & self.result_filter_mask
        idx = self.results_to_metrics_idx[mask]
        return np.take(self.object_names, idx), np.take(self.metric_names, idx), self.test_names_results[idx], self.results[idx]

    @property
    def number_of_tests(self):
        return len(self.known_test_names) if self.results is not None else 0

    @property
    def number_of_metrics(self):
        return len(self.known_metrics)

    @property
    def number_of_objects(self):
        return len(self.known_objects)

    def get_test_name(self, idx):
        return self.known_test_names[idx]

    def get_metric_name(self, idx):
        return self.known_metrics[idx]

    def get_result_per_metric_and_test(self, metric_index_or_name=None, test_index_or_name=None):
        test_name = test_index_or_name if (isinstance(test_index_or_name, str) or test_index_or_name is None) else self.known_test_names[test_index_or_name]
        metric_name = metric_index_or_name if (isinstance(metric_index_or_name, str) or metric_index_or_name is None) else self.known_metrics[metric_index_or_name]
        metric_idx = np.argwhere(self.metric_names == metric_name) if metric_name is not None else self.results_to_metrics_idx
        mask = np.isin(self.results_to_metrics_idx, metric_idx) & self.result_filter_mask
        if test_name is not None:
            mask = mask & (self.test_names_results == test_name)
        return np.take(self.object_names, self.results_to_metrics_idx[mask]), self.results[mask]

    def get_result_matrix_objects_metrics(self, test_index):
        mask = self.test_names_results == (self.known_test_names[test_index])
        idx = self.results_to_metrics_idx[mask]
        results = self.results[mask]
        object_names = np.take(self.object_names, idx)
        metric_names = np.take(self.metric_names, idx)

        idx = np.lexsort((metric_names, object_names))

        object_names = np.sort(np.unique(object_names))
        metric_names = np.sort(np.unique(metric_names))

        return metric_names, object_names, np.reshape(results[idx], (len(object_names), len(metric_names)))

    def yield_metrics_results_per_object(self):
        results = None
        if self.results is not None:
            mask = self.result_filter_mask
            idx = self.results_to_metrics_idx[mask]
            object_names = np.take(self.object_names, idx)
            metrics = np.take(self.metrics, idx)
            results = self.results[mask]
        else:
            object_names = self.object_names
            metrics = self.metrics

        for object_name in np.unique(object_names):
            mask = object_names == object_name
            yield_metrics = metrics[mask]
            yield_results = results[mask] if results is not None else np.array([None] * len(yield_metrics))
            yield object_name, yield_metrics, yield_results

    def write(self, filepath, annotations=None):

        all_objects = []

        # TODO return one flat dictionary not a nested one
        def make_dict_include_results(object_name, metric, result):
            return {RelVal.KEY_OBJECT_NAME: object_name} | metric.as_dict() | result.as_dict()

        def make_dict_exclude_results(object_name, metric, *args):
            return {RelVal.KEY_OBJECT_NAME: object_name} | metric.as_dict()

        if self.results is None:
            object_names = self.object_names
            metrics = self.metrics
            results = np.empty(metric.shape, dtype=bool)
            make_dict = make_dict_exclude_results
        else:
            object_names = np.take(self.object_names, self.results_to_metrics_idx)
            metrics = np.take(self.metrics, self.results_to_metrics_idx)
            results = self.results
            make_dict = make_dict_include_results

        for object_name, metric, result in zip(object_names, metrics, results):
            all_objects.append(make_dict(object_name, metric, result))

        final_dict = {RelVal.KEY_OBJECTS: all_objects,
                      RelVal.KEY_ANNOTATIONS: annotations}

        with open(filepath, "w") as f:
            json.dump(final_dict, f, indent=2)


def get_summaries_or_from_file(in_objects):

    if len(in_objects) == 1 and in_objects[0].startswith("@"):
        with open(in_objects[0][1:], "r") as f:
            return f.read().splitlines()
    return in_objects


def initialise_thresholds(evaluator, rel_val, rel_val_thresholds, thresholds_default, thresholds_margin, thresholds_combine="mean"):

    # The default thresholds will be derived and set for all the objects and metrics that we find in the RelVal to test
    _, _, metrics = rel_val.get_metrics()
    for metric in metrics:
        proposed_threshold = thresholds_default.get(metric.name, metric.proposed_threshold) if thresholds_default else metric.proposed_threshold
        std = (None, 0) if metric.lower_is_better else (0, None)
        evaluator.add_limits(metric.object_name, metric.name, TestLimits("threshold_default", proposed_threshold, std))

    if not rel_val_thresholds:
        # no need to go further if no user-specific thresholds are given
        return

    for object_name in rel_val_thresholds.known_objects:
        for metric_name in rel_val_thresholds.known_metrics:
            _, _, metrics = rel_val_thresholds.get_metrics((object_name,), (metric_name,))
            if not np.any(metrics):
                continue

            values = [m.value for m in metrics if m.comparable]

            lower_is_better = metrics[0].lower_is_better
            factor = 1 if lower_is_better else -1

            if not values:
                continue
            if thresholds_combine == "mean":
                mean_central = np.mean(values)
            else:
                mean_central = factor * max([factor * v for v in values])

            if factor > 0:
                low = None
                up = (1 + thresholds_margin[metric_name]) * mean_central
            else:
                up = None
                low = (1 - thresholds_margin) * mean_central
            evaluator.add_limits(object_name, metric_name, TestLimits("threshold_user", mean_central, (low, up)))


def initialise_regions(evaluator, regions):
    rel_val_regions = RelVal()
    rel_val_regions.load(regions)
    for object_name in rel_val_regions.known_objects:
        for metric_name in rel_val_regions.known_metrics:
            _, _, metrics = rel_val_regions.get_metrics((object_name,), (metric_name,))
            values = [m.value for m in metrics if m.comparable]
            proposed_threshold = metrics[0].proposed_threshold
            lower_is_better = metrics[0].lower_is_better
            values_central = []
            values_outlier = []
            for v in values:
                diff = v - proposed_threshold
                if (diff < 0 and lower_is_better) or (diff > 0 and not lower_is_better):
                    # if the value is below and lower is better (or the other way round), then accept it
                    values_central.append(v)
                    continue
                if diff != 0:
                    diff = abs(proposed_threshold / diff)
                    if diff < 0.1:
                        # this means we accept up to an order of magnitude
                        values_outlier.append(v)
                        continue
                values_central.append(v)

            mean_central = np.mean(values_central)
            std_central = np.std(values_central)
            if np.any(values_outlier):
                mean_outlier = np.mean(values_outlier)
                std_outlier = np.std(values_outlier)
            else:
                mean_outlier = None
                std_outlier = None
            evaluator.add_limits(object_name, metric_name, TestLimits("regions_tight", mean_central, (std_central, std_central)))
            evaluator.add_limits(object_name, metric_name, TestLimits("regions_loose", mean_outlier, (std_outlier, std_outlier)))


def run_macro(cmd, log_file, cwd=None):
    p = Popen(split(cmd), cwd=cwd, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
    log_file = open(log_file, 'a')
    for line in p.stdout:
        log_file.write(line)
    p.wait()
    log_file.close()
    return p.returncode


def count_interpretations(results, interpretation):
    """
    return indices where results have a certain interpretation
    """
    return np.array([result.interpretation == interpretation for result in results], dtype=bool)


def print_summary(rel_val, interpretations, long=False):
    """
    Check if any 2 histograms have a given severity level after RelVal
    """
    print("\n##### RELVAL SUMMARY #####\n")
    for metric_name in rel_val.known_metrics:
        for test_name in rel_val.known_test_names:
            object_names, results = rel_val.get_result_per_metric_and_test(metric_name, test_name)
            print(f"METRIC: {metric_name}, TEST: {test_name}")
            for interpretation in interpretations:
                object_names_interpretation = object_names[count_interpretations(results, interpretation)]
                percent = len(object_names_interpretation) / rel_val.number_of_objects
                print(f"  {interpretation}: {len(object_names_interpretation)} ({percent * 100:.2f}%)")
                if long:
                    for object_name in object_names_interpretation:
                        print(f"    {object_name}")

    print("\n##########################\n")


def get_summary_path(path):
    if isdir(path):
        path = join(path, "Summary.json")
    if exists(path):
        return path
    print(f"ERROR: Cannot neither find {path}.")
    return None
