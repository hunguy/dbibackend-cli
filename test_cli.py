import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import os
import tempfile
import shutil

# Adjust the path to include the directory containing cli.py
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from cli import main, validate_file, log, ProgressManager

class TestDBIBackendCLI(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Create a temporary directory with test files before running tests."""
        cls.test_dir = tempfile.mkdtemp()
        cls.nsp_dir = os.path.join(cls.test_dir, "nsp")
        os.makedirs(cls.nsp_dir)

        # Create dummy files in the nsp directory
        cls.valid_file = Path(os.path.join(cls.nsp_dir, "valid_file.nsp"))
        with open(cls.valid_file, "wb") as f:
            f.write(os.urandom(1024))  # Write 1KB of random data

        cls.empty_file = Path(os.path.join(cls.nsp_dir, "empty_file.nsp"))
        with open(cls.empty_file, "wb") as f:
            pass  # Create an empty file

        cls.file1 = Path(os.path.join(cls.nsp_dir, "file1.nsp"))
        with open(cls.file1, "wb") as f:
            f.write(os.urandom(2048))

        cls.not_a_file = Path(os.path.join(cls.nsp_dir, "not_a_file.nsp"))
        os.makedirs(cls.not_a_file)


    @classmethod
    def tearDownClass(cls):
        """Remove the temporary directory and its contents after running tests."""
        shutil.rmtree(cls.test_dir)

    @patch('cli.usb.core.find')
    @patch('cli.argparse.ArgumentParser.parse_args')
    def test_main_no_switch(self, mock_parse_args, mock_usb_find):
        """Test the main function without connecting to a Switch."""
        mock_parse_args.return_value = MagicMock(
            paths=[self.file1.__str__()],
            debug=True,
            filter=None,
            retry_count=1,
            timeout=0
        )
        mock_usb_find.return_value = None

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)

    def test_validate_file(self):
        """Test the validate_file function."""

        is_valid, error = validate_file(self.valid_file)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        invalid_file = Path('/path/to/invalid_file.nsp')
        is_valid, error = validate_file(invalid_file)
        self.assertFalse(is_valid)
        self.assertEqual(error, "File does not exist")

        is_valid, error = validate_file(self.not_a_file)
        self.assertFalse(is_valid)
        self.assertEqual(error, "Not a file")

        is_valid, error = validate_file(self.empty_file)
        self.assertFalse(is_valid)
        self.assertEqual(error, "File is empty")

    @patch('cli.ProgressManager.start_transfer')
    @patch('cli.ProgressManager.create_progress_bar')
    @patch('cli.ProgressManager.update_progress')
    @patch('cli.ProgressManager.complete_file')
    def test_progress_manager(self, mock_complete_file, mock_update_progress, mock_create_progress_bar, mock_start_transfer):
        """Test the ProgressManager class."""
        file_list = {'file1.nsp': self.file1}
        progress_manager = ProgressManager(file_list, debug_mode=True)

        progress_manager.start_transfer()
        mock_start_transfer.assert_called_once()

        task_id = progress_manager.create_progress_bar('file1.nsp', 1024, 0)
        mock_create_progress_bar.assert_called_once_with('file1.nsp', 1024, 0)

        progress_manager.update_progress('file1.nsp', 512)
        mock_update_progress.assert_called_once_with('file1.nsp', 512)

        progress_manager.complete_file('file1.nsp')
        mock_complete_file.assert_called_once_with('file1.nsp')

if __name__ == '__main__':
    unittest.main()
