#!/usr/bin/env python
"""
Command-line interface for SchedulingArena.
"""
import argparse
import json
import sys
from .experiments import run_from_config, ExperimentRunner
from .agents import PIDBetaController


def main():
    """
    命令行入口：
      scheduling-arena --config path/to/config.json
    """
    parser = argparse.ArgumentParser(
        description="SchedulingArena: Unified experimental platform for wireless scheduling algorithms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run experiments from config file
  scheduling-arena --config examples/config_example.json
  
  # Run with default baseline experiments
  scheduling-arena
        """
    )
    parser.add_argument(
        "config",
        nargs="?",
        type=str,
        help="Path to JSON config file defining experiments.",
    )
    parser.add_argument(
        "--config",
        dest="config_legacy",
        type=str,
        help="[Deprecated] Use positional argument instead. Path to JSON config file.",
    )
    args = parser.parse_args()
    
    # Support both --config and positional argument
    config_file = args.config or args.config_legacy

    if config_file:
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            run_from_config(config)
        except FileNotFoundError:
            print(f"Error: Config file not found: {config_file}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error running experiments: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 默认运行内置的 baseline 实验
        runner = ExperimentRunner(tti_steps=1000)
        
        # 1. Baseline: Proportional Fair
        runner.run_scenario("Baseline-PF", {"type": "PF"})
        
        # 2. Baseline: M-LWDF
        runner.run_scenario("Baseline-MLWDF", {"type": "M-LWDF", "params": {"delta_u": 0.05, "tau_u": 0.1}})
        
        # 3. 按钮 1: PID (Constant Gain)
        pid_constant = PIDBetaController.create_constant(kp=0.6, ki=0.01, kd=0.1)
        runner.run_scenario(
            name="Proposed-PID-Constant", 
            scheduler_config={"type": "B-M-LWDF"}, 
            agent_policy=pid_constant
        )
        
        # 4. 按钮 2: PID (Gain Scheduling)
        pid_scheduled = PIDBetaController.create_scheduled(base_kp=0.6, base_ki=0.01, base_kd=0.1)
        runner.run_scenario(
            name="Proposed-PID-Scheduled", 
            scheduler_config={"type": "B-M-LWDF"}, 
            agent_policy=pid_scheduled
        )
        
        runner.print_summary()


if __name__ == "__main__":
    main()
