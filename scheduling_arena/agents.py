import numpy as np

class PIDBetaController:
    """
    PID 控制器，支持两种模式（就像两个按钮）：
    1. 恒定增益 (Constant Gain): 所有工况使用同一套 Kp, Ki, Kd。
    2. 增益调度 (Gain Scheduling): 根据 Beta 的大小动态调整 PID 参数。
    """
    
    def __init__(self, kp=0.5, ki=0.01, kd=0.1, action_map=None, use_gain_scheduling=True):
        self.base_kp = kp
        self.base_ki = ki
        self.base_kd = kd
        self.use_gain_scheduling = use_gain_scheduling
        
        # 积分项累计
        self.integral = 0.0
        # 上一次误差 (用于微分项)
        self.prev_error = 0.0
        
        # 环境的动作空间映射表
        if action_map is None:
            self.action_map = [0, 1e-4, -1e-4, 1e-3, -1e-3, 
                               1e-2, -1e-2, 5e-2, -5e-2, 1e-1, -1e-1]
        self.action_map = np.array(action_map)

    # --- "按钮 1"：创建恒定增益控制器 ---
    @classmethod
    def create_constant(cls, kp=0.5, ki=0.01, kd=0.1):
        """
        工厂方法：创建一个恒定参数的 PID 控制器 (Gain Scheduling OFF)
        """
        return cls(kp=kp, ki=ki, kd=kd, use_gain_scheduling=False)

    # --- "按钮 2"：创建增益调度控制器 ---
    @classmethod
    def create_scheduled(cls, base_kp=0.5, base_ki=0.01, base_kd=0.1):
        """
        工厂方法：创建一个带增益调度的 PID 控制器 (Gain Scheduling ON)
        """
        return cls(kp=base_kp, ki=base_ki, kd=base_kd, use_gain_scheduling=True)

    def _schedule_gains(self, current_beta):
        """
        核心调度逻辑
        """
        if not self.use_gain_scheduling:
            # 模式 1: 恒定返回基准参数
            return self.base_kp, self.base_ki, self.base_kd

        # 模式 2: 动态调度参数
        # 敏感区 (Beta < 2.0): 减小增益，防止震荡
        if current_beta < 2.0:
            kp = self.base_kp * 0.8
            ki = self.base_ki * 0.8
            kd = self.base_kd
            
        # 线性区 (2.0 <= Beta < 5.0): 使用基准参数
        elif current_beta < 5.0:
            kp = self.base_kp
            ki = self.base_ki
            kd = self.base_kd
            
        # 饱和区 (Beta >= 5.0): 增大增益，克服饱和效应
        else:
            kp = self.base_kp * 1.5
            ki = self.base_ki * 1.2
            kd = self.base_kd * 1.0
            
        return kp, ki, kd

    def get_action(self, obs, info=None):
        """
        obs 结构: [beta, d_inf, d_sup, mean_w, std_w, mean_mcs, std_mcs]
        """
        current_beta = obs[0]
        d_inf = obs[1]
        d_sup = obs[2]
        
        # 计算误差 (Error)
        error = 0.0
        if info:
            case = info.get('fairness_case', 'FF')
            if case == 'UF':
                error = d_sup  # Unfair -> 需要增大 Beta
            elif case == 'OF':
                error = -d_inf # Over-fair -> 需要减小 Beta
        else:
            # Fallback
            if d_sup > 0.01: error = d_sup
            elif d_inf > 0.01: error = -d_inf
        
        # 获取当前工况下的 PID 参数
        kp, ki, kd = self._schedule_gains(current_beta)
        
        # PID 计算
        p_term = kp * error
        
        self.integral += error
        self.integral = np.clip(self.integral, -5.0, 5.0) # Anti-windup
        i_term = ki * self.integral
        
        d_term = kd * (error - self.prev_error)
        self.prev_error = error
        
        control_output = p_term + i_term + d_term
        
        # 动作量化
        action_idx = (np.abs(self.action_map - control_output)).argmin()
        
        return action_idx

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0
