#!/usr/bin/env python3
"""Offline tests for the strace analyser."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

from filegraph_test_support import FILEGRAPH_DIR  # noqa: F401

import analyse_FileIO_strace as A  # noqa: E402

ALL = [re.compile(r".*")]

# What `strace -f -qq -y -e status=successful` really writes. The last two
# lines of the open block are a call split around another process's entry.
TRACE = '''\
101 openat(AT_FDCWD</w/tf1>, "sgn.dat", O_WRONLY|O_CREAT|O_TRUNC, 0666) = 3</w/tf1/sgn.dat>
101 openat(AT_FDCWD</w/tf1>, "../bkg.dat", O_RDONLY) = 4</w/bkg.dat>
102 openat(AT_FDCWD</w/tf1>, "kine.dat", O_RDONLY|O_CLOEXEC) = 3</w/tf1/kine.dat>
102 openat(AT_FDCWD</w/tf1>, "/usr/lib/libc.so.6", O_RDONLY|O_CLOEXEC) = 3</usr/lib/libc.so.6>
102 openat(AT_FDCWD</w/tf1>, ".", O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_DIRECTORY) = 8</w/tf1>
101 openat(AT_FDCWD</w/tf1>, "reco.dat", O_WRONLY|O_CREAT|O_APPEND <unfinished ...>
102 openat(AT_FDCWD</w/tf1>, "digi.dat", O_RDONLY) = 5</w/tf1/digi.dat>
101 <... openat resumed>, 0666)          = 6</w/tf1/reco.dat>
101 renameat2(AT_FDCWD, "tmp.dat", AT_FDCWD, "final.dat", 0) = 0
'''


class TestParseTrace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "trace_0_reco_1.log")
            with open(p, "w") as f:
                f.write(TRACE)
            cls.seen, cls.calls = A.parse_trace(p)

    def test_resolved_path_wins_over_the_argument(self):
        # the argument said '../bkg.dat'; -y resolved it
        self.assertIn(("/w/bkg.dat", "read"), self.seen)

    def test_write_flags_classify_as_write(self):
        self.assertIn(("/w/tf1/sgn.dat", "write"), self.seen)
        self.assertIn(("/w/tf1/kine.dat", "read"), self.seen)

    def test_split_call_keeps_its_flags(self):
        # O_WRONLY appeared on the '<unfinished>' half only
        self.assertIn(("/w/tf1/reco.dat", "write"), self.seen)

    def test_interleaved_call_is_not_swallowed(self):
        self.assertIn(("/w/tf1/digi.dat", "read"), self.seen)

    def test_rename_destination_counts_as_written(self):
        self.assertIn(("final.dat", "write"), self.seen)

    def test_directory_open_is_not_part_of_the_graph(self):
        self.assertNotIn("/w/tf1", [p for p, _ in self.seen])

    def test_repeated_accesses_collapse(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "trace_0_t.log")
            line = ('9 openat(AT_FDCWD</w>, "a.dat", O_RDONLY) = 3</w/a.dat>\n')
            with open(p, "w") as f:
                f.write(line * 500)
            seen, calls = A.parse_trace(p)
        self.assertEqual(seen, {("/w/a.dat", "read")})
        self.assertEqual(calls, 500)


class TestCollect(unittest.TestCase):
    def test_attribution_comes_from_the_file_name(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "trace_3_reco_1.log"), "w") as f:
                f.write(TRACE)
            with open(os.path.join(d, "trace_4_aod_1.log"), "w") as f:
                f.write('7 openat(AT_FDCWD</w/tf1>, "reco.dat", O_RDONLY) '
                        '= 3</w/tf1/reco.dat>\n')
            written, read, tasks, stats = A.collect(d, "/w", ALL)

        self.assertEqual(tasks, ["aod_1", "reco_1"])
        self.assertEqual(written["./tf1/sgn.dat"], {"reco_1"})
        self.assertEqual(read["./tf1/reco.dat"], {"aod_1"})
        # outside the working directory, so not part of the graph
        self.assertNotIn("/usr/lib/libc.so.6", written)
        self.assertNotIn("/usr/lib/libc.so.6", read)

    def test_non_trace_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "notes.txt"), "w") as f:
                f.write("nothing\n")
            _, _, tasks, stats = A.collect(d, "/w", ALL)
        self.assertEqual(tasks, [])
        self.assertEqual(stats["traces"], 0)


class TestCli(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            td = os.path.join(d, "traces")
            os.makedirs(td)
            with open(os.path.join(td, "trace_1_sgnsim_1.log"), "w") as f:
                f.write('9 openat(AT_FDCWD</w/tf1>, "sgn.dat", O_WRONLY|O_CREAT, '
                        '0666) = 3</w/tf1/sgn.dat>\n')
            with open(os.path.join(td, "trace_2_digi_1.log"), "w") as f:
                f.write('9 openat(AT_FDCWD</w/tf1>, "sgn.dat", O_RDONLY) '
                        '= 3</w/tf1/sgn.dat>\n')
            out = os.path.join(d, "report.json")
            subprocess.run(
                [sys.executable,
                 os.path.join(FILEGRAPH_DIR, "analyse_FileIO_strace.py"),
                 "--straceDir", td, "--basedir", "/w", "-o", out],
                check=True, stdout=subprocess.DEVNULL)
            with open(out) as f:
                doc = json.load(f)

        entry = doc["file_report"][0]
        self.assertEqual(entry["file"], "./tf1/sgn.dat")
        self.assertEqual(entry["written_by"], ["sgnsim_1"])
        self.assertEqual(entry["read_by"], ["digi_1"])
        tpl = doc["file_template_report"][0]
        self.assertEqual(tpl["file"], "./tfX/sgn.dat")
        self.assertEqual(tpl["written_by"], ["sgnsim_X"])


if __name__ == "__main__":
    unittest.main()
