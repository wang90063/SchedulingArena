import gym
from gym import spaces
import numpy as np
from .scheduler import SchedulerRegistry, BaseScheduler
from .utils import FairnessCalculator
from .wireless_env import WirelessEnvRegistry

class WirelessSchedulingEnv(gym.Env):
    """
    基于配置的 5G 调度环境。
    支持动态切换调度算法和环境参数。
    """
    
    def __init__(self, scheduler_config=None, env_params=None, wireless_env_config=None):
        super(WirelessSchedulingEnv, self).__init__()
        
        # --- 调度器配置加载 ---
        if scheduler_config is None:
            scheduler_config = {"type": "B-M-LWDF"}
            
        self.scheduler_type = scheduler_config.get("type", "B-M-LWDF")
        scheduler_params = scheduler_config.get("params", {})
        
        # 使用注册表工厂创建调度器实例
        self.scheduler = SchedulerRegistry.make(self.scheduler_type, **scheduler_params)
        
        # --- 系统参数 (Table I) ---
        # 允许通过 env_params 覆盖默认值
        if env_params is None:
            env_params = {}
        
        self.num_rbs = env_params.get("num_rbs", 100)
        self.num_users = env_params.get("num_users", 60)
        self.tti_duration = env_params.get("tti_duration", 1e-3)
        self.scbr_bytes = env_params.get("scbr_bytes", 850)
        self.tcbr_ms = env_params.get("tcbr_ms", 60)
        self.tcbr_ttis = int(self.tcbr_ms)
        self.pf_window_size = env_params.get("pf_window_size", 100)
        
        # --- 无线环境配置加载 ---
        if wireless_env_config is None:
            wireless_env_config = {"type": "SimpleRayleigh"}
        
        wireless_env_type = wireless_env_config.get("type", "SimpleRayleigh")
        wireless_env_params = wireless_env_config.get("params", {})
        
        # 从 env_params 中提取无线环境相关参数（向后兼容）
        if "channel_mean_low_db" in env_params:
            wireless_env_params.setdefault("channel_mean_low_db", env_params["channel_mean_low_db"])
        if "channel_mean_high_db" in env_params:
            wireless_env_params.setdefault("channel_mean_high_db", env_params["channel_mean_high_db"])
        
        # 传递 TTI 持续时间给无线环境（如果支持）
        wireless_env_params.setdefault("tti_duration", self.tti_duration)
        
        # 使用注册表工厂创建无线环境实例
        self.wireless_env = WirelessEnvRegistry.make(
            wireless_env_type,
            num_users=self.num_users,
            num_rbs=self.num_rbs,
            **wireless_env_params
        )
        
        
        # --- RL 空间定义 ---
        # 即使运行的是 PF 算法（不需要 Action），保持 Action Space 不变兼容性更好
        # Action 只影响 Env 中的 self.beta，如果 Scheduler 不用 beta，则 Action 无效但无害
        self.action_mapping = [0, 1e-4, -1e-4, 1e-3, -1e-3, 
                               1e-2, -1e-2, 5e-2, -5e-2, 1e-1, -1e-1]
        self.action_space = spaces.Discrete(len(self.action_mapping))
        
        # Observation Space (State)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(7,), dtype=np.float32)
        
        # --- 内部状态 ---
        self.beta = 1.0
        self.current_tti = 0
        self.user_buffers = np.zeros(self.num_users)
        self.head_of_line_delays = np.zeros(self.num_users)
        self.packet_queues = [[] for _ in range(self.num_users)]
        self.avg_throughput = np.zeros(self.num_users) + 1e-6
        
        self.fairness_calc = FairnessCalculator(self.num_users)

    def reset(self):
        self.beta = 1.0
        self.current_tti = 0
        self.user_buffers.fill(0)
        self.packet_queues = [[] for _ in range(self.num_users)]
        self.head_of_line_delays.fill(0)
        self.avg_throughput.fill(1e-6)
        
        # 重置无线环境状态
        self.wireless_env.reset()
        
        return self._get_obs()

    def step(self, action_idx):
        # 1. Update Beta (RL Action)
        # 如果是 PF 或标准 M-LWDF，beta 变化不会影响调度结果，但为了兼容 RL 接口，我们依然计算它
        if action_idx is not None:
            delta_beta = self.action_mapping[action_idx]
            self.beta += delta_beta
            self.beta = np.clip(self.beta, 0.0, 10.0)
        else:
            delta_beta = 0

        # 2. Traffic Generation
        if self.current_tti % self.tcbr_ttis == 0:
            bits_arrival = self.scbr_bytes * 8
            self.user_buffers += bits_arrival
            current_time = self.current_tti * self.tti_duration
            for u in range(self.num_users):
                self.packet_queues[u].append(current_time)

        # 3. Channel Simulation (使用无线环境抽象接口)
        channel_state = self.wireless_env.get_channel_state(self.current_tti)
        inst_snr_linear = channel_state['snr_linear']
        
        # 4. Scheduling Context Preparation
        potential_rates = self.wireless_env.calculate_potential_rates(inst_snr_linear)
        self._update_delays()
        
        context = {
            'potential_rates': potential_rates,
            'head_of_line_delays': self.head_of_line_delays,
            'avg_throughput': self.avg_throughput,
            'beta': self.beta, # 只有 B-M-LWDF 会用到这个
            'current_tti': self.current_tti
        }
        
        # 5. Execute Schedule
        allocation = self.scheduler.schedule(context)
        
        # 6. Transmission
        transmitted_bits = np.zeros(self.num_users)
        for rb_idx, user_idx in enumerate(allocation):
            rate = potential_rates[user_idx, rb_idx]
            bits_in_tti = rate * self.tti_duration
            bits_to_tx = min(self.user_buffers[user_idx], bits_in_tti)
            self.user_buffers[user_idx] -= bits_to_tx
            transmitted_bits[user_idx] += bits_to_tx
        
        # Update Throughput
        alpha = 1.0 / self.pf_window_size
        current_rate = transmitted_bits / self.tti_duration
        self.avg_throughput = (1 - alpha) * self.avg_throughput + alpha * current_rate
        
        self._clean_queues()
        
        # 7. Metrics & Reward
        norm_delays = self.fairness_calc.compute_normalized_delay(self.head_of_line_delays)
        fairness_case = self.fairness_calc.get_fairness_case(norm_delays)
        
        reward = self._calculate_reward(fairness_case, delta_beta)
        
        self.current_tti += 1
        obs = self._get_obs(norm_delays, fairness_case)
        done = False
        info = {
            "beta": self.beta, 
            "fairness_case": fairness_case,
            "avg_delay": np.mean(self.head_of_line_delays),
            "scheduler": self.scheduler_type,
            "avg_throughput": np.mean(self.avg_throughput),  # Added: Mean User Throughput (bps)
            "total_throughput": np.sum(self.avg_throughput)  # Added: Total Cell Throughput (bps)
        }
        
        return obs, reward, done, info

    def _update_delays(self):
        current_time = self.current_tti * self.tti_duration
        for u in range(self.num_users):
            if self.packet_queues[u]:
                self.head_of_line_delays[u] = current_time - self.packet_queues[u][0]
            else:
                self.head_of_line_delays[u] = 0.0

    def _clean_queues(self):
        packet_bits = self.scbr_bytes * 8
        for u in range(self.num_users):
            num_packets = int(np.ceil(self.user_buffers[u] / packet_bits))
            if len(self.packet_queues[u]) > num_packets:
                diff = len(self.packet_queues[u]) - num_packets
                self.packet_queues[u] = self.packet_queues[u][diff:]

    def _calculate_reward(self, case, delta_beta):
        if case == "FF": return 1.0
        elif case == "UF": return delta_beta if delta_beta > 0 else -1.0
        elif case == "OF": return -delta_beta if delta_beta < 0 else -1.0
        return 0.0

    def _get_obs(self, norm_delays=None, fairness_case="FF"):
        if norm_delays is None: norm_delays = np.zeros(self.num_users)
        d_inf, d_sup = self.fairness_calc.get_state_distances(norm_delays, fairness_case)
        state = np.array([
            self.beta, d_inf, d_sup,
            np.mean(norm_delays), np.std(norm_delays), 15.0, 2.0
        ], dtype=np.float32)
        return state
