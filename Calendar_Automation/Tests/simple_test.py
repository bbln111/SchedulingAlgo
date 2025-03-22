# Save as simple_test.py in the same directory
import unittest

class SimpleTest(unittest.TestCase):
    def test_basic(self):
        print("Running basic test")
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
