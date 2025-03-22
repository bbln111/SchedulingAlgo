#!/usr/bin/env python3
"""
End-to-End Test Runner for SchedulingAlgo

This script runs the end-to-end tests for the SchedulingAlgo project.
It provides options for running specific tests or all tests.
"""

import unittest
import sys
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path


# Setup logging
def setup_logging(verbose=False):
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run End-to-End tests for SchedulingAlgo')

    parser.add_argument(
        '--test', '-t',
        dest='test_names',
        nargs='*',
        help='Specific test method names to run (e.g., "test_scheduling_with_existing_inputs")'
    )

    parser.add_argument(
        '--input', '-i',
        dest='input_file',
        help='Specific input file to test with (relative to input_for_testing directory)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available tests without running them'
    )

    return parser.parse_args()


def main():
    """Main function to run the tests."""
    args = parse_arguments()
    setup_logging(args.verbose)

    logger = logging.getLogger("TestRunner")
    logger.info(f"Starting E2E tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Set verbose flag in environment variable for tests to use
    if args.verbose:
        os.environ['VERBOSE_TESTING'] = '1'

    # List all tests if requested
    if args.list:
        # Just use unittest's built-in discovery to list tests
        print("Available tests:")
        tests = unittest.defaultTestLoader.discover('.', pattern='e2e_*.py')
        for test_suite in tests:
            for test_case in test_suite:
                for test in test_case:
                    print(f"  - {test_case.__class__.__name__}.{test._testMethodName}")
        return 0

    # Prepare test arguments
    test_args = []

    # If specific test is requested
    if args.test_names:
        for test_name in args.test_names:
            test_args.extend(['-k', test_name])

    # If specific input file is requested, set environment variable
    if args.input_file:
        os.environ['TEST_INPUT_FILE'] = args.input_file

    # Set verbosity
    if args.verbose:
        test_args.append('-v')

    # Run the tests using unittest module directly
    unittest_args = [sys.argv[0]] + test_args + ['e2e_test_implementation.py']
    sys.argv = unittest_args

    # Run unittest directly
    unittest.main(module=None)

    return 0


if __name__ == "__main__":
    main()
