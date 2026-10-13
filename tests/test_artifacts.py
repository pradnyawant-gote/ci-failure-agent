import unittest
from pathlib import Path
from unittest.mock import patch

from ci_diagnosis.evaluation import write_python_artifact
from ci_diagnosis.probability import ValidationError


class ArtifactTests(unittest.TestCase):
    def test_python_payload_roundtrip_including_infinite_metric(self):
        with patch.object(Path,"mkdir"), patch.object(Path,"write_text") as write:
            path=Path("results.py")
            original={"metric":float("inf"),"record":{"case":"one","status":"signal"},"missing":None}
            write_python_artifact(path,original)
            source=write.call_args.args[0]
            namespace={};exec(compile(source,str(path),"exec"),namespace)
            self.assertEqual(namespace["EVALUATION"],original)
            self.assertIn("PAYLOAD_SHA256",namespace)

    def test_artifact_exclusively_python_and_rejects_nan(self):
        with patch.object(Path,"mkdir"), patch.object(Path,"write_text"):
            with self.assertRaises(ValidationError):
                write_python_artifact(Path("results.json"),{})
            with self.assertRaises(ValidationError):
                write_python_artifact(Path("results.py"),{"bad":float("nan")})

