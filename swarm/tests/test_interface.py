"""Interface invariants (OWNER_DIRECTIVE.md §3, §9): one shared import, vectors only, no cross-reading."""
import ast
from pathlib import Path
import tempfile
import unittest

import numpy as np

from swarm import latent

PACKAGE = Path(__file__).resolve().parents[1]
# Names an agent file may not use: ways around the import audit (dynamic import,
# object-graph walks, reaching the kernel through a handed-over bound method).
BANNED_NAMES = ("importlib", "__import__", "__self__", "__closure__", "__globals__", "__subclasses__",
                "gc", "inspect", "ctypes", "subprocess", "socket", "builtins", "sys.modules", "exec(", "eval(")


def package_of(path: Path) -> str:
    """The dotted package a file belongs to, from its place under the swarm package."""
    relative = path.resolve().relative_to(PACKAGE.parent)
    return ".".join(relative.parts[:-1])


def package_imports(path: Path, package: str | None = None) -> set:
    """Every ``swarm.*`` module a file imports, absolute or relative (relative imports are resolved)."""
    package = package_of(path) if package is None else package
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("swarm"))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                parts = package.split(".")
                base = ".".join(parts[:len(parts) - (node.level - 1)] + ([node.module] if node.module else []))
            if not base.startswith("swarm"):
                continue
            for alias in node.names:
                candidate = f"{base}.{alias.name}"
                # ``from swarm.x import name``: name is a module when a file by that name exists.
                target = PACKAGE.parent / Path(*candidate.split("."))
                found.add(candidate if (target.with_suffix(".py").exists() or target.is_dir()) else base)
    return found


def agent_files(name: str, recursive: bool = False):
    pattern = "**/*.py" if recursive else "*.py"
    return sorted(p for p in (PACKAGE / name).glob(pattern) if p.name != "__init__.py" and "__pycache__" not in p.parts)


class ImportTests(unittest.TestCase):
    def test_relative_and_dynamic_imports_are_seen(self):
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "probe.py"
            probe.write_text("from ..kernel import vault\nfrom .. import mapper\nfrom . import forge\n"
                             "import swarm.loop\n", encoding="utf-8")
            found = package_imports(probe, package="swarm.builder")
            self.assertEqual(found, {"swarm.kernel.vault", "swarm.mapper", "swarm.builder.forge", "swarm.loop"})

    def test_agents_share_exactly_one_package_import(self):
        for agent in ("breaker", "builder"):
            files = agent_files(agent)
            self.assertTrue(files)
            imported = set()
            for path in files:
                imported |= {m for m in package_imports(path) if not m.startswith(f"swarm.{agent}.")}
            self.assertEqual(imported, {"swarm.latent"}, f"{agent} imports {sorted(imported)}")

    def test_mutable_tree_imports_only_the_checker_language(self):
        """The Builder's tree (run by the guarded executor) imports nothing of swarm but the kernel's checker language."""
        imported = set()
        for path in agent_files("builder/mutable", recursive=True):
            imported |= {m for m in package_imports(path) if not m.startswith("swarm.builder.mutable")}
        self.assertEqual(imported, {"swarm.kernel.checker_lang"}, sorted(imported))

    def test_agents_do_not_read_each_other_or_the_kernel(self):
        for agent, other in (("breaker", "builder"), ("builder", "breaker")):
            for path in agent_files(agent):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(f"swarm.{other}", text, str(path))
                self.assertNotIn(f"swarm/{other}", text, str(path))
                self.assertNotIn("swarm.kernel", text, str(path))
                self.assertNotIn("swarm.mapper", text, str(path))
                for name in BANNED_NAMES:
                    self.assertNotIn(name, text, f"{path}: {name}")
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
        self.assertFalse(hasattr(breaker, "_field"), "a port holds no reference to the field")

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
