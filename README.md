# SchedulingArena

A unified experimental platform for wireless scheduling algorithms. This package provides a clean interface to run scheduling experiments with configurable environment parameters and scheduling algorithms.


## Installation

```bash
# Install in development mode
pip install -e .

# Or install normally
pip install .
```

## Quick Start

### 1. Using Python Script (Simplest - Recommended)

```bash
# Just run with a JSON config file
python run.py examples/quick_test.json
python run.py examples/config_example.json
```

### 2. Using Command Line Tool

```bash
# Run experiments from a config file (positional argument)
scheduling-arena examples/config_example.json

# Or use --config flag (legacy)
scheduling-arena --config examples/config_example.json

# Run default baseline experiments
scheduling-arena
```

### 3. Configuration File Format

Create a JSON config file to define your experiments:

```json
{
  "tti_steps": 1000,
  "env": {
    "num_users": 60,
    "num_rbs": 100,
    "tti_duration": 0.001,
    "scbr_bytes": 850,
    "tcbr_ms": 60,
    "pf_window_size": 100,
    "channel_mean_low_db": 10,
    "channel_mean_high_db": 20
  },
  "scenarios": [
    {
      "name": "Baseline-PF",
      "scheduler": {
        "type": "PF"
      }
    },
    {
      "name": "Baseline-MLWDF",
      "scheduler": {
        "type": "M-LWDF",
        "params": {
          "delta_u": 0.05,
          "tau_u": 0.1
        }
      }
    },
    {
      "name": "Heavy-Load-PF",
      "scheduler": {
        "type": "PF"
      },
      "env": {
        "num_users": 120,
        "tcbr_ms": 30
      }
    }
  ]
}
```

### 4. Environment Parameters

Global environment parameters (in `"env"` at top level) apply to all scenarios. Each scenario can override specific parameters in its own `"env"` section.

Available parameters:
- `num_users`: Number of users (default: 60)
- `num_rbs`: Number of resource blocks (default: 100)
- `tti_duration`: TTI duration in seconds (default: 0.001)
- `scbr_bytes`: SCBR packet size in bytes (default: 850)
- `tcbr_ms`: TCBR period in milliseconds (default: 60)
- `pf_window_size`: Proportional fair window size (default: 100)
- `channel_mean_low_db`: Lower bound of channel mean SNR in dB (default: 10)
- `channel_mean_high_db`: Upper bound of channel mean SNR in dB (default: 20)

### 5. Available Schedulers

- `"PF"`: Proportional Fair
- `"Ehanced-PF"`: Enhanced Proportional Fair (requires `tau_u` param)
- `"M-LWDF"`: Modified Largest Weighted Delay First (requires `delta_u`, `tau_u` params)
- `"B-M-LWDF"`: Beta-controlled M-LWDF (requires `delta_u`, `tau_u` params)
- `"LDF"`: Largest Delay First

### 6. Available Agents

- `"PID-constant"`: PID controller with constant gains
- `"PID-scheduled"`: PID controller with gain scheduling

## Architecture

The package is designed with clear separation of concerns:

- **Schedulers** (`scheduling_arena.scheduler`): Implement scheduling algorithms by inheriting from `BaseScheduler` and registering with `SchedulerRegistry`. Schedulers only depend on the `context` dictionary provided by the environment.

- **Environment** (`scheduling_arena.env`): Provides a Gym-compatible environment that simulates wireless scheduling scenarios. It accepts scheduler configuration and environment parameters.

- **Experiments** (`scheduling_arena.experiments`): Provides `ExperimentRunner` and `run_from_config()` to execute batch experiments from JSON configurations.

## Adding New Schedulers

To add a new scheduler:

1. Create a class inheriting from `BaseScheduler`
2. Implement the `schedule(context)` method
3. Register it with `@SchedulerRegistry.register("YourSchedulerName")`

Example:

```python
from schedulingArena.scheduler import BaseScheduler, SchedulerRegistry

@SchedulerRegistry.register("MyScheduler")
class MyScheduler(BaseScheduler):
    def schedule(self, context):
        potential_rates = context['potential_rates']
        # ... your scheduling logic ...
        return allocation  # numpy array of user indices per RB
```

## License

[Your License Here]

