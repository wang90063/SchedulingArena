import numpy as np
from abc import ABC, abstractmethod

class SchedulerRegistry:
    """调度器注册工厂"""
    _registry = {}

    @classmethod
    def register(cls, name):
        def inner_wrapper(wrapped_class):
            cls._registry[name] = wrapped_class
            return wrapped_class
        return inner_wrapper

    @classmethod
    def make(cls, name, **kwargs):
        if name not in cls._registry:
            raise ValueError(f"Scheduler '{name}' not found. Available: {list(cls._registry.keys())}")
        return cls._registry[name](**kwargs)

class BaseScheduler(ABC):
    """调度算法基类"""
    
    def __init__(self, **kwargs):
        pass

    @staticmethod
    def calculate_potential_rates(snr_matrix, bandwidth_per_rb=180e3):
        """
        通用工具：根据SNR计算潜在速率 (Shannon Capacity)
        snr_matrix: (Num_Users, Num_RBs) linear scale
        """
        return bandwidth_per_rb * np.log2(1 + snr_matrix)
    
    @staticmethod
    def _allocate_resources(metric_matrix):
        """
        通用工具：Winner-takes-all 资源分配
        metric_matrix: (Num_Users, Num_RBs)
        """
        # 对每个 RB (axis 1)，找 metric 最大的用户 (axis 0)
        return np.argmax(metric_matrix, axis=0)

    @abstractmethod
    def schedule(self, context):
        """
        核心调度方法
        :param context: 包含环境状态的字典 (rates, delays, throughputs, beta, etc.)
        :return: allocation list
        """
        pass

@SchedulerRegistry.register("PF")
class ProportionalFairScheduler(BaseScheduler):
    """Proportional Fair (PF)"""
    
    def schedule(self, context):
        potential_rates = context['potential_rates']
        avg_throughput = context['avg_throughput']
        
        # 防止除零
        avg_tp_safe = np.maximum(avg_throughput, 1e-6)
        
        # Metric = r_{u,k} / R_u
        metric = potential_rates / avg_tp_safe[:, np.newaxis]
        return self._allocate_resources(metric)

@SchedulerRegistry.register("Ehanced-PF")
class EhancedProportionalFairScheduler(BaseScheduler):
    """
    Enhanced Proportional Fair (PF)

    factor = (tau_u / (tau_u - head_of_line_delays)) * (PF factor)
           = (tau_u / (tau_u - W_u)) * (r_{u,k} / R_u)
    """

    def __init__(self, tau_u=0.1, **kwargs):
        super().__init__(**kwargs)
        self.tau_u = tau_u

    def schedule(self, context):
        potential_rates = context['potential_rates']
        avg_throughput = context['avg_throughput']
        delays = context['head_of_line_delays']

        # PF factor: r_{u,k} / R_u
        avg_tp_safe = np.maximum(avg_throughput, 1e-6)
        pf_factor = potential_rates / avg_tp_safe[:, np.newaxis]

        # Enhanced factor: tau_u / (tau_u - W_u)
        # 数值保护：当 W_u >= tau_u 时分母 <= 0，会导致发散；这里用很小的正数下界避免除零/负数。
        denom = np.maximum(self.tau_u - delays, 1e-9)
        delay_factor = (self.tau_u / denom)[:, np.newaxis]

        metric = delay_factor * pf_factor
        return self._allocate_resources(metric)

@SchedulerRegistry.register("M-LWDF")
class MLWDFScheduler(BaseScheduler):
    """Standard M-LWDF (Beta fixed to 1 implicitly)"""
    
    def __init__(self, delta_u=0.05, tau_u=0.1, **kwargs):
        super().__init__(**kwargs)
        self.delta_u = delta_u
        self.tau_u = tau_u

    def schedule(self, context):
        potential_rates = context['potential_rates']
        avg_throughput = context['avg_throughput']
        delays = context['head_of_line_delays']
        
        # Calculate constants
        a_u = -np.log(self.delta_u) / self.tau_u
        avg_tp_safe = np.maximum(avg_throughput, 1e-6)
        g_u = a_u / avg_tp_safe
        
        # Metric = g_u * W_u * r_{u,k}
        # W_u shape adjust for broadcasting
        metric = g_u[:, np.newaxis] * delays[:, np.newaxis] * potential_rates
        return self._allocate_resources(metric)

@SchedulerRegistry.register("B-M-LWDF")
class BMLWDFScheduler(BaseScheduler):
    """
    B-M-LWDF (Beta controlled externally)
    This is the algorithm used by the RL agent.
    """
    
    def __init__(self, delta_u=0.05, tau_u=0.1, **kwargs):
        super().__init__(**kwargs)
        self.delta_u = delta_u
        self.tau_u = tau_u

    def schedule(self, context):
        potential_rates = context['potential_rates']
        avg_throughput = context['avg_throughput']
        delays = context['head_of_line_delays']
        beta = context.get('beta', 1.0) # Get beta from context
        
        a_u = -np.log(self.delta_u) / self.tau_u
        avg_tp_safe = np.maximum(avg_throughput, 1e-6)
        g_u = a_u / avg_tp_safe
        
        # Metric = g_u * (W_u)^beta * r_{u,k}
        # Protect against 0 delay for power operation
        delays_pow = np.power(np.maximum(delays, 1e-9), beta)
        
        metric = g_u[:, np.newaxis] * delays_pow[:, np.newaxis] * potential_rates
        return self._allocate_resources(metric)

@SchedulerRegistry.register("LDF")
class LDFScheduler(BaseScheduler):
    """Largest Delay First"""
    
    def schedule(self, context):
        # LDF ignores channel quality, purely delay based.
        # But we need to assign RBs.
        # Usually LDF assigns *all* resources to the user with max delay,
        # or prioritizes them.
        # Implementation here: User with max delay gets priority on all RBs 
        # (effectively getting all RBs unless we do per-RB logic, but LDF is user-centric).
        
        delays = context['head_of_line_delays']
        num_rbs = context['potential_rates'].shape[1]
        
        # Find user with max delay
        user_idx = np.argmax(delays)
        
        # Give all RBs to this user
        allocation = np.full(num_rbs, user_idx, dtype=int)
        return allocation
