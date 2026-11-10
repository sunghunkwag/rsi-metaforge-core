"""test_vocabulary_matches_VOCABULARY_md and the vocabulary's basic invariants."""
import re
import unittest
from pathlib import Path

from rsi5.dsl.types import PRIMITIVE_TYPES, ORIGINAL_PRIMITIVE_TYPES, RESTORED_PRIMITIVE_TYPES
from rsi5.dsl.vocabulary import ORIGINAL, RESTORED

DOC = Path(__file__).resolve().parents[1] / "dsl" / "VOCABULARY.md"


def _rows(section_title):
    text = DOC.read_text(encoding="utf-8")
    start = text.index(section_title)
    end = text.find("\n## ", start + 1)
    block = text[start:end if end > 0 else None]
    rows = []
    for line in block.splitlines():
        if line.startswith("| `") or line.startswith("| integer") or line.startswith("| boolean"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows.append(cells)
    return rows


class VocabularyMatchesDocument(unittest.TestCase):
    def _symbols(self, rows):
        found = {}
        for cells in rows:
            names = re.findall(r"`([^`]+)`", cells[0])
            if cells[0].startswith("integer constants"):
                found["__ints__"] = tuple(int(k) for k in re.findall(r"-?\d+", cells[1]))
            elif cells[0].startswith("boolean constants"):
                found["__bools__"] = cells[1]
            else:
                for name in names:
                    found[name] = cells[1].strip("`")
        return found

    def test_vocabulary_matches_VOCABULARY_md(self):
        """The test OWNER_DIRECTIVE.md section 11 names: both sections of the document against
        the two vocabularies (the two tests below, one per section)."""
        self.test_original_section_matches_vocabulary()
        self.test_restored_section_matches_vocabulary()
        listed = set(self._symbols(_rows("## ORIGINAL"))) | set(self._symbols(_rows("## RESTORED")))
        self.assertEqual(listed - {"__ints__", "__bools__"}, set(PRIMITIVE_TYPES))

    def test_original_section_matches_vocabulary(self):
        found = self._symbols(_rows("## ORIGINAL"))
        ints = found.pop("__ints__")
        found.pop("__bools__")
        self.assertEqual(ints, ORIGINAL.integer_constants)
        self.assertEqual(set(found), set(ORIGINAL.primitives))
        self.assertEqual(set(found), set(ORIGINAL_PRIMITIVE_TYPES))
        for name, type_text in found.items():
            self.assertEqual(type_text, str(PRIMITIVE_TYPES[name]), name)

    def test_restored_section_matches_vocabulary(self):
        found = self._symbols(_rows("## RESTORED"))
        ints = found.pop("__ints__")
        self.assertEqual(ints, RESTORED.integer_constants)
        self.assertEqual(set(found), set(RESTORED_PRIMITIVE_TYPES))
        self.assertEqual(set(found) | set(ORIGINAL.primitives), set(RESTORED.primitives))
        for name, type_text in found.items():
            self.assertEqual(type_text, str(PRIMITIVE_TYPES[name]), name)

    def test_restored_extends_original_only(self):
        self.assertEqual(RESTORED.primitives[:len(ORIGINAL.primitives)], ORIGINAL.primitives)
        self.assertEqual(ORIGINAL.integer_constants, (-1, 0, 1, 2))
        self.assertEqual(RESTORED.integer_constants, (-1, 0, 1, 2, 3, 4, 5))
        self.assertEqual(len(ORIGINAL.primitives), 26)
        self.assertEqual(len(RESTORED.primitives), 35)

    def test_original_signatures_equal_rsi2(self):
        from rsi2.types import PRIMITIVE_TYPES as RSI2
        self.assertEqual(set(RSI2), set(ORIGINAL_PRIMITIVE_TYPES))
        for name, type_ in RSI2.items():
            self.assertEqual(str(type_), str(ORIGINAL_PRIMITIVE_TYPES[name]), name)


if __name__ == "__main__":
    unittest.main()
