import numpy as np
import time
import json

from .env import WirelessSchedulingEnv
from .agents import PIDBetaController


class ExperimentRunner:
    def __init__(self, tti_steps=1000, base_env_params=None, base_wireless_env_config=None):
        self.tti_steps = tti_steps
        self.results = {}
        # 可以在配置里给一个全局 env 参数作为默认
        self.base_env_params = base_env_params or {}
        # 全局无线环境配置
        self.base_wireless_env_config = base_wireless_env_config or {}

    def run_scenario(self, name, scheduler_config, env_params=None, agent_policy=None, wireless_env_config=None):
        print(f"--- Running Experiment: {name} ---")

        # 合并全局和场景内的 env 参数（场景内优先）
        merged_env_params = dict(self.base_env_params)
        if env_params:
            merged_env_params.update(env_params)

        # 合并全局和场景内的无线环境配置（场景内优先）
        merged_wireless_env_config = dict(self.base_wireless_env_config)
        if wireless_env_config:
            # 如果场景配置中有 params，需要合并
            if "params" in wireless_env_config and "params" in merged_wireless_env_config:
                merged_params = dict(merged_wireless_env_config.get("params", {}))
                merged_params.update(wireless_env_config.get("params", {}))
                merged_wireless_env_config["params"] = merged_params
                merged_wireless_env_config.update({k: v for k, v in wireless_env_config.items() if k != "params"})
            else:
                merged_wireless_env_config.update(wireless_env_config)

        env = WirelessSchedulingEnv(
            scheduler_config=scheduler_config,
            env_params=merged_env_params,
            wireless_env_config=merged_wireless_env_config if merged_wireless_env_config else None,
        )
        obs = env.reset()
        
        # Metrics storage
        delays_history = []
        fairness_history = []
        beta_history = []
        throughput_history = []
        
        start_time = time.time()
        info = {}
        
        # 重置 Agent 状态 (如果是对象)
        if hasattr(agent_policy, 'reset'):
            agent_policy.reset()

        for _ in range(self.tti_steps):
            if agent_policy:
                if hasattr(agent_policy, 'get_action'):
                    action = agent_policy.get_action(obs, info)
                else:
                    action = agent_policy(obs)
            else:
                action = 0 
                
            obs, reward, done, info = env.step(action)
            
            delays_history.append(info['avg_delay'])
            fairness_history.append(info['fairness_case'])
            beta_history.append(info['beta'])
            throughput_history.append(info['total_throughput'])
            
        elapsed = time.time() - start_time
        
        avg_delay = np.mean(delays_history)
        avg_throughput = np.mean(throughput_history)
        ff_percent = fairness_history.count("FF") / len(fairness_history) * 100
        
        self.results[name] = {
            "avg_delay_ms": avg_delay * 1000,
            "avg_throughput_mbps": avg_throughput / 1e6,
            "ff_percentage": ff_percent,
            "final_beta": beta_history[-1],
            "elapsed_time": elapsed
        }
        
        print(f"Done. Avg Delay: {avg_delay*1000:.2f}ms, FF Time: {ff_percent:.1f}%")
        print("-" * 30)

    def print_summary(self):
        print("\n=== Experiment Summary ===")
        header = f"{'Experiment':<28} | {'Avg Delay (ms)':<15} | {'Tp (Mbps)':<10} | {'FF Time (%)':<12} | {'Time (s)':<10}"
        print(header)
        print("-" * len(header))
        for name, res in self.results.items():
            print(f"{name:<28} | {res['avg_delay_ms']:<15.2f} | {res['avg_throughput_mbps']:<10.2f} | {res['ff_percentage']:<12.1f} | {res['elapsed_time']:<10.2f}")


def _create_agent_from_config(agent_cfg):
    """
    从配置创建 Agent。
    目前支持:
      - type: "PID-constant"  -> PIDBetaController.create_constant(**params)
      - type: "PID-scheduled" -> PIDBetaController.create_scheduled(**params)
    """
    if agent_cfg is None:
        return None

    agent_type = agent_cfg.get("type")
    params = agent_cfg.get("params", {})

    if agent_type == "PID-constant":
        return PIDBetaController.create_constant(**params)
    elif agent_type == "PID-scheduled":
        return PIDBetaController.create_scheduled(**params)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


def run_from_config(config: dict):
    """
    统一实验入口：根据配置文件批量跑实验。

    config 示例（JSON）:
    {
      "tti_steps": 1000,
      "env": {
        "num_users": 60,
        "num_rbs": 100,
        ...
      },
      "scenarios": [
        {
          "name": "Baseline-PF",
          "scheduler": { "type": "PF" }
        },
        ...
      ]
    }
    """
    tti_steps = config.get("tti_steps", 1000)
    base_env_params = config.get("env", {})
    base_wireless_env_config = config.get("wireless_env")
    runner = ExperimentRunner(
        tti_steps=tti_steps, 
        base_env_params=base_env_params,
        base_wireless_env_config=base_wireless_env_config
    )

    scenarios = config.get("scenarios", [])
    if not scenarios:
        raise ValueError("Config must contain non-empty 'scenarios' list.")

    for sc in scenarios:
        name = sc["name"]
        scheduler_cfg = sc["scheduler"]
        env_params = sc.get("env")
        agent_cfg = sc.get("agent")
        wireless_env_cfg = sc.get("wireless_env")
        agent_policy = _create_agent_from_config(agent_cfg) if agent_cfg else None
        runner.run_scenario(name, scheduler_cfg, env_params, agent_policy, wireless_env_cfg)

    runner.print_summary()
