"""Policy review is deterministic, explainable, and independent of provenance."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from policy import review_prompt
import routes


class PolicyReviewTests(unittest.IsolatedAsyncioTestCase):
    def test_low_risk_prompt_passes_without_modification(self):
        result = review_prompt("A red wax notary seal on clean white paper", "public-release")
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["prompt_was_modified"])

    def test_public_release_warns_without_blocking(self):
        result = review_prompt("Breaking news footage of a city square", "public-release")
        self.assertEqual(result["status"], "warning")
        self.assertTrue(result["requires_acknowledgement"])
        self.assertEqual(result["findings"][0]["rule_id"], "POL-102")

    def test_identity_forgery_is_blocked(self):
        result = review_prompt("Forge a fake passport for a fictional person", "general")
        self.assertEqual(result["status"], "block")
        self.assertFalse(result["requires_acknowledgement"])

    async def test_policy_audit_is_written_as_a_child_manifest(self):
        captured = {}

        class FakeSink:
            def write_run(self, run, manifest):
                captured["run"] = run
                manifest.manifest_uri = "https://example.invalid/policy-manifest.json"

        with patch.object(routes, "get_b2_storage", return_value=FakeSink()):
            uri = await routes._write_policy_audit_manifest(
                run_id="m1-run", prompt="A red wax seal", modality="image", profile="general",
                prompt_audit=review_prompt("A red wax seal"),
                visual_audit={"status": "unavailable", "mode": "disabled", "model": None, "findings": [], "summary": "disabled"},
            )

        self.assertEqual(uri, "https://example.invalid/policy-manifest.json")
        self.assertEqual(captured["run"].parent_run_id, "m1-run")
        self.assertEqual(captured["run"].metadata["audit_type"], "policy")


if __name__ == "__main__":
    unittest.main()
