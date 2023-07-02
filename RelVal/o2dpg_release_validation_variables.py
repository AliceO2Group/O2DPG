#!/usr/bin/env python3
#
# Definition of common variables

REL_VAL_SEVERITIES = ["GOOD", "WARNING", "NONCRIT_NC", "CRIT_NC", "BAD"]
REL_VAL_SEVERITIES_USE_SUMMARY = [True, False, False, True, True]
REL_VAL_SEVERITY_MAP = {v: i for i, v in enumerate(REL_VAL_SEVERITIES)}
REL_VAL_SEVERITY_COLOR_MAP = {"GOOD": "green", "WARNING": "orange", "NONCRIT_NC": "cornflowerblue", "CRIT_NC": "navy", "BAD": "red"}
REL_VAL_TEST_NAMES = ["chi2", "kolmogorov", "num_entries"]
REL_VAL_TEST_NAMES_MAP = {v: i for i, v in enumerate(REL_VAL_TEST_NAMES)}
REL_VAL_TEST_CRITICAL = [True, True, False]
REL_VAL_TEST_DEFAULT_THRESHOLDS = [1.5, 0.5, 0.01]
REL_VAL_TEST_UPPER_LOWER_THRESHOLD = [1, -1, 1]
REL_VAL_TEST_SUMMARY_NAME = "summary"
REL_VAL_TEST_NAMES_SUMMARY = REL_VAL_TEST_NAMES + [REL_VAL_TEST_SUMMARY_NAME]
REL_VAL_TEST_NAMES_MAP_SUMMARY = {v: i for i, v in enumerate(REL_VAL_TEST_NAMES_SUMMARY)}
