# Experiment Examples

This directory contains example configuration files for SchedulingArena experiments.

## Quick Start

### 1. Quick Test (Fast)
```bash
# Run a quick test with fewer steps and users
./run_experiment.sh examples/quick_test.json
```

### 2. Full Example
```bash
# Run the full example with all schedulers
./run_experiment.sh examples/config_example.json
```

### 3. Save Results
```bash
# Run and save results to a directory
./run_experiment.sh examples/config_example.json --output results/
```

## Configuration Files

### `quick_test.json`
A minimal configuration for quick testing:
- 500 TTI steps (faster)
- 30 users, 50 RBs (smaller scale)
- Tests PF and Enhanced-PF schedulers

### `config_example.json`
A comprehensive example showing:
- Global environment parameters (`env` section)
- Multiple scheduler types (PF, M-LWDF, Enhanced-PF, B-M-LWDF)
- Scenario-specific environment overrides
- Agent configurations (PID controllers)

## Creating Your Own Config

1. Copy `config_example.json` as a template
2. Modify the `env` section for global parameters
3. Add/remove scenarios in the `scenarios` array
4. Each scenario can override global `env` parameters

Example structure:
```json
{
  "tti_steps": 1000,
  "env": {
    "num_users": 60,
    "num_rbs": 100,
    ...
  },
  "scenarios": [
    {
      "name": "My-Experiment",
      "scheduler": {
        "type": "PF"
      },
      "env": {
        "num_users": 120
      }
    }
  ]
}
```
