#!/usr/bin/env python3
"""
Unit tests for the improved david_sdk module
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the parent directory to the path for imports
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
sys.path.append(str(parent_dir))

# Import the module to test
import david_sdk


class TestDavidSDK(unittest.TestCase):
    """Test cases for the david_sdk module"""

    def setUp(self):
        """Set up test fixtures before each test"""
        # Create a sample input file
        self.sample_data = {
            "start_date": "2025-03-01",
            "appointments": [
                {
                    "id": "1",
                    "priority": "High",
                    "type": "zoom",
                    "time": 60,
                    "days": [
                        {
                            "day": "Monday",
                            "time_frames": [
                                {
                                    "start": "2025-03-03T10:00:00",
                                    "end": "2025-03-03T12:00:00"
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        # Create a temporary file to use for tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.input_file = os.path.join(self.temp_dir.name, "input.json")

        with open(self.input_file, 'w', encoding='utf-8') as f:
            json.dump(self.sample_data, f)

    def tearDown(self):
        """Clean up test fixtures after each test"""
        self.temp_dir.cleanup()

    def test_import_module_from_path(self):
        """Test importing a module from a path"""
        # Create a temporary Python module
        module_content = """
def test_function():
    return "Hello World"
        """
        module_path = os.path.join(self.temp_dir.name, "test_module.py")
        with open(module_path, 'w', encoding='utf-8') as f:
            f.write(module_content)

        # Import the module
        module = david_sdk.import_module_from_path(module_path)

        # Verify the module was imported correctly
        self.assertTrue(hasattr(module, "test_function"))
        self.assertEqual(module.test_function(), "Hello World")

    def test_find_flask_script(self):
        """Test finding Flask script in common locations"""
        # Mock Path.exists to return True for a test path
        with patch('pathlib.Path.exists', return_value=True):
            script_path = david_sdk.find_flask_script()
            self.assertIsNotNone(script_path)

    @patch('david_sdk.import_module_from_path')
    def test_run_flask_server_direct_mode(self, mock_import):
        """Test run_flask_server direct mode"""
        # Create a mock module with scheduler functions
        mock_module = MagicMock()
        mock_module.ScheduleSettings = MagicMock()
        mock_module.parse_appointments.return_value = []
        mock_module.schedule_appointments.return_value = (True, {}, [])
        mock_module.format_output.return_value = {"filled_appointments": [], "unfilled_appointments": []}

        # Make the import_module_from_path function return our mock
        mock_import.return_value = mock_module

        # Call the function
        result = david_sdk.run_flask_server("dummy_path", {"start_date": "2025-03-01"})

        # Verify the result
        self.assertEqual(result, {"filled_appointments": [], "unfilled_appointments": []})

    def test_run_on_file_nonexistent_file(self):
        """Test run_on_file with a nonexistent file"""
        result = david_sdk.run_on_file("nonexistent_file.json")

        # Verify the result
        self.assertEqual(result.get("validation", {}).get("valid"), False)
        self.assertTrue(any("not found" in issue for issue in result.get("validation", {}).get("issues", [])))

    def test_run_on_file_invalid_json(self):
        """Test run_on_file with invalid JSON"""
        # Create a file with invalid JSON
        invalid_json_file = os.path.join(self.temp_dir.name, "invalid.json")
        with open(invalid_json_file, 'w', encoding='utf-8') as f:
            f.write("{invalid json")

        result = david_sdk.run_on_file(invalid_json_file)

        # Verify the result
        self.assertEqual(result.get("validation", {}).get("valid"), False)
        self.assertTrue(any("Invalid JSON" in issue for issue in result.get("validation", {}).get("issues", [])))

    @patch('david_sdk.run_flask_server')
    @patch('pathlib.Path.exists')
    def test_run_on_file_direct_mode(self, mock_exists, mock_run_flask):
        """Test run_on_file in direct mode"""
        # Set up the mock for Path.exists
        mock_exists.return_value = True

        # Set up the mock to return a sample result
        mock_result = {
            "filled_appointments": [{"id": "1", "type": "zoom"}],
            "unfilled_appointments": [],
            "validation": {"valid": True, "issues": []}
        }
        mock_run_flask.return_value = mock_result

        # Run with the input file
        result = david_sdk.run_on_file(self.input_file, "dummy_flask_script")

        # Verify that run_flask_server was called with correct parameters
        mock_run_flask.assert_called_once()

        # Just verify that we get the mock result back
        self.assertEqual(result, mock_result)

    @patch('requests.post')
    def test_run_on_file_http_mode(self, mock_post):
        """Test run_on_file in HTTP mode"""
        # Set up the mock to return a sample result
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "filled_appointments": [{"id": "1", "type": "zoom"}],
            "unfilled_appointments": [],
            "validation": {"valid": True, "issues": []}
        }
        mock_post.return_value = mock_response

        # Run with the input file but no Flask script
        with patch('david_sdk.find_flask_script', return_value=None):
            result = david_sdk.run_on_file(self.input_file)

            # Verify the result
            self.assertEqual(len(result.get("filled_appointments", [])), 1)


if __name__ == '__main__':
    unittest.main()
