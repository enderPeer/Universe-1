import unittest
from share_bridge import merge_files


class MergeTests(unittest.TestCase):
    def test_independent_handoffs_are_preserved(self):
        self.assertEqual(merge_files({'claude.md':['100644','a']}, {'codex.md':['100644','b']}, {}),
                         {'claude.md':['100644','a'],'codex.md':['100644','b']})

    def test_single_writer_update(self):
        old = {'note':['100644','old']}
        new = {'note':['100644','new']}
        self.assertEqual(merge_files(new, old, old), new)
        self.assertEqual(merge_files(old, new, old), new)

    def test_deletion_propagates(self):
        old = {'note':['100644','old']}
        self.assertEqual(merge_files({}, old, old), {})

    def test_conflicting_edits_and_delete_edit_preserve_histories(self):
        old = {'note':['100644','old']}
        with self.assertRaisesRegex(RuntimeError, 'note'):
            merge_files({'note':['100644','a']}, {'note':['100644','b']}, old)
        with self.assertRaisesRegex(RuntimeError, 'note'):
            merge_files({}, {'note':['100644','edited']}, old)


if __name__ == '__main__':
    unittest.main()
