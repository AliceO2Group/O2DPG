#!/usr/bin/env python3
"""Offline test: publish_MCProdInfo uploads a new version only when the content of a tag and run changes."""
import os
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import quote, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import mcprodinfo_ccdb_upload as up

TAG = "LHC26h3_nodelta"
RUN = 572196
V12 = "VO_ALICE@O2PDPSuite::MC-prod-2026-v12-1"
V15 = "VO_ALICE@O2PDPSuite::MC-prod-2026-v15-1"
OUT = "/alice/sim/2026/LHC26h3_nodelta/0"


def listing(*objects):
    """A CCDB browse listing in text form; objects are (created, metadata) pairs."""
    text = f"Listing content of Users/a/aliprod/MCProdInfo/{TAG}\n\n"
    for created, meta in objects:
        text += f"ID: id-{created}\nPath: Users/a/aliprod/MCProdInfo/{TAG}\nCreated: {created} (some date)\nMetadata:\n"
        text += "".join(f"  {k} = {v}\n" for k, v in meta.items()) + "\n\n"
    return text + "Subfolders:\n"


def stored(**over):
    """Metadata of a stored object, as CCDB lists it (values URL-encoded as uploaded)."""
    meta = {"Col": "PbPb", "Comment": "FirstOrbitMC added because of O2-7335", "RunNumber": RUN,
            "FirstOrbitMC": 27020420, "IntRate": 23425.04719279499, "OrbitsPerTF": 6, "UploadedBy": "swenzel",
            "Hash": "1974c68783c1a1115868bd69b1d392209d4aefbdb42d89e4fc298025d79d975b",
            "LPMProductionTag": TAG, "partName": "blob", "McTag": V12, "OutputDir": OUT, "MasterJobID": 3500000000}
    meta.update(over)
    return {k: (quote(v, safe="@:,") if k == "OutputDir" and v else v) for k, v in meta.items() if v is not None}


def job(**over):
    """The object a job of the anchored workflow builds."""
    kw = dict(LPMProductionTag=TAG, Col="PbPb", IntRate=21000.5, RunNumber=RUN, OrbitsPerTF=6, McTag=V12,
              FirstOrbitMC=27020420, MasterJobID=3500000000, OutputDir=OUT)
    kw.update(over)
    return up.MCProdInfo(**kw)


class Response:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.content = text.encode()
        self.text = text


class FakeCCDBCase(unittest.TestCase):
    """Runs publish_MCProdInfo against a mocked CCDB in a temporary directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def publish(self, info, listing_text, force=False, complete=True, post_status=201, posts=None):
        """Runs publish_MCProdInfo against a fake CCDB; returns the uploaded metadata or None, and the output."""
        get = Response(200, listing_text) if listing_text is not None else Response(404)
        with mock.patch.object(up.requests, "get", return_value=get), \
             mock.patch.object(up.requests, "post", return_value=Response(post_status, "error"), side_effect=posts) as post, \
             mock.patch("builtins.print") as out:
            cwd = os.getcwd()
            os.chdir(self.tmp.name)
            try:
                up.publish_MCProdInfo(info, ccdb_url="http://ccdb", username="aliprod", force_overwrite=force,
                                      complete=complete)
            finally:
                os.chdir(cwd)
        text = "\n".join(" ".join(str(a) for a in c.args) for c in out.call_args_list)
        self.posted = [self.metadata(c.args[0]) for c in post.call_args_list]
        return (self.posted[-1] if self.posted else None), text

    @staticmethod
    def metadata(url):
        """Metadata of an upload URL; values are unescaped after splitting, so slashes survive."""
        return dict(unquote(kv).split("=", 1) for kv in url.split(f"/{RUN}/{RUN + 1}/", 1)[1].split("/"))



class PublishTest(FakeCCDBCase):

    def test_no_object_uploads(self):
        meta, _ = self.publish(job(), None)
        self.assertEqual(meta["McTag"], V12)

    def test_equal_content_does_not_upload(self):
        # IntRate, Comment and a stale Hash differ, the content does not
        meta, out = self.publish(job(), listing((1, stored())))
        self.assertIsNone(meta)
        self.assertIn("up to date", out)

    def test_changed_software_uploads_new_version_with_warning(self):
        meta, out = self.publish(job(McTag=V15, FirstOrbitMC=27020428), listing((1, stored())))
        self.assertEqual(meta["McTag"], V15)
        self.assertEqual(meta["FirstOrbitMC"], "27020428")
        # the comment of the old upload is not carried over to a different production
        self.assertNotIn("Comment", meta)
        self.assertIn("WARNING", out)
        self.assertIn(f"McTag: {V12} -> {V15}", out)
        self.assertIn("FirstOrbitMC: 27020420 -> 27020428", out)
        self.assertIn(TAG, out)
        self.assertIn(str(RUN), out)

    def test_equal_creation_time_takes_highest_id(self):
        text = listing((5, stored(McTag=V12)), (5, stored(McTag=V15))).replace("ID: id-5", "ID: id-a", 1)
        self.assertEqual(up.extract_newest_metadata_from_CCDB(text)["McTag"], V12)
        text = listing((5, stored(McTag=V12)), (5, stored(McTag=V15))).replace("ID: id-5", "ID: id-0", 1)
        self.assertEqual(up.extract_newest_metadata_from_CCDB(text)["McTag"], V15)

    def test_newest_version_is_compared(self):
        # the v15 object is newer, although listed after the v12 one
        text = listing((1, stored()), (2, stored(McTag=V15)))
        meta, _ = self.publish(job(McTag=V15), text)
        self.assertIsNone(meta)

    def test_first_orbit_alone_is_kept(self):
        meta, out = self.publish(job(FirstOrbitMC=27020428), listing((1, stored())))
        self.assertIsNone(meta)
        self.assertIn("Keeping the stored value", out)

    def test_first_orbit_kept_while_adding_fields(self):
        meta, out = self.publish(job(FirstOrbitMC=27020428, OutputDir="/alice/sim/2026/LHC26h3_nodelta/0"),
                                 listing((1, stored(OutputDir=None))))
        self.assertEqual(meta["FirstOrbitMC"], "27020420")
        self.assertEqual(meta["OutputDir"], "/alice/sim/2026/LHC26h3_nodelta/0")

    def test_first_orbit_replaced_when_forced(self):
        meta, _ = self.publish(job(FirstOrbitMC=27020428), listing((1, stored())), force=True)
        self.assertEqual(meta["FirstOrbitMC"], "27020428")

    def test_forced_equal_content_uploads(self):
        meta, _ = self.publish(job(Comment="new comment"), listing((1, stored())), force=True)
        self.assertEqual(meta["Comment"], "new comment")

    def test_adding_reco_tag_and_output_dir_keeps_stored_fields(self):
        meta, out = self.publish(job(FirstOrbitMC=None, RecoTag="O2PDPSuite::async-v6",
                                     OutputDir="/alice/sim/2026/LHC26h3_dev2/0"), listing((1, stored(OutputDir=None))),
                                 complete=False)
        self.assertEqual(meta["RecoTag"], "O2PDPSuite::async-v6")
        self.assertEqual(meta["OutputDir"], "/alice/sim/2026/LHC26h3_dev2/0")
        self.assertEqual(meta["FirstOrbitMC"], "27020420")
        self.assertNotIn("WARNING", out)

    def test_changed_output_dir_alone_is_not_a_new_version(self):
        text = listing((1, stored(OutputDir="/alice/sim/2026/LHC26h3/0")))
        meta, _ = self.publish(job(OutputDir="/alice/sim/2026/LHC26h3_dev2/0"), text)
        self.assertIsNone(meta)

    def test_output_dir_follows_a_new_version(self):
        text = listing((1, stored(OutputDir="/alice/sim/2026/LHC26h3/0")))
        meta, _ = self.publish(job(McTag=V15, OutputDir="/alice/sim/2026/LHC26h3_dev2/0"), text)
        self.assertEqual(meta["OutputDir"], "/alice/sim/2026/LHC26h3_dev2/0")

    def test_stale_writer_is_refused(self):
        # a late job of the v12 cycle after the v15 cycle has written its object
        text = listing((1, stored(McTag=V15, MasterJobID=3600000000)))
        meta, out = self.publish(job(McTag=V12, MasterJobID=3500000000), text)
        self.assertIsNone(meta)
        self.assertIn("not replacing", out)

    def test_writer_without_key_does_not_replace_keyed_object(self):
        text = listing((1, stored(MasterJobID=3600000000)))
        meta, _ = self.publish(job(McTag=V15, MasterJobID=None), text)
        self.assertIsNone(meta)

    def test_keyed_writer_replaces_object_without_key(self):
        meta, _ = self.publish(job(McTag=V15, MasterJobID=3600000000), listing((1, stored(MasterJobID=None))))
        self.assertEqual(meta["MasterJobID"], "3600000000")

    def test_same_masterjob_replaces(self):
        text = listing((1, stored(MasterJobID=3500000000)))
        meta, _ = self.publish(job(McTag=V15), text)
        self.assertEqual(meta["McTag"], V15)

    def test_complete_writer_dropping_reco_tag_is_a_change(self):
        text = listing((1, stored(RecoTag="O2PDPSuite::async-v6")))
        meta, out = self.publish(job(RecoTag=None), text)
        self.assertNotIn("RecoTag", meta)
        self.assertIn("RecoTag: O2PDPSuite::async-v6 -> None", out)

    def test_incomplete_writer_none_is_unknown(self):
        text = listing((1, stored(RecoTag="O2PDPSuite::async-v6")))
        meta, _ = self.publish(job(RecoTag=None), text, complete=False)
        self.assertIsNone(meta)

    def test_float_first_orbit_equals_stored_int(self):
        meta, _ = self.publish(job(FirstOrbitMC=27020420.0), listing((1, stored())))
        self.assertIsNone(meta)

    def test_failed_upload_warns(self):
        meta, out = self.publish(job(), None, post_status=403)
        self.assertIn("WARNING: upload of MCProdInfo", out)
        self.assertIn("HTTP 403", out)

    def test_rejected_upload_is_retried_without_output_dir(self):
        meta, out = self.publish(job(), None, posts=[Response(400, "bad"), Response(201)])
        self.assertEqual(len(self.posted), 2)
        self.assertEqual(self.posted[0]["OutputDir"], OUT)
        self.assertNotIn("OutputDir", meta)
        self.assertEqual(meta["McTag"], V12)
        self.assertIn("retrying", out)

    def test_accepted_upload_is_not_retried(self):
        self.publish(job(), None)
        self.assertEqual(len(self.posted), 1)

    def test_job_outside_production_dir_does_not_replace(self):
        # a release-validation job reusing the tag LHC24e8, writing to a directory without run component
        out_dir = up.production_output_dir("/alice/sim/2024/LHC24e8/v20261121-1/001", RUN)
        self.assertIsNone(out_dir)
        meta, out = self.publish(job(McTag="VO_ALICE@O2sim::v20261121-1", MasterJobID=3761069062, OutputDir=out_dir),
                                 listing((1, stored(MasterJobID=None))))
        self.assertIsNone(meta)
        self.assertIn("outside of a production directory", out)

    def test_job_outside_production_dir_creates_new_object(self):
        meta, _ = self.publish(job(OutputDir=None), None)
        self.assertEqual(meta["McTag"], V12)

    def test_unkeyed_object_gets_masterjob(self):
        meta, out = self.publish(job(), listing((1, stored(MasterJobID=None))))
        self.assertEqual(meta["MasterJobID"], "3500000000")
        self.assertEqual(meta["McTag"], V12)
        self.assertNotIn("WARNING", out)

    def test_adding_first_orbit_is_no_warning(self):
        meta, out = self.publish(job(), listing((1, stored(FirstOrbitMC=None))))
        self.assertEqual(meta["FirstOrbitMC"], "27020420")
        self.assertNotIn("WARNING", out)

    def test_non_numeric_masterjob_is_unkeyed(self):
        meta, out = self.publish(job(McTag=V15), listing((1, stored(MasterJobID="abc"))))
        self.assertEqual(meta["McTag"], V15)
        self.assertIn("non-numeric MasterJobID abc", out)

    def test_fill_keeps_stored_strings(self):
        meta, _ = self.publish(job(), listing((1, stored(Comment="007", MasterJobID=None))))
        self.assertEqual(meta["Comment"], "007")
        self.assertEqual(meta["IntRate"], "23425.04719279499")
        self.assertNotIn("partName", meta)


    def test_rejected_output_dir_fill_is_not_retried(self):
        meta, _ = self.publish(job(), listing((1, stored(OutputDir=None))), posts=[Response(400, "bad"), Response(201)])
        self.assertEqual(len(self.posted), 1)
        self.assertEqual(meta["OutputDir"], OUT)

    def test_production_replaces_object_without_output_dir(self):
        # a validation job with a newer masterjob created the first object
        text = listing((1, stored(McTag="VO_ALICE@O2sim::v20261121-1", OutputDir=None, MasterJobID=3761069062)))
        meta, _ = self.publish(job(McTag=V15, MasterJobID=3600000000), text)
        self.assertEqual(meta["McTag"], V15)
        self.assertEqual(meta["OutputDir"], OUT)

    def test_stale_writer_refused_with_output_dir_on_both(self):
        text = listing((1, stored(McTag=V15, MasterJobID=3600000000)))
        meta, _ = self.publish(job(McTag=V12, MasterJobID=3500000000), text)
        self.assertIsNone(meta)

    def test_complete_fill_raises_masterjob(self):
        meta, _ = self.publish(job(MasterJobID=3600000000), listing((1, stored(FirstOrbitMC=None))))
        self.assertEqual(meta["FirstOrbitMC"], "27020420")
        self.assertEqual(meta["MasterJobID"], "3600000000")

    def test_newer_masterjob_alone_is_no_upload(self):
        meta, _ = self.publish(job(MasterJobID=3600000000), listing((1, stored())))
        self.assertIsNone(meta)

    def test_incomplete_fill_keeps_masterjob(self):
        meta, _ = self.publish(job(MasterJobID=3600000000, FirstOrbitMC=None, RecoTag="O2PDPSuite::async-v6"),
                               listing((1, stored())), complete=False)
        self.assertEqual(meta["RecoTag"], "O2PDPSuite::async-v6")
        self.assertEqual(meta["MasterJobID"], "3500000000")


class OptOutTest(unittest.TestCase):

    def test_disable_variable(self):
        for value, disabled in ((None, False), ("", False), ("0", False), ("1", True), ("yes", True)):
            env = {k: v for k, v in os.environ.items() if k != "ALIEN_JDL_DISABLE_MCPRODINFO"}
            if value is not None:
                env["ALIEN_JDL_DISABLE_MCPRODINFO"] = value
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(up.publishing_disabled(), disabled, value)


class HarvesterTest(FakeCCDBCase):
    """The harvester publishes without complete and, unless --overwrite, only fills empty fields."""

    def harvested(self, **over):
        kw = dict(LPMProductionTag=TAG, Col="PbPb", IntRate=21000.5, RunNumber=RUN, OrbitsPerTF=6, McTag=V12)
        kw.update(over)
        return up.MCProdInfo(**kw)

    def test_does_not_replace_values(self):
        meta, out = self.publish(self.harvested(McTag=V15), listing((1, stored())), complete=False)
        self.assertIsNone(meta)
        self.assertIn("not changing it without force_overwrite", out)

    def test_fills_and_keeps_first_orbit(self):
        meta, _ = self.publish(self.harvested(RecoTag="O2PDPSuite::async-v6", OutputDir=OUT),
                               listing((1, stored(OutputDir=None))), complete=False)
        self.assertEqual(meta["McTag"], V12)
        self.assertEqual(meta["RecoTag"], "O2PDPSuite::async-v6")
        self.assertEqual(meta["OutputDir"], OUT)
        self.assertEqual(meta["FirstOrbitMC"], "27020420")

    def test_conflict_fills_nothing(self):
        # the harvested job belongs to another production than the stored object
        meta, out = self.publish(self.harvested(McTag=V15, RecoTag="O2PDPSuite::async-v6", OutputDir=OUT),
                                 listing((1, stored(OutputDir=None))), complete=False)
        self.assertIsNone(meta)
        self.assertIn(f"McTag: {V12} -> {V15}", out)

    def test_env_from_stdout_ignores_script_lines(self):
        import mcprodinfo_harvester as hv
        script = ('  elif [ "${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG}" ]; then\n'
                  '    echo_error "Alternative-reco (2-tag) requested (ALIEN_JDL_O2DPG_ASYNC_RECO_TAG=${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG})"\n')
        dump = ("ALIEN_JDL_OUTPUTDIR=/alice/sim/2026/LHC26h3/0/572196/001\n"
                f"ALIEN_JDL_PACKAGES={V12}\n"
                "ALIEN_MASTERJOB_ID=3761069062\n")
        env = hv.env_from_stdout(dump + script)
        self.assertNotIn("ALIEN_JDL_O2DPG_ASYNC_RECO_TAG", env)
        self.assertEqual(env["ALIEN_JDL_PACKAGES"], V12)
        self.assertEqual(env["ALIEN_MASTERJOB_ID"], "3761069062")
        self.assertNotIn("ALIEN_MASTERJOB", env)
        env = hv.env_from_stdout(dump + "ALIEN_JDL_O2DPG_ASYNC_RECO_TAG=O2PDPSuite::async-v6\n" + script)
        self.assertEqual(env["ALIEN_JDL_O2DPG_ASYNC_RECO_TAG"], "O2PDPSuite::async-v6")

    def test_overwrite_replaces_and_keeps_first_orbit(self):
        meta, _ = self.publish(self.harvested(McTag=V15), listing((1, stored())), complete=False, force=True)
        self.assertEqual(meta["McTag"], V15)
        self.assertEqual(meta["FirstOrbitMC"], "27020420")

    def test_build_info_takes_output_dir_and_masterjob(self):
        import mcprodinfo_harvester as hv
        info = hv.build_info(TAG, RUN, {"meta": {"col": "PbPb", "interactionRate": 1.0, "orbitsPerTF": 6}},
                             {"ALIEN_JDL_PACKAGES": V12, "ALIEN_MASTERJOB_ID": "3500000000"},
                             f"/alice/sim/2026/{TAG}/0/{RUN}/001/log_archive.zip")
        self.assertEqual(info.OutputDir, f"/alice/sim/2026/{TAG}/0")
        self.assertEqual(info.MasterJobID, 3500000000)
        self.assertIsNone(info.RecoTag)


class ReadTest(unittest.TestCase):

    def test_old_object_without_new_fields_loads(self):
        text = listing((1, {"Col": "pp", "RunNumber": RUN, "IntRate": 500.0, "OrbitsPerTF": 32,
                            "LPMProductionTag": TAG, "McTag": "None", "RecoTag": "None", "Comment": "None"}))
        with mock.patch.object(up.requests, "get", return_value=Response(200, text)):
            info = up.query_mcprodinfo("http://ccdb", "aliprod", RUN, TAG)
        self.assertIsNone(info.OutputDir)
        self.assertIsNone(info.RecoTag)
        self.assertEqual(info.OrbitsPerTF, 32)

    def test_encoded_output_dir_reads_back_decoded(self):
        # ccdb-test keeps the value as uploaded: OutputDir = %2Falice%2Fsim%2F...
        text = listing((1, stored()))
        self.assertIn("%2Falice%2Fsim", text)
        with mock.patch.object(up.requests, "get", return_value=Response(200, text)):
            info = up.query_mcprodinfo("http://ccdb", "aliprod", RUN, TAG)
        self.assertEqual(info.OutputDir, OUT)

    def test_unknown_fields_are_ignored(self):
        text = listing((1, stored(SomeFutureField="x")))
        with mock.patch.object(up.requests, "get", return_value=Response(200, text)):
            info = up.query_mcprodinfo("http://ccdb", "aliprod", RUN, TAG)
        self.assertEqual(info.McTag, V12)


class OutputDirTest(unittest.TestCase):

    def test_run_and_subjob_are_removed(self):
        self.assertEqual(up.production_output_dir("/alice/sim/2026/LHC26a7/0/559783/14378", 559783),
                         "/alice/sim/2026/LHC26a7/0")

    def test_without_run_gives_none(self):
        self.assertIsNone(up.production_output_dir("/alice/cern.ch/user/a/aliprod/test/001", 559783))
        self.assertIsNone(up.production_output_dir(None, 559783))


if __name__ == "__main__":
    unittest.main()
