# DBI Backend CLI

A command-line tool for transferring files to Nintendo Switch via USB using the DBI protocol. This tool provides a simple and efficient way to transfer multiple files and directories with progress tracking and error handling.

## Features

- Transfer files and directories to Nintendo Switch
- Progress tracking with detailed transfer information
- File filtering by extension (e.g., NSP, XCI)
- Automatic retry on connection failures
- Debug mode for troubleshooting
- Clean exit handling with CTRL+C

## Prerequisites

- Python 3.13 or higher
- libusb (system dependency)
- Nintendo Switch with DBI installed

### System Dependencies

#### macOS
```bash
brew install libusb
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get install libusb-1.0-0-dev
```

#### Linux (Fedora)
```bash
sudo dnf install libusb-devel
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/dbibackend_cli.git
cd dbibackend_cli
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Basic usage:
```bash
python dbibackend.py file1.nsp file2.nsp
```

Transfer all NSP files from a directory:
```bash
python dbibackend.py /path/to/games --filter nsp
```

### Command Line Options

```
python dbibackend.py [files/folders] [options]

Arguments:
  files/folders          Files or directories to transfer

Options:
  --debug               Enable debug logging
  --filter EXT          Filter files by extension (e.g., "nsp,xci")
  --retry-count N       Number of connection retry attempts (default: 3)
  --timeout MS          USB timeout in milliseconds (default: 0)
```

### Examples

1. Transfer specific files:
```bash
python dbibackend.py game1.nsp game2.xci
```

2. Transfer all NSP files from multiple directories:
```bash
python dbibackend.py /games/switch /games/backup --filter nsp
```

3. Enable debug mode with custom retry count:
```bash
python dbibackend.py game.nsp --debug --retry-count 5
```

## Progress Display

The tool provides detailed progress information:

1. Overall Progress:
```
Overall Progress: 2/5 files (40.0%) [45s elapsed]
```

2. Current File Progress:
```
[2/5] game.nsp (45.2%) [1.5GB/4GB]: 100%|██████████| 1.5G/1.5G [00:30<00:00, 50.3MB/s]
```

## Troubleshooting

1. USB Connection Issues:
   - Ensure your Switch is properly connected via USB
   - Check that DBI is running on your Switch
   - Try a different USB port or cable
   - Run with --debug flag for detailed logs

2. Permission Issues:
   - On Linux, you might need to add udev rules for USB access
   - Try running with sudo if you encounter permission errors

3. Installation Issues:
   - Ensure libusb is properly installed
   - Check Python version (3.13+ required)
   - Verify all dependencies are installed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- DBI Project for the USB protocol implementation
- PyUSB developers for the USB communication library
- TQDM developers for the progress bar implementation
