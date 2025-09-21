#!/usr/bin/env python3
"""
Browser-use Error Investigation and Fix Script (Minimal Version)

Usage: python minimal_fix.py <task_data_file>

This script reads task data from a file, combines it with a prompt template,
and runs Claude to investigate and fix browser-use errors.
"""

import sys
import subprocess
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("Usage: python minimal_fix.py <task_data_file>")
        sys.exit(1)
    
    # Read task data from input file
    task_data_file = Path(sys.argv[1])
    if not task_data_file.exists():
        print(f"Error: File '{task_data_file}' not found")
        sys.exit(1)
    
    task_data = task_data_file.read_text(encoding='utf-8')
    
    script_dir = Path(__file__).parent
    prompt_template_file = script_dir / "prompt_template.txt"
    prompt_template = prompt_template_file.read_text(encoding='utf-8')
    formatted_prompt = prompt_template.replace("{task_data}", task_data)
    
    print(f"Running Claude with task data from: {task_data_file}")
    try:
        subprocess.run(["claude", "--permission-mode", "plan", formatted_prompt], check=True)
        print("Claude plan completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error running Claude: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'claude' command not found. Please ensure Claude CLI is installed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
