#!/usr/bin/python3

"""
DBI Backend CLI - Nintendo Switch USB File Transfer Tool

This script provides a command-line interface for transferring files to a Nintendo Switch
using the DBI (DevkitPro Binutils Interface) protocol. It supports transferring multiple
files and directories, with progress tracking and error handling.

Usage:
    python dbibackend.py [files/folders] [options]
    
Options:
    --debug          Enable debug logging
    --filter         Filter files by extension (e.g., "nsp,xci")
    --retry-count    Number of connection retry attempts (default: 3)
    --timeout        USB timeout in milliseconds (default: 0)
"""

# This script can be run without activate virtual env : uv run dbibackend.py
# This script has inline dependencies, it will ignore the project toml file

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     # Core USB communication
#     "pyusb>=1.2.1",           # USB communication with the Switch
#     "libusb>=1.0.26b5",       # Required by pyusb for USB access
#     
#     # CLI and Progress Bar
#     "tqdm>=4.66.1",           # Progress bars for file transfers
#     "argparse>=1.4.0",        # Command line argument parsing
#     
#     # Utility
#     "six>=1.16.0",            # Python 2/3 compatibility (required by pyusb)
#     "pathlib>=1.0.1",         # Path manipulation (included in Python 3.4+)
#     
#     # Optional but recommended
#     "colorama>=0.4.6",        # Cross-platform colored terminal output
# ]
# ///

import usb.core
import usb.util
import struct
import sys
import time
import threading
import signal
import argparse
from tqdm import tqdm
from binascii import hexlify as hx, unhexlify as uhx
from pathlib import Path

# DBI Protocol Command IDs
CMD_ID_EXIT = 0          # Command to exit the connection
CMD_ID_LIST_OLD = 1      # Legacy list command (deprecated)
CMD_ID_FILE_RANGE = 2    # Command for file data transfer
CMD_ID_LIST = 3          # Command to list available files

# DBI Protocol Command Types
CMD_TYPE_REQUEST = 0     # Request from Switch to PC
CMD_TYPE_RESPONSE = 1    # Response from PC to Switch
CMD_TYPE_ACK = 2         # Acknowledgment message

# Buffer size for file transfers (1MB)
BUFFER_SEGMENT_DATA_SIZE = 0x100000

# Global variables for USB endpoints and state
in_ep = None            # USB IN endpoint (Switch -> PC)
out_ep = None           # USB OUT endpoint (PC -> Switch)
debug_mode = False      # Debug mode flag
file_list = {}          # Dictionary of files to transfer {filename: path}
should_exit = False     # Flag for graceful exit
total_files_transferred = 0
transfer_start_time = None
file_progress_bars = {}  # Dictionary to store progress bars for each file

def signal_handler(signum, frame):
    """Handle system signals (SIGINT, SIGTERM) for graceful exit."""
    global should_exit
    print("\nReceived signal to exit. Cleaning up...")
    should_exit = True

# Register signal handlers for graceful exit
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def log(line, level="INFO"):
    """
    Log messages with different severity levels.
    
    Args:
        line (str): Message to log
        level (str): Log level (INFO, DEBUG, ERROR, WARNING)
    """
    if level == "DEBUG" and not debug_mode:
        return
    print(f"[{level}] {line}")

def format_size(size):
    """Format size in bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PB"

def process_file_range_command(data_size):
    """
    Process a file range transfer request from the Switch.
    Handles the transfer of a specific portion of a file.
    """
    global file_list, should_exit, total_files_transferred, transfer_start_time, file_progress_bars

    if transfer_start_time is None:
        transfer_start_time = time.time()

    log('Processing file range request', "DEBUG")
    out_ep.write(struct.pack('<4sIII', b'DBI0', CMD_TYPE_ACK, CMD_ID_FILE_RANGE, data_size))

    file_range_header = in_ep.read(data_size)
    range_size = struct.unpack('<I', file_range_header[:4])[0]
    range_offset = struct.unpack('<Q', file_range_header[4:12])[0]
    nsp_name_len = struct.unpack('<I', file_range_header[12:16])[0]
    nsp_name = bytes(file_range_header[16:]).decode('utf-8')

    log(f'Range Size: {range_size}, Range Offset: {range_offset}, Name len: {nsp_name_len}', "DEBUG")

    response_bytes = struct.pack('<4sIII', b'DBI0', CMD_TYPE_RESPONSE, CMD_ID_FILE_RANGE, range_size)
    out_ep.write(response_bytes)

    ack = bytes(in_ep.read(16, timeout=0))
    magic = ack[:4]
    cmd_type = struct.unpack('<I', ack[4:8])[0]
    cmd_id = struct.unpack('<I', ack[8:12])[0]
    data_size = struct.unpack('<I', ack[12:16])[0]

    with open(file_list[nsp_name].__str__(), 'rb') as f:
        # Get file size information
        total_size = f.seek(0, 2)
        f.seek(range_offset)
        
        curr_off = 0x0
        end_off = range_size
        read_size = BUFFER_SEGMENT_DATA_SIZE

        # Create or get existing progress bar
        if nsp_name not in file_progress_bars:
            progress_desc = f"[{total_files_transferred + 1}/{len(file_list)}] {nsp_name}"
            file_progress_bars[nsp_name] = tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                desc=progress_desc,
                ncols=100,
                initial=range_offset
            )
            
            # Show overall progress for multiple files
            if len(file_list) > 1:
                elapsed_time = time.time() - transfer_start_time
                overall_desc = (
                    f"Overall Progress: {total_files_transferred}/{len(file_list)} files "
                    f"({total_files_transferred/len(file_list)*100:.1f}%) "
                    f"[{elapsed_time:.0f}s elapsed]"
                )
                print(overall_desc)

        pbar = file_progress_bars[nsp_name]
        
        while curr_off < end_off and not should_exit:
            if curr_off + read_size >= end_off:
                read_size = end_off - curr_off
            buf = f.read(read_size)
            out_ep.write(data=buf, timeout=0)
            curr_off += read_size
            pbar.update(read_size)

        # Close and remove progress bar if file is complete
        if range_offset + range_size >= total_size:
            pbar.close()
            del file_progress_bars[nsp_name]
            total_files_transferred += 1

def poll_commands():
    """
    Main command polling loop.
    Continuously listens for commands from the Switch and processes them.
    Handles file transfers, list requests, and exit commands.
    """
    log('Entering command loop')
    global should_exit
    
    while not should_exit:
        try:
            # Read command header from Switch
            cmd_header = bytes(in_ep.read(16, timeout=0))
            magic = cmd_header[:4]

            if magic != b'DBI0':
                continue

            # Parse command header
            cmd_type = struct.unpack('<I', cmd_header[4:8])[0]
            cmd_id = struct.unpack('<I', cmd_header[8:12])[0]
            data_size = struct.unpack('<I', cmd_header[12:16])[0]

            log(f'Received command - Type: {cmd_type}, ID: {cmd_id}, Size: {data_size}', "DEBUG")

            # Process different command types
            if cmd_id == CMD_ID_EXIT:
                process_exit_command()
            elif cmd_id == CMD_ID_FILE_RANGE:
                process_file_range_command(data_size)
            elif cmd_id == CMD_ID_LIST:
                process_list_command()
        except usb.core.USBError as e:
            log(f'Switch connection lost: {str(e)}', "ERROR")
            if not should_exit:
                connect_to_switch()
        except Exception as e:
            log(f'Unexpected error: {str(e)}', "ERROR")
            if debug_mode:
                raise
            should_exit = True

def process_exit_command():
    """Handle exit command from Switch by sending acknowledgment and setting exit flag."""
    log('Received exit command')
    out_ep.write(struct.pack('<4sIII', b'DBI0', CMD_TYPE_RESPONSE, CMD_ID_EXIT, 0))
    global should_exit
    should_exit = True

def process_list_command():
    """
    Process list command from Switch.
    Sends the list of available files to the Switch.
    """
    global file_list
    log('Processing file list request', "DEBUG")
    nsp_path_list = ""
    nsp_path_list_len = 0

    # Build list of files
    for i, (k, v) in enumerate(sorted(file_list.items())):
        nsp_path_list += k + '\n'
        log(f'Listed file: {k}', "DEBUG")

    nsp_path_list_bytes = nsp_path_list.encode('utf-8')
    nsp_path_list_len = len(nsp_path_list_bytes)

    # Send response header
    out_ep.write(struct.pack('<4sIII', b'DBI0', CMD_TYPE_RESPONSE, CMD_ID_LIST, nsp_path_list_len))

    if nsp_path_list_len > 0:
        # Wait for acknowledgment
        ack = bytes(in_ep.read(16, timeout=0))
        magic = ack[:4]
        cmd_type = struct.unpack('<I', ack[4:8])[0]
        cmd_id = struct.unpack('<I', ack[8:12])[0]
        data_size = struct.unpack('<I', ack[12:16])[0]

        # Send file list
        out_ep.write(nsp_path_list_bytes)

def connect_to_switch():
    """
    Establish USB connection with the Nintendo Switch.
    Handles device detection, configuration, and endpoint setup.
    Retries connection until successful or interrupted.
    """
    global in_ep, out_ep, should_exit
    
    while not should_exit:
        try:
            # Find Switch USB device
            dev = usb.core.find(idVendor=0x057E, idProduct=0x3000)
            if dev is None:
                log('Waiting for switch...', "DEBUG")
                time.sleep(1)
                continue

            # Reset and configure device
            dev.reset()
            log('Switch detected, resetting connection...', "DEBUG")
            time.sleep(1)
            
            try:
                dev.set_configuration()
            except usb.core.USBError as e:
                log(f"Failed to set configuration: {str(e)}", "ERROR")
                continue

            cfg = dev.get_active_configuration()

            # Find USB endpoints
            is_out_ep = lambda ep: usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT
            is_in_ep = lambda ep: usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN
            
            out_ep = usb.util.find_descriptor(cfg[(0,0)], custom_match=is_out_ep)
            in_ep = usb.util.find_descriptor(cfg[(0,0)], custom_match=is_in_ep)

            if out_ep is None or in_ep is None:
                log("Failed to find USB endpoints", "ERROR")
                continue

            log('Successfully connected to Switch')
            break
            
        except usb.core.USBError as e:
            log(f"USB Error during connection: {str(e)}", "ERROR")
            time.sleep(1)
        except Exception as e:
            log(f"Unexpected error during connection: {str(e)}", "ERROR")
            if debug_mode:
                raise
            time.sleep(1)

def validate_file(file_path):
    """
    Validate if a file is suitable for transfer.
    
    Args:
        file_path (Path): Path to the file to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        if not file_path.exists():
            return False, "File does not exist"
        if not file_path.is_file():
            return False, "Not a file"
        if file_path.stat().st_size == 0:
            return False, "File is empty"
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    """
    Main entry point for the DBI Backend CLI tool.
    Handles argument parsing, file validation, and initiates the transfer process.
    """
    global debug_mode, file_list

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='DBI Backend CLI - Nintendo Switch USB File Transfer Tool')
    parser.add_argument('paths', nargs='+', help='Files or directories to transfer')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--filter', type=str, help='Filter files by extension (e.g., "nsp,xci")')
    parser.add_argument('--retry-count', type=int, default=3, help='Number of connection retry attempts')
    parser.add_argument('--timeout', type=int, default=0, help='USB timeout in milliseconds (0 for no timeout)')
    
    args = parser.parse_args()
    debug_mode = args.debug
    allowed_extensions = set(args.filter.lower().split(',')) if args.filter else None

    log("Starting DBI Backend CLI")
    if debug_mode:
        log("Debug mode enabled", "DEBUG")

    # Process input paths and validate files
    for path_str in args.paths:
        path = Path(path_str)
        if path.is_file():
            if allowed_extensions and path.suffix.lower()[1:] not in allowed_extensions:
                log(f"Skipping {path.name} - extension not in filter", "DEBUG")
                continue
                
            is_valid, error = validate_file(path)
            if is_valid:
                file_list[path.name] = path.resolve()
                log(f"Added file: {path.name}")
            else:
                log(f"Skipping {path.name} - {error}", "WARNING")
                
        elif path.is_dir():
            for file_path in path.rglob('*'):
                if not file_path.is_file():
                    continue
                    
                if allowed_extensions and file_path.suffix.lower()[1:] not in allowed_extensions:
                    log(f"Skipping {file_path.name} - extension not in filter", "DEBUG")
                    continue
                    
                is_valid, error = validate_file(file_path)
                if is_valid:
                    file_list[file_path.name] = file_path.resolve()
                    log(f"Added file from directory: {file_path.name}")
                else:
                    log(f"Skipping {file_path.name} - {error}", "WARNING")
        else:
            log(f"Warning: {path_str} is not a valid file or directory", "WARNING")

    if not file_list:
        log("No valid files found to transfer", "ERROR")
        sys.exit(1)

    log(f"Found {len(file_list)} files to transfer")
    
    # Start transfer process with retry mechanism
    retry_count = args.retry_count
    while retry_count > 0 and not should_exit:
        try:
            connect_to_switch()
            poll_commands()
            break
        except Exception as e:
            retry_count -= 1
            if retry_count > 0 and not should_exit:
                log(f"Error occurred: {str(e)}, retrying... ({retry_count} attempts left)", "ERROR")
                time.sleep(2)
            else:
                log(f"Failed to complete transfer: {str(e)}", "ERROR")
                sys.exit(1)

    if should_exit:
        log("Transfer interrupted by user")
    else:
        log("Transfer completed successfully")

if __name__ == "__main__":
    main()