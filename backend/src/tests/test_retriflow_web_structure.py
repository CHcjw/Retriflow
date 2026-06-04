import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class RetriFlowWebStructureTests(unittest.TestCase):
    def test_expected_frontend_files_exist(self) -> None:
        expected_files = [
            PROJECT_ROOT / "frontend" / "package.json",
            PROJECT_ROOT / "frontend" / "vite.config.ts",
            PROJECT_ROOT / "frontend" / "tsconfig.json",
            PROJECT_ROOT / "frontend" / "index.html",
            PROJECT_ROOT / "frontend" / "src" / "main.ts",
            PROJECT_ROOT / "frontend" / "src" / "App.vue",
            PROJECT_ROOT / "frontend" / "src" / "router" / "index.ts",
            PROJECT_ROOT / "frontend" / "src" / "stores" / "app.ts",
            PROJECT_ROOT / "frontend" / "src" / "views" / "HomeView.vue",
            PROJECT_ROOT / "frontend" / "src" / "views" / "ChatView.vue",
            PROJECT_ROOT / "frontend" / "src" / "views" / "AdminView.vue",
            PROJECT_ROOT / "frontend" / "src" / "assets" / "main.css",
        ]

        missing = [str(path.relative_to(PROJECT_ROOT)) for path in expected_files if not path.exists()]

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
