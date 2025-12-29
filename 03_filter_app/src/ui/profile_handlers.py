"""
Profile management handlers for the filter application.

Contains functions for saving, loading, and managing user configuration profiles.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from tkinter import messagebox, simpledialog

logger = logging.getLogger(__name__)


def get_profiles_directory() -> Path:
    """Get or create the profiles directory."""
    profiles_dir = Path(__file__).parent.parent.parent / 'perfiles'
    profiles_dir.mkdir(exist_ok=True)
    return profiles_dir


def list_profiles() -> List[str]:
    """
    List all available profile names.
    
    Returns:
        List of profile filenames (without .json extension).
    """
    profiles_dir = get_profiles_directory()
    profiles = []
    
    for file in profiles_dir.glob('*.json'):
        profiles.append(file.stem)
    
    return sorted(profiles)


def save_profile(name: str, config: Dict[str, Any]) -> bool:
    """
    Save a configuration profile.
    
    Args:
        name: Profile name.
        config: Configuration dictionary to save.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        profiles_dir = get_profiles_directory()
        profile_path = profiles_dir / f'{name}.json'
        
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Profile saved: {name}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving profile {name}: {e}")
        return False


def load_profile(name: str) -> Optional[Dict[str, Any]]:
    """
    Load a configuration profile.
    
    Args:
        name: Profile name to load.
        
    Returns:
        Configuration dictionary or None if not found.
    """
    try:
        profiles_dir = get_profiles_directory()
        profile_path = profiles_dir / f'{name}.json'
        
        if not profile_path.exists():
            logger.warning(f"Profile not found: {name}")
            return None
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        logger.info(f"Profile loaded: {name}")
        return config
        
    except Exception as e:
        logger.error(f"Error loading profile {name}: {e}")
        return None


def delete_profile(name: str) -> bool:
    """
    Delete a configuration profile.
    
    Args:
        name: Profile name to delete.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        profiles_dir = get_profiles_directory()
        profile_path = profiles_dir / f'{name}.json'
        
        if profile_path.exists():
            profile_path.unlink()
            logger.info(f"Profile deleted: {name}")
            return True
        else:
            logger.warning(f"Profile not found: {name}")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting profile {name}: {e}")
        return False


def get_profile_config(
    provider: str,
    model: str,
    api_key: str,
    excel_path: str,
    sheet_name: str,
    start_index: int,
    end_index: int,
    output_path: str
) -> Dict[str, Any]:
    """
    Create a profile configuration dictionary.
    
    Args:
        provider: AI provider name.
        model: Model name.
        api_key: API key (will be partially masked).
        excel_path: Path to input Excel file.
        sheet_name: Name of the sheet to process.
        start_index: Starting row index.
        end_index: Ending row index.
        output_path: Path for output file.
        
    Returns:
        Configuration dictionary.
    """
    return {
        'provider': provider,
        'model': model,
        'api_key_preview': api_key[:20] + '...' if api_key else '',
        'excel_path': excel_path,
        'sheet_name': sheet_name,
        'start_index': start_index,
        'end_index': end_index,
        'output_path': output_path
    }
