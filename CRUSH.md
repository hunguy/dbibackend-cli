# CRUSH.md - DBI Backend CLI Development Guide

## Build/Lint/Test Commands

- **Run all tests**: `.venv/bin/python -m unittest test_cli.py -v`
- **Run specific test**: `.venv/bin/python -c "import sys; sys.path.insert(0, '.'); from test_cli import TestDBIBackendCLI; import unittest; suite = unittest.TestSuite(); suite.addTest(TestDBIBackendCLI('test_validate_file')); runner = unittest.TextTestRunner(verbosity=2); runner.run(suite)"`
- **Run CLI tool**: `.venv/bin/python cli.py [files/folders] [options]`
- **Run with uv**: `uv run cli.py [files/folders] [options]`

## Code Style Guidelines

### Python Version & Dependencies
- **Python**: 3.13+ required
- **Package Manager**: uv preferred, pip fallback
- **Dependencies**: Use inline script dependencies in cli.py, maintain requirements.txt and pyproject.toml

### Imports & Structure
- Use absolute imports: `from cli import main`
- Group imports: standard library, third-party, local
- Use pathlib for file operations: `from pathlib import Path`
- USB imports: `import usb.core`, `import usb.util`

### Naming Conventions
- **Functions**: snake_case (e.g., `validate_file`, `connect_to_switch`)
- **Classes**: PascalCase (e.g., `ProgressManager`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `CMD_ID_EXIT`, `BUFFER_SEGMENT_DATA_SIZE`)
- **Variables**: snake_case (e.g., `file_list`, `debug_mode`)

### Error Handling
- Use try-except blocks for USB operations
- Log errors with level: `log(f"Error: {str(e)}", "ERROR")`
- Handle USBError specifically: `except usb.core.USBError as e:`
- Use graceful exit with global `should_exit` flag

### Type Hints
- Add type hints to function signatures
- Use Path objects for file paths: `file_path: Path`
- Return tuples for validation: `return True, None`

### Logging & Debug
- Use custom `log()` function with Rich formatting
- Support log levels: INFO, DEBUG, ERROR, WARNING
- Use global `debug_mode` flag for conditional debug output
- Color-code log levels using Rich styles

### Testing
- Use unittest framework
- Mock USB operations: `@patch('cli.usb.core.find')`
- Create temporary files for testing: `tempfile.mkdtemp()`
- Test validation logic separately from integration tests

### USB Protocol Constants
- Define protocol constants at module level
- Use descriptive names: `CMD_ID_FILE_RANGE`, `CMD_TYPE_RESPONSE`
- Include buffer size constants: `BUFFER_SEGMENT_DATA_SIZE = 0x100000`

### Progress Display
- Use Rich library for progress bars and formatting
- Create color-coded progress bars for multiple files
- Handle file completion tracking with sets
- Support progress cancellation with signal handlers