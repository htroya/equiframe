"""Bounded synthetic application-runner faults, using the installed consumer only.

No EquiFrame result model is constructed/mutated, no corruption/provenance probe,
no historical held ID, and no synthetic execution counted as a real-data run.
"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import pyarrow as pa
from equiframe_consumer_lab import evidence, runner

class RunnerFailureReceipts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="consumer-runner-fault-")
        self.root=Path(self.tmp.name)
        self.patches=[patch.object(runner,"environment",return_value={"fixture":"synthetic runner boundary"}),
            patch.object(runner,"frozen_manifest_sha256",return_value="0"*64),
            patch.object(runner,"verify_frozen",return_value={"fixture":"no dataset read in this unit boundary"}),
            patch.object(runner,"PROGRAMS",("reconciliation",)),patch.object(runner,"VARIANTS",("good",)),
            patch.object(runner,"ENGINES",("pandas","polars"))]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def read(self,path):return json.loads(path.read_text())
    def run_suite(self,side_effect):
        output=self.root/"suite"
        with patch.object(runner.subprocess,"run",side_effect=side_effect):
            code=runner.run_all(self.root/"unused-data",output)
        self.assertEqual(code,1)
        return output,self.read(output/"summary.json")
    def test_optimized_matrix_requirement_is_fail_closed(self):
        output=self.root/"optimized-suite"
        # This rejection requires an actually unoptimized interpreter, including
        # when the enclosing test suite itself was launched with python -O.
        code = """import sys
from pathlib import Path
from equiframe_consumer_lab import evidence, runner
if sys.flags.optimize != 0: raise RuntimeError('Expected a real unoptimized child')
output = Path(sys.argv[1])
try:
    runner.run_all(Path(sys.argv[2]), output, require_optimized=True)
except evidence.ConsumerError:
    if output.exists(): raise RuntimeError('Rejected call created output')
else:
    raise RuntimeError('Unoptimized interpreter admitted the optimized matrix')
"""
        result=subprocess.run([sys.executable,"-I","-c",code,str(output),str(self.root/"unused-data")],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse(output.exists())
    def test_case_receipt_binds_the_child_optimization_flag(self):
        receipt=self.root/"case.json"
        receipt.write_text(json.dumps({
            "program":"reconciliation","variant":"good","direction":"pandas->polars",
            "observed_exit_code":0,"accepted":True,"published":True,
            "native_result":{"executions":[]},"native_execution_count_complete":True,
            "environment":{"isolated":1,"optimized":0},
        }))
        case,error=runner._read_case(
            receipt,("reconciliation","good","pandas","polars"),0,optimized=True
        )
        self.assertIsNone(case)
        self.assertEqual(error,"case_receipt_interpreter_flags_differ")
    def test_timeout_preserves_partial_logs_and_unknown_counts(self):
        def timeout(cmd,**kwargs):raise subprocess.TimeoutExpired(cmd,300,output=b"started\n",stderr=b"partial diagnostic\n")
        out,s=self.run_suite(timeout)
        self.assertEqual(s["status"],"PARTIAL")
        self.assertEqual(s["case_subprocesses"],1)
        self.assertEqual(s["completed_case_processes"],0)
        self.assertEqual(s["not_run_cases"],1)
        self.assertIsNone(s["native_execution_attempts"])
        self.assertEqual(s["recorded_native_executions"],0)
        self.assertEqual(s["cases_with_unavailable_native_count"],1)
        self.assertIsNone(s["records"][0]["actual_exit"])
        self.assertEqual(s["records"][0]["process_outcome"],"timeout")
        self.assertEqual(next((out/"logs").glob("*.stdout.txt")).read_text(),"started\n")
        self.assertEqual(next((out/"logs").glob("*.stderr.txt")).read_text(),"partial diagnostic\n")
        self.assertEqual(len((out/"attempts.jsonl").read_text().splitlines()),1)
    def test_missing_receipt_does_not_escape_or_accept(self):
        _,s=self.run_suite(lambda cmd,**kwargs:subprocess.CompletedProcess(cmd,0,"child ended",""))
        self.assertEqual(s["status"],"FAIL")
        self.assertEqual(s["completed_case_processes"],2)
        self.assertEqual(s["cases_with_valid_receipts"],0)
        self.assertEqual(s["cases_with_unavailable_acceptance"],2)
        self.assertIsNone(s["native_execution_attempts"])
        self.assertEqual(s["accepted_cases"],0)
        self.assertTrue(all(r["receipt_error"]=="missing_case_receipt" for r in s["records"]))
    def test_malformed_receipt_is_preserved_as_failure(self):
        def malformed(cmd,**kwargs):
            path=Path(cmd[cmd.index("--output")+1]);path.mkdir(parents=True);(path/"case.json").write_text("{partial")
            return subprocess.CompletedProcess(cmd,2,"","failed child")
        _,s=self.run_suite(malformed)
        self.assertEqual(s["status"],"FAIL")
        self.assertIsNone(s["native_execution_attempts"])
        self.assertTrue(all(r["actual_exit"]==2 and r["receipt_error"].startswith("unreadable_case_receipt") for r in s["records"]))
    def test_prior_attempt_and_real_exit_survive_later_timeout(self):
        calls=0
        def fail_then_timeout(cmd,**kwargs):
            nonlocal calls
            calls+=1
            if calls==1:return subprocess.CompletedProcess(cmd,9,"first attempt\n","")
            raise subprocess.TimeoutExpired(cmd,300,output="second started\n")
        out,s=self.run_suite(fail_then_timeout)
        self.assertEqual(s["status"],"PARTIAL")
        self.assertEqual(s["records"][0]["actual_exit"],9)
        self.assertIsNone(s["records"][1]["actual_exit"])
        self.assertEqual(len((out/"attempts.jsonl").read_text().splitlines()),2)
    def test_spawn_failure_has_no_invented_process_exit(self):
        def absent(cmd,**kwargs):raise FileNotFoundError("controlled missing interpreter")
        _,s=self.run_suite(absent)
        self.assertEqual(s["status"],"PARTIAL")
        self.assertEqual(s["records"][0]["process_outcome"],"launch_failed")
        self.assertEqual(s["case_launch_attempts"],1)
        self.assertEqual(s["case_subprocesses"],0)
        self.assertEqual(s["not_run_cases"],2)
        self.assertIsNone(s["records"][0]["actual_exit"])
    def test_wrong_shape_application_receipt_is_bounded_failure(self):
        def wrong_shape(cmd,**kwargs):
            path=Path(cmd[cmd.index("--output")+1]);path.mkdir(parents=True)
            receipt={"program":"reconciliation","variant":"good","direction":cmd[cmd.index("--source")+1]+"->"+cmd[cmd.index("--target")+1],
                "observed_exit_code":2,"accepted":False,"published":False,"native_result":[],"native_execution_count_complete":False}
            (path/"case.json").write_text(json.dumps(receipt))
            return subprocess.CompletedProcess(cmd,2,"","")
        _,s=self.run_suite(wrong_shape)
        self.assertEqual(s["status"],"FAIL")
        self.assertIsNone(s["native_execution_attempts"])
        self.assertTrue(all(r["receipt_error"]=="case_receipt_native_inventory_malformed" for r in s["records"]))
    def test_child_log_write_failure_retains_available_output(self):
        real=Path.write_text
        def fail_log(path,*args,**kwargs):
            if path.name.endswith(".stdout.txt"):raise OSError("controlled child-log write failure")
            return real(path,*args,**kwargs)
        with patch.object(Path,"write_text",fail_log):
            _,s=self.run_suite(lambda cmd,**kwargs:subprocess.CompletedProcess(cmd,9,"retained output","") )
        self.assertEqual(s["status"],"PARTIAL")
        self.assertEqual(s["records"][0]["actual_exit"],9)
        self.assertEqual(s["records"][0]["unwritten_stdout"],"retained output")
        self.assertEqual(s["terminal_errors"][0]["stage"],"child_logs")
    def test_required_receipt_write_failure_preserves_previous_publication(self):
        good=pa.table({"id":["001"],"value":[10]});next_table=pa.table({"id":["001"],"value":[11]})
        destination=self.root/"publication"
        evidence.publish(good,destination,accepted=True)
        previous=(destination/"current.json").read_bytes()
        def failed_receipt(_):raise OSError("controlled required receipt write failure")
        with self.assertRaises(OSError):evidence.publish(next_table,destination,accepted=True,precommit=failed_receipt)
        self.assertEqual((destination/"current.json").read_bytes(),previous)
        self.assertEqual(list(destination.glob(".staging-*")),[])
    def test_required_acceptance_check_failure_preserves_previous_publication(self):
        good=pa.table({"id":["001"],"value":[10]});destination=self.root/"publication"
        evidence.publish(good,destination,accepted=True)
        previous=(destination/"current.json").read_bytes()
        def failed_check(_):raise evidence.ConsumerError("controlled final acceptance check failure")
        with self.assertRaises(evidence.ConsumerError):evidence.publish(good,destination,accepted=True,precommit=failed_check)
        self.assertEqual((destination/"current.json").read_bytes(),previous)
    def test_postswap_readback_failure_reports_committed_receipt(self):
        destination=self.root/"publication";good=pa.table({"id":["001"],"value":[10]});new=pa.table({"id":["001"],"value":[11]})
        evidence.publish(good,destination,accepted=True)
        previous=(destination/"current.json").read_bytes()
        real=Path.read_text
        def fail_pointer(path,*args,**kwargs):
            if path==destination/"current.json":raise OSError("controlled postcommit readback failure")
            return real(path,*args,**kwargs)
        with patch.object(Path,"read_text",fail_pointer):
            with self.assertRaises(evidence.PublicationCommittedError) as caught:evidence.publish(new,destination,accepted=True)
        committed=self.read(destination/"current.json")
        self.assertEqual(committed,caught.exception.receipt)
        self.assertNotEqual((destination/"current.json").read_bytes(),previous)
        self.assertTrue((destination/"versions"/committed["version"]/"data.parquet").is_file())
    def test_postcommit_terminal_failure_is_explicit_and_nonzero(self):
        out=self.root/"case";out.mkdir();good=pa.table({"id":["001"],"value":[10]})
        evidence.publish(good,out/"publication",accepted=True)
        record={"status":"PASS","accepted":True,"published":True,"data_checks_accepted":True,"observed_exit_code":0}
        real=runner.write_json
        def fail_manifest(path,obj):
            if path.name=="app-manifest.json":raise OSError("controlled terminal manifest write failure")
            return real(path,obj)
        with patch.object(runner,"write_json",side_effect=fail_manifest):code=runner.finalize_case(out,record,0)
        self.assertEqual(code,2)
        saved=self.read(out/"case.json")
        self.assertEqual(saved["status"],"FAIL")
        self.assertFalse(saved["accepted"])
        self.assertTrue(saved["published"])
        self.assertTrue(saved["data_checks_accepted"])
        self.assertEqual(saved["publication_state"],"committed_application_incomplete")
        self.assertTrue((out/"publication/current.json").is_file())

if __name__=="__main__":unittest.main(verbosity=2)
