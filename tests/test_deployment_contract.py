import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentContractTest(unittest.TestCase):
    def test_streamlit_is_pinned_for_reproducible_cloud_rebuilds(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

        self.assertIn("streamlit==1.63.0", requirements)


if __name__ == "__main__":
    unittest.main()
