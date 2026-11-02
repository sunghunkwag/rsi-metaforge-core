"""Interface invariants (OWNER_DIRECTIVE.md §3, §9): one shared import, vectors only, no cross-reading."""
import ast
from pathlib import Path
import unittest

import numpy as np

from swarm import latent

PACKAGE = Path(__file__).resolve().parents[1]


def package_imports(path: Path) -> set:
    """Absolute ``swarm.*`` modules a file imports (relative imports resolve inside its own package)."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("swarm"))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and (node.module or "").startswith("swarm"):
                module = node.module
                found.update(module if module != "swarm" else f"swarm.{a.name}" for a in node.names)
    return found


def agent_files(name: str):
    return sorted(p for p in (PACKAGE / name).glob("*.py") if p.name != "__init__.py")


class ImportTests(unittest.TestCase):
    def test_agents_share_exactly_one_package_import(self):
        for agent in ("breaker", "builder"):
            files = agent_files(agent)
            self.assertTrue(files)
            imported = set()
            for path in files:
                imported |= package_imports(path)
            self.assertEqual(imported, {"swarm.latent"}, f"{agent} imports {sorted(imported)}")

    def test_agents_do_not_read_each_other_or_the_kernel(self):
        for agent, other in (("breaker", "builder"), ("builder", "breaker")):
            for path in agent_files(agent):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(f"swarm.{other}", text, str(path))
                self.assertNotIn(f"swarm/{other}", text, str(path))
                self.assertNotIn("swarm.kernel", text, str(path))
                self.assertNotIn("swarm.mapper", text, str(path))
        # The mutable tree is the Builder's; the Breaker names no file of it.
        for path in agent_files("breaker"):
            self.assertNotIn("mutable", path.read_text(encoding="utf-8"), str(path))


class ChannelTests(unittest.TestCase):
    def test_ports_exchange_vectors_only(self):
        field = latent.Field(d=256)
        breaker, builder = field.port("breaker"), field.port("builder")
        for junk in ("text", {"summary": 1}, [1, 2, 3], 3.0, np.zeros(255, dtype=np.int8)):
            with self.assertRaises(TypeError):
                breaker.write(junk, tag=0)
        vector = latent.random_vector(256, 1)
        breaker.write(vector, tag=4)
        read = builder.read()
        self.assertIsInstance(read, np.ndarray)
        self.assertEqual(read.shape, (1, 256))
        self.assertEqual(builder.read_tags(), [4])
        self.assertEqual(len(breaker.read()), 0, "an agent reads the other's region, not its own")
        self.assertIsInstance(builder.read_summary(), np.ndarray)
        self.assertFalse(hasattr(breaker, "_field") and hasattr(breaker._field, "text"))

    def test_port_public_surface_is_vectors_and_integer_tags(self):
        public = [name for name in dir(latent.Port) if not name.startswith("_")]
        self.assertEqual(sorted(public), ["read", "read_summary", "read_tags", "write"])

    def test_shuffled_field_destroys_what_is_read(self):
        plain, shuffled = latent.Field(d=2048), latent.Field(d=2048, shuffled=True, seed=3)
        vector = latent.random_vector(2048, 9)
        plain.port("breaker").write(vector, tag=0)
        shuffled.port("breaker").write(vector, tag=0)
        self.assertEqual(latent.similarity(plain.port("builder").read()[0], vector), 1.0)
        self.assertLess(abs(latent.similarity(shuffled.port("builder").read()[0], vector)), 0.1)


if __name__ == "__main__":
    unittest.main()
