#!/usr/bin/env python3
"""
File I/O Utilities - consolidates identical file I/O patterns with different error messages.

This module provides:
- Unified file operations with consistent error handling
- Cache file operations with automatic JSON serialization
- Timestamp file operations with text I/O
- State file operations with JSON persistence
- Directory management utilities
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from .error_handlers import handle_file_io_errors, handle_json_errors


class FileIOManager:
    """Base file I/O manager with consistent error handling patterns."""
    
    def __init__(self, base_directory: str = ""):
        """Initialize with optional base directory."""
        self.base_directory = Path(base_directory) if base_directory else Path.cwd()
        self.ensure_directory_exists(self.base_directory)
    
    def ensure_directory_exists(self, directory: Union[str, Path]) -> None:
        """Ensure directory exists, creating it if necessary."""
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_file_path(self, filename: str) -> Path:
        """Get full file path relative to base directory."""
        return self.base_directory / filename
    
    @handle_file_io_errors("read text file", context="")
    def read_text_file(self, filename: str, encoding: str = "utf-8") -> Optional[str]:
        """
        Read text content from file with error handling.
        
        Args:
            filename: Name of file to read
            encoding: Text encoding (default: utf-8)
            
        Returns:
            str: File content or None if error
        """
        file_path = self.get_file_path(filename)
        if file_path.exists():
            with open(file_path, "r", encoding=encoding) as f:
                return f.read().strip()
        return None
    
    @handle_file_io_errors("write text file", context="")
    def write_text_file(self, filename: str, content: str, encoding: str = "utf-8") -> bool:
        """
        Write text content to file with error handling.
        
        Args:
            filename: Name of file to write
            content: Text content to write
            encoding: Text encoding (default: utf-8)
            
        Returns:
            bool: True if successful, False if error
        """
        file_path = self.get_file_path(filename)
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        return True
    
    @handle_file_io_errors("read JSON file", context="")
    @handle_json_errors("parse JSON", default_return=None)
    def read_json_file(self, filename: str, encoding: str = "utf-8") -> Optional[Dict[str, Any]]:
        """
        Read and parse JSON file with error handling.
        
        Args:
            filename: Name of JSON file to read
            encoding: Text encoding (default: utf-8)
            
        Returns:
            dict: Parsed JSON data or None if error
        """
        file_path = self.get_file_path(filename)
        if file_path.exists():
            with open(file_path, "r", encoding=encoding) as f:
                return json.load(f)
        return None
    
    @handle_file_io_errors("write JSON file", context="")
    def write_json_file(self, filename: str, data: Any, encoding: str = "utf-8", 
                       indent: int = 2) -> bool:
        """
        Write data to JSON file with error handling.
        
        Args:
            filename: Name of JSON file to write
            data: Data to serialize as JSON
            encoding: Text encoding (default: utf-8)
            indent: JSON indentation (default: 2)
            
        Returns:
            bool: True if successful, False if error
        """
        file_path = self.get_file_path(filename)
        with open(file_path, "w", encoding=encoding) as f:
            json.dump(data, f, indent=indent)
        return True
    
    def file_exists(self, filename: str) -> bool:
        """Check if file exists."""
        return self.get_file_path(filename).exists()
    
    def delete_file(self, filename: str) -> bool:
        """Delete file if it exists."""
        file_path = self.get_file_path(filename)
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except OSError:
                return False
        return True


class CacheManager(FileIOManager):
    """Cache file operations with automatic JSON serialization."""
    
    def __init__(self, cache_directory: str):
        """Initialize with cache directory."""
        super().__init__(cache_directory)
    
    def save_cache(self, cache_key: str, data: Any) -> bool:
        """
        Save data to cache file.
        
        Args:
            cache_key: Cache identifier (e.g., 'onionoo_details')
            data: Data to cache (will be JSON serialized)
            
        Returns:
            bool: True if successful, False if error
        """
        cache_filename = f"{cache_key}.json"
        return self.write_json_file(cache_filename, data)
    
    def load_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Load data from cache file.
        
        Args:
            cache_key: Cache identifier (e.g., 'onionoo_details')
            
        Returns:
            dict: Cached data or None if not available
        """
        cache_filename = f"{cache_key}.json"
        return self.read_json_file(cache_filename)
    
    def cache_exists(self, cache_key: str) -> bool:
        """Check if cache file exists."""
        cache_filename = f"{cache_key}.json"
        return self.file_exists(cache_filename)
    
    def delete_cache(self, cache_key: str) -> bool:
        """Delete cache file."""
        cache_filename = f"{cache_key}.json"
        return self.delete_file(cache_filename)
    
    def get_cache_age(self, cache_key: str) -> Optional[float]:
        """
        Get cache file age in seconds.
        
        Returns:
            float: Age in seconds or None if file doesn't exist
        """
        cache_filename = f"{cache_key}.json"
        file_path = self.get_file_path(cache_filename)
        
        if file_path.exists():
            return time.time() - file_path.stat().st_mtime
        return None


class TimestampManager(FileIOManager):
    """Timestamp file operations for conditional requests."""
    
    def __init__(self, timestamp_directory: str):
        """Initialize with timestamp directory."""
        super().__init__(timestamp_directory)
    
    def write_timestamp(self, api_name: str, timestamp_str: str) -> bool:
        """
        Store timestamp for conditional requests.
        
        Args:
            api_name: Name of the API
            timestamp_str: Formatted timestamp string
            
        Returns:
            bool: True if successful, False if error
        """
        timestamp_filename = f"{api_name}_timestamp.txt"
        return self.write_text_file(timestamp_filename, timestamp_str)
    
    def read_timestamp(self, api_name: str) -> Optional[str]:
        """
        Read stored timestamp for conditional requests.
        
        Args:
            api_name: Name of the API
            
        Returns:
            str: Timestamp string or None if not available
        """
        timestamp_filename = f"{api_name}_timestamp.txt"
        return self.read_text_file(timestamp_filename)
    
    def timestamp_exists(self, api_name: str) -> bool:
        """Check if timestamp file exists."""
        timestamp_filename = f"{api_name}_timestamp.txt"
        return self.file_exists(timestamp_filename)
    
    def delete_timestamp(self, api_name: str) -> bool:
        """Delete timestamp file."""
        timestamp_filename = f"{api_name}_timestamp.txt"
        return self.delete_file(timestamp_filename)


class StateManager(FileIOManager):
    """State file operations with JSON persistence."""
    
    def __init__(self, state_file_path: str):
        """Initialize with state file path."""
        self.state_file_path = Path(state_file_path)
        super().__init__(self.state_file_path.parent)
        self.state_filename = self.state_file_path.name
    
    def save_state(self, state_data: Dict[str, Any]) -> bool:
        """
        Save state data to file.
        
        Args:
            state_data: State dictionary to save
            
        Returns:
            bool: True if successful, False if error
        """
        return self.write_json_file(self.state_filename, state_data)
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """
        Load state data from file.
        
        Returns:
            dict: State data or None if not available
        """
        return self.read_json_file(self.state_filename)
    
    def state_exists(self) -> bool:
        """Check if state file exists."""
        return self.file_exists(self.state_filename)
    
    def update_state(self, updates: Dict[str, Any]) -> bool:
        """
        Update state file with new data.
        
        Args:
            updates: Dictionary of updates to apply
            
        Returns:
            bool: True if successful, False if error
        """
        current_state = self.load_state() or {}
        current_state.update(updates)
        return self.save_state(current_state)


class TestFileHelper:
    """Helper utilities for creating test files and directories."""
    
    @staticmethod
    def create_temp_directory() -> tempfile.TemporaryDirectory:
        """Create temporary directory for testing."""
        return tempfile.TemporaryDirectory()
    
    @staticmethod
    def create_test_json_file(directory: str, filename: str, data: Dict[str, Any]) -> str:
        """
        Create a test JSON file with specified data.
        
        Args:
            directory: Directory to create file in
            filename: Name of file to create
            data: JSON data to write
            
        Returns:
            str: Full path to created file
        """
        file_path = os.path.join(directory, filename)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return file_path
    
    @staticmethod
    def create_corrupted_json_file(directory: str, filename: str, 
                                  content: str = '{"invalid": json}') -> str:
        """
        Create a corrupted JSON file for error testing.
        
        Args:
            directory: Directory to create file in
            filename: Name of file to create
            content: Invalid JSON content
            
        Returns:
            str: Full path to created file
        """
        file_path = os.path.join(directory, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return file_path
    
    @staticmethod
    def create_test_cache_structure(base_dir: str) -> Dict[str, str]:
        """
        Create standard test cache directory structure.
        
        Args:
            base_dir: Base directory for cache structure
            
        Returns:
            dict: Dictionary of created directory paths
        """
        cache_dir = os.path.join(base_dir, "cache")
        data_dir = base_dir
        
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        
        return {
            'cache_dir': cache_dir,
            'data_dir': data_dir,
            'state_file': os.path.join(data_dir, 'state.json')
        }


class BulkFileOperations:
    """Bulk file operations for common patterns."""
    
    def __init__(self, base_directory: str):
        """Initialize with base directory."""
        self.base_directory = Path(base_directory)
        self.file_manager = FileIOManager(base_directory)
    
    def copy_files_with_pattern(self, pattern: str, destination: str) -> List[str]:
        """
        Copy files matching pattern to destination.
        
        Args:
            pattern: File pattern to match (glob-style)
            destination: Destination directory
            
        Returns:
            List[str]: List of copied file paths
        """
        import shutil
        
        copied_files = []
        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        for file_path in self.base_directory.glob(pattern):
            if file_path.is_file():
                dest_file = dest_path / file_path.name
                shutil.copy2(file_path, dest_file)
                copied_files.append(str(dest_file))
        
        return copied_files
    
    def delete_files_with_pattern(self, pattern: str) -> List[str]:
        """
        Delete files matching pattern.
        
        Args:
            pattern: File pattern to match (glob-style)
            
        Returns:
            List[str]: List of deleted file paths
        """
        deleted_files = []
        
        for file_path in self.base_directory.glob(pattern):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    deleted_files.append(str(file_path))
                except OSError:
                    continue
        
        return deleted_files
    
    def get_files_by_age(self, max_age_seconds: float) -> List[str]:
        """
        Get files older than specified age.
        
        Args:
            max_age_seconds: Maximum age in seconds
            
        Returns:
            List[str]: List of old file paths
        """
        current_time = time.time()
        old_files = []
        
        for file_path in self.base_directory.rglob("*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    old_files.append(str(file_path))
        
        return old_files


# Convenience functions for backward compatibility
def create_cache_manager(cache_directory: str) -> CacheManager:
    """Create a new cache manager instance."""
    return CacheManager(cache_directory)


def create_timestamp_manager(timestamp_directory: str) -> TimestampManager:
    """Create a new timestamp manager instance."""
    return TimestampManager(timestamp_directory)


def create_state_manager(state_file_path: str) -> StateManager:
    """Create a new state manager instance."""
    return StateManager(state_file_path)


def create_test_helper() -> TestFileHelper:
    """Create a new test file helper instance."""
    return TestFileHelper()


# Factory function for unified file I/O operations
def create_unified_file_manager(base_directory: str, 
                               cache_subdir: str = "cache",
                               state_filename: str = "state.json") -> Dict[str, Any]:
    """
    Create unified file managers for common use cases.
    
    Args:
        base_directory: Base directory for all operations
        cache_subdir: Subdirectory for cache files
        state_filename: Name of state file
        
    Returns:
        dict: Dictionary containing all manager instances
    """
    base_path = Path(base_directory)
    cache_path = base_path / cache_subdir
    state_path = base_path / state_filename
    
    return {
        'file_manager': FileIOManager(str(base_path)),
        'cache_manager': CacheManager(str(cache_path)),
        'timestamp_manager': TimestampManager(str(cache_path)),
        'state_manager': StateManager(str(state_path)),
        'bulk_operations': BulkFileOperations(str(base_path)),
        'test_helper': TestFileHelper()
    }