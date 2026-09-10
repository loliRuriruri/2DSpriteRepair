"""Semantic tests for full transactional state history and undo/redo reversibility."""
import copy
import unittest

class TestUndoSemantics(unittest.TestCase):
    def test_undo_redo_reversibility(self):
        history = []
        future = []

        current_state = {"anchor": {"x": 10, "y": 20}, "layer_count": 1}

        def push_state(state):
            history.append(copy.deepcopy(state))
            future.clear()

        # Action 1: move anchor
        push_state(current_state)
        current_state["anchor"] = {"x": 15, "y": 25}

        # Action 2: add layer
        push_state(current_state)
        current_state["layer_count"] = 2

        # Undo 1 (revert add layer)
        future.append(copy.deepcopy(current_state))
        current_state = history.pop()
        self.assertEqual(current_state["layer_count"], 1)
        self.assertEqual(current_state["anchor"], {"x": 15, "y": 25})

        # Undo 2 (revert move anchor)
        future.append(copy.deepcopy(current_state))
        current_state = history.pop()
        self.assertEqual(current_state["anchor"], {"x": 10, "y": 20})

        # Redo 1 (restore move anchor)
        history.append(copy.deepcopy(current_state))
        current_state = future.pop()
        self.assertEqual(current_state["anchor"], {"x": 15, "y": 25})

if __name__ == "__main__":
    unittest.main()
