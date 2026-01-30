#!/usr/bin/env python
"""
Simple Python entry point for running SchedulingArena experiments.
Just pass a JSON config file as argument.

Usage:
    python run.py examples/config_example.json
    python run.py examples/quick_test.json
"""

import sys
import json
from schedulingArena.experiments import run_from_config


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <config.json>")
        print("\nExample:")
        print("  python run.py examples/config_example.json")
        print("  python run.py examples/quick_test.json")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        print(f"Running experiments from: {config_path}\n")
        run_from_config(config)
        
    except FileNotFoundError:
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error running experiments: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
