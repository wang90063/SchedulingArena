"""
无线环境仿真器抽象层

提供可插拔的无线环境仿真接口，支持不同的信道模型和仿真器。
"""
import numpy as np
from abc import ABC, abstractmethod


class WirelessEnvRegistry:
    """无线环境仿真器注册工厂"""
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
            raise ValueError(f"WirelessEnv '{name}' not found. Available: {list(cls._registry.keys())}")
        return cls._registry[name](**kwargs)


class BaseWirelessEnv(ABC):
    """
    无线环境仿真器基类
    
    定义无线环境仿真的标准接口，包括：
    - 信道状态生成（SNR/信道质量）
    - 潜在速率计算
    - 环境重置和状态管理
    """
    
    def __init__(self, num_users, num_rbs, **kwargs):
        """
        初始化无线环境
        
        :param num_users: 用户数量
        :param num_rbs: 资源块数量
        :param kwargs: 其他环境特定参数
        """
        self.num_users = num_users
        self.num_rbs = num_rbs
    
    @abstractmethod
    def get_channel_state(self, current_tti):
        """
        获取当前 TTI 的信道状态
        
        :param current_tti: 当前传输时间间隔索引
        :return: dict 包含：
            - 'snr_linear': (num_users, num_rbs) 线性尺度的 SNR 矩阵
            - 'snr_db': (num_users, num_rbs) dB 尺度的 SNR 矩阵（可选）
        """
        pass
    
    @abstractmethod
    def reset(self):
        """
        重置无线环境状态（例如：重新初始化信道参数）
        """
        pass
    
    def calculate_potential_rates(self, snr_linear, bandwidth_per_rb=180e3):
        """
        根据 SNR 计算潜在传输速率（Shannon Capacity）
        
        :param snr_linear: (num_users, num_rbs) 线性尺度的 SNR 矩阵
        :param bandwidth_per_rb: 每个资源块的带宽（Hz），默认 180kHz
        :return: (num_users, num_rbs) 潜在速率矩阵（bps）
        """
        return bandwidth_per_rb * np.log2(1 + snr_linear)


@WirelessEnvRegistry.register("SimpleRayleigh")
class SimpleRayleighWirelessEnv(BaseWirelessEnv):
    """
    简单的 Rayleigh 衰落信道模型
    
    实现：
    - 每个用户有平均 SNR（dB）
    - 瞬时 SNR = 平均 SNR + 快衰落（高斯噪声）+ 慢衰落（指数分布）
    """
    
    def __init__(self, num_users, num_rbs, 
                 channel_mean_low_db=10, channel_mean_high_db=20,
                 fast_fading_std=3.0, **kwargs):
        """
        初始化 Rayleigh 信道环境
        
        :param num_users: 用户数量
        :param num_rbs: 资源块数量
        :param channel_mean_low_db: 平均 SNR 下限（dB）
        :param channel_mean_high_db: 平均 SNR 上限（dB）
        :param fast_fading_std: 快衰落标准差（dB）
        """
        super().__init__(num_users, num_rbs, **kwargs)
        self.channel_mean_low_db = channel_mean_low_db
        self.channel_mean_high_db = channel_mean_high_db
        self.fast_fading_std = fast_fading_std
        
        # 每个用户的平均 SNR（在 reset 时初始化）
        self.channel_means = None
        self.reset()
    
    def reset(self):
        """重置信道参数（重新随机生成平均 SNR）"""
        self.channel_means = np.random.uniform(
            self.channel_mean_low_db, 
            self.channel_mean_high_db, 
            size=self.num_users
        )
    
    def get_channel_state(self, current_tti):
        """
        生成当前 TTI 的信道状态
        
        :param current_tti: 当前传输时间间隔索引
        :return: dict 包含 'snr_linear' 和 'snr_db'
        """
        # 快衰落：高斯噪声
        fast_fading_db = np.random.normal(0, self.fast_fading_std, (self.num_users, self.num_rbs))
        
        # 瞬时 SNR (dB) = 平均 SNR + 快衰落
        inst_snr_db = self.channel_means[:, np.newaxis] + fast_fading_db
        
        # 慢衰落：指数分布（Rayleigh 衰落）
        # 转换为线性尺度并乘以指数分布的衰落因子
        inst_snr_linear = np.power(10, inst_snr_db / 10.0) * np.random.exponential(1.0, (self.num_users, self.num_rbs))
        
        return {
            'snr_linear': inst_snr_linear,
            'snr_db': inst_snr_db
        }


@WirelessEnvRegistry.register("Realistic5G")
class Realistic5GWirelessEnv(BaseWirelessEnv):
    """
    基于 Table I 参数的相对实际的 5G 无线环境模型
    
    实现特性：
    - 多普勒效应（考虑用户移动速度 5 km/h 和载波频率 5 GHz）
    - 多径衰落（考虑时延扩展 100 µs）
    - 快衰落和慢衰落组合
    - 时间相关性（简化的 Jakes 模型）
    - 频率选择性衰落（基于相干带宽）
    - 符合 Table I 的参数设置
    
    参数说明（基于 Table I）：
    - mean_snr_db: 平均 SNR = 15 dB (μ_γ)
    - std_snr_db: SNR 标准差 = 3 dB (σ_γ)
    - carrier_frequency: 载波频率 = 5 GHz
    - user_speed: 用户移动速度 = 5 km/h
    - delay_spread: 时延扩展 = 100 µs
    - tti_duration: TTI 持续时间 = 1 ms
    
    信道模型：
    1. 慢衰落（大尺度）：
       - 路径损耗：PL(d) = 10*α*log10(d/d_0)，其中 α 是路径损耗指数
       - 阴影衰落：对数正态分布，标准差 8 dB，具有时间相关性
       - 用户间差异：模拟不同用户的基础信道质量差异
       - 组合：慢衰落 = 参考SNR - 路径损耗 + 阴影衰落 + 用户差异
    2. 快衰落（小尺度）：Rayleigh 衰落，具有时间相关性
    3. 频率选择性：基于时延扩展计算相干带宽，应用频率相关衰落
    4. 多普勒效应：根据用户速度和载波频率计算多普勒频移和相干时间
    
    距离相关特性：
    - 用户距离：假设用户均匀分布在小区内（圆形区域，半径可配置）
    - 路径损耗：与距离的 α 次方相关（α 通常为 2-4，城市环境约 3.5）
    - 阴影衰落：对数正态分布，随时间缓慢变化（相干时间约 1 秒）
    - 用户移动：支持基于速度和方向的动态距离变化
      * 径向移动：朝向/远离基站
      * 切向移动：围绕基站移动（距离不变）
      * 随机移动：混合模式
    """
    
    def __init__(self, num_users, num_rbs,
                 tti_duration=1e-3,  # 1 ms
                 carrier_frequency=5e9,  # 5 GHz
                 user_speed=5.0,  # 5 km/h
                 delay_spread=100e-6,  # 100 µs
                 mean_snr_db=15.0,  # μ_γ = 15 dB (参考距离处的平均 SNR)
                 std_snr_db=3.0,  # σ_γ = 3 dB (阴影衰落标准差)
                 coherence_time_factor=0.1,  # 相干时间因子
                 cell_radius=500.0,  # 小区半径（米），默认 500m
                 reference_distance=100.0,  # 参考距离（米），默认 100m
                 path_loss_exponent=3.5,  # 路径损耗指数，默认 3.5（城市环境）
                 shadowing_std_db=8.0,  # 阴影衰落标准差（dB），默认 8 dB
                 enable_distance_based_fading=True,  # 是否启用基于距离的慢衰落
                 enable_mobility=True,  # 是否启用用户移动（距离随时间变化）
                 movement_direction_mode="random",  # 移动方向模式："random", "radial", "tangential"
                 **kwargs):
        """
        初始化实际的 5G 无线环境
        
        :param num_users: 用户数量
        :param num_rbs: 资源块数量
        :param tti_duration: TTI 持续时间（秒），默认 1 ms
        :param carrier_frequency: 载波频率（Hz），默认 5 GHz
        :param user_speed: 用户移动速度（km/h），默认 5 km/h
        :param delay_spread: 时延扩展（秒），默认 100 µs
        :param mean_snr_db: 参考距离处的平均 SNR（dB），默认 15 dB (μ_γ)
        :param std_snr_db: SNR 标准差（dB），默认 3 dB (σ_γ)，用于用户间差异
        :param coherence_time_factor: 相干时间因子，控制时间相关性
        :param cell_radius: 小区半径（米），默认 500m
        :param reference_distance: 参考距离（米），默认 100m
        :param path_loss_exponent: 路径损耗指数，默认 3.5（城市环境，范围通常 2-4）
        :param shadowing_std_db: 阴影衰落标准差（dB），默认 8 dB
        :param enable_distance_based_fading: 是否启用基于距离的慢衰落，默认 True
        """
        super().__init__(num_users, num_rbs, **kwargs)
        self.tti_duration = tti_duration
        self.carrier_frequency = carrier_frequency
        self.user_speed = user_speed
        self.delay_spread = delay_spread
        self.mean_snr_db = mean_snr_db
        self.std_snr_db = std_snr_db
        self.coherence_time_factor = coherence_time_factor
        
        # 距离相关参数
        self.cell_radius = cell_radius
        self.reference_distance = reference_distance
        self.path_loss_exponent = path_loss_exponent
        self.shadowing_std_db = shadowing_std_db
        self.enable_distance_based_fading = enable_distance_based_fading
        self.enable_mobility = enable_mobility
        self.movement_direction_mode = movement_direction_mode
        
        # 物理常数
        self.c = 3e8  # 光速 (m/s)
        
        # 计算多普勒频移
        # f_d = v * f_c / c
        # v in m/s = user_speed * 1000 / 3600
        self.user_speed_ms = user_speed * 1000 / 3600  # 转换为 m/s
        self.doppler_freq = self.user_speed_ms * carrier_frequency / self.c  # Hz
        
        # 计算相干时间（近似）
        # T_c ≈ 0.423 / f_d (Jakes 模型)
        if self.doppler_freq > 0:
            self.coherence_time = 0.423 / self.doppler_freq
        else:
            self.coherence_time = np.inf
        
        # 计算相干带宽（基于时延扩展）
        # B_c ≈ 1 / (2π * τ_rms)
        if delay_spread > 0:
            self.coherence_bandwidth = 1 / (2 * np.pi * delay_spread)
        else:
            self.coherence_bandwidth = np.inf
        
        # 每个 RB 的带宽（5G NR: 180 kHz）
        self.bandwidth_per_rb = 180e3  # Hz
        self.total_bandwidth = num_rbs * self.bandwidth_per_rb
        
        # 初始化状态变量
        self.current_tti = 0
        self.channel_phases = None  # 用于时间相关性
        self.slow_fading_db = None  # 慢衰落（大尺度）
        self.fast_fading_complex = None  # 快衰落（小尺度，复数）
        self.user_distances = None  # 用户到基站的距离（米）
        self.user_angles = None  # 用户相对于基站的方位角（弧度）
        self.user_movement_directions = None  # 用户移动方向（相对于基站：1=远离，-1=朝向，0=随机）
        self.shadowing_db = None  # 阴影衰落（dB）
        self.user_variation_db = None  # 用户间差异（固定，只在 reset 时设置）
        
        self.reset()
    
    def reset(self):
        """重置信道参数"""
        self.current_tti = 0
        
        # 初始化用户到基站的距离和位置
        # 假设用户均匀分布在小区内（圆形区域）
        # 使用平方根分布以保持均匀的空间分布
        if self.enable_distance_based_fading:
            # 均匀分布在 [r_min, r_max] 范围内
            r_min = 50.0  # 最小距离（避免过近）
            r_max = self.cell_radius
            # 使用平方根分布以保持均匀的空间分布
            uniform_r = np.random.uniform(0, 1, size=self.num_users)
            self.user_distances = np.sqrt(uniform_r * (r_max**2 - r_min**2) + r_min**2)
            
            # 初始化用户方位角（相对于基站）
            self.user_angles = np.random.uniform(0, 2 * np.pi, size=self.num_users)
            
            # 初始化用户移动方向
            if self.enable_mobility:
                if self.movement_direction_mode == "radial":
                    # 径向移动：随机选择朝向或远离基站
                    self.user_movement_directions = np.random.choice([-1, 1], size=self.num_users)
                elif self.movement_direction_mode == "tangential":
                    # 切向移动：垂直于半径方向（距离不变，但角度变化）
                    self.user_movement_directions = np.zeros(self.num_users)  # 0 表示切向
                else:  # "random"
                    # 随机方向：每个用户随机选择移动方向
                    # -1: 朝向基站, 1: 远离基站, 0: 切向移动
                    self.user_movement_directions = np.random.choice([-1, 0, 1], size=self.num_users, p=[0.3, 0.3, 0.4])
            else:
                self.user_movement_directions = np.zeros(self.num_users)  # 不移动
            
            # 计算路径损耗（基于距离）
            # PL(d) = PL_0 + 10*α*log10(d/d_0)
            # 其中 PL_0 是参考距离 d_0 处的路径损耗
            # 这里我们直接计算相对于参考距离的路径损耗
            path_loss_db = 10 * self.path_loss_exponent * np.log10(
                self.user_distances / self.reference_distance
            )
            
            # 阴影衰落（对数正态分布）
            # 每个用户的阴影衰落在时间上相关，但在初始化时随机
            self.shadowing_db = np.random.normal(0, self.shadowing_std_db, size=self.num_users)
            
            # 用户间差异（模拟不同用户的基础信道质量差异）
            # 这个差异是固定的，只在 reset 时设置一次
            self.user_variation_db = np.random.normal(0, self.std_snr_db, size=self.num_users)
            
            # 组合：慢衰落 = 参考SNR - 路径损耗 + 阴影衰落 + 用户间差异
            self.slow_fading_db = (self.mean_snr_db - path_loss_db + 
                                  self.shadowing_db + self.user_variation_db)
        else:
            # 如果不启用基于距离的衰落，使用原来的简单模型
            self.user_distances = np.ones(self.num_users) * self.reference_distance
            self.shadowing_db = np.zeros(self.num_users)
            self.slow_fading_db = np.random.normal(
                self.mean_snr_db, 
                self.std_snr_db, 
                size=self.num_users
            )
        
        # 初始化快衰落的相位（用于时间相关性）
        # 使用 Jakes 模型的简化版本
        self.channel_phases = np.random.uniform(0, 2 * np.pi, size=(self.num_users, self.num_rbs))
        
        # 初始化快衰落（复数，用于多径效应）
        self.fast_fading_complex = np.zeros((self.num_users, self.num_rbs), dtype=complex)
        self._update_fast_fading()
    
    def _update_user_positions(self):
        """
        更新用户位置（基于速度和移动方向）
        考虑用户移动导致的距离变化
        """
        if self.user_distances is None or self.user_movement_directions is None:
            return
        
        # 计算每个 TTI 移动的距离（米）
        # user_speed 是 km/h，转换为 m/s，然后乘以 TTI 持续时间
        distance_per_tti = self.user_speed_ms * self.tti_duration  # 米/TTI
        
        # 更新距离和角度
        for u in range(self.num_users):
            direction = self.user_movement_directions[u]
            
            if direction == -1:
                # 朝向基站移动（距离减小）
                new_distance = self.user_distances[u] - distance_per_tti
                # 防止距离过小
                self.user_distances[u] = max(new_distance, 50.0)
            elif direction == 1:
                # 远离基站移动（距离增大）
                new_distance = self.user_distances[u] + distance_per_tti
                # 防止超出小区范围（可以反弹或循环）
                if new_distance > self.cell_radius:
                    # 反弹：改变方向
                    self.user_movement_directions[u] = -1
                    self.user_distances[u] = 2 * self.cell_radius - new_distance
                else:
                    self.user_distances[u] = new_distance
            else:  # direction == 0 (切向移动)
                # 切向移动：距离不变，但角度变化
                # 计算切向速度（保持距离不变）
                angular_velocity = distance_per_tti / max(self.user_distances[u], 50.0)  # rad/TTI
                # 随机选择顺时针或逆时针
                if np.random.random() < 0.5:
                    self.user_angles[u] += angular_velocity
                else:
                    self.user_angles[u] -= angular_velocity
                self.user_angles[u] = np.mod(self.user_angles[u], 2 * np.pi)
    
    def _update_fast_fading(self):
        """
        更新快衰落（考虑时间相关性和多径效应）
        使用简化的 Jakes 模型
        """
        # 计算时间相关性因子
        if self.coherence_time > 0 and self.coherence_time < np.inf:
            # 时间相关性：exp(-Δt / T_c)
            time_corr = np.exp(-self.tti_duration / (self.coherence_time * self.coherence_time_factor))
        else:
            time_corr = 0.0  # 完全独立
        
        # 更新相位（考虑多普勒效应）
        phase_increment = 2 * np.pi * self.doppler_freq * self.tti_duration
        self.channel_phases += phase_increment + np.random.normal(0, 0.1, size=(self.num_users, self.num_rbs))
        self.channel_phases = np.mod(self.channel_phases, 2 * np.pi)
        
        # 生成新的独立快衰落分量
        # 实部和虚部独立的高斯分布（Rayleigh 衰落）
        new_real = np.random.normal(0, 1/np.sqrt(2), size=(self.num_users, self.num_rbs))
        new_imag = np.random.normal(0, 1/np.sqrt(2), size=(self.num_users, self.num_rbs))
        new_fading = new_real + 1j * new_imag
        
        # 应用时间相关性（AR(1) 模型）
        self.fast_fading_complex = (time_corr * self.fast_fading_complex + 
                                    np.sqrt(1 - time_corr**2) * new_fading)
    
    def _apply_frequency_selective_fading(self, base_snr_linear):
        """
        应用频率选择性衰落（考虑时延扩展和多径效应）
        
        :param base_snr_linear: 基础 SNR（线性尺度）
        :return: 应用频率选择性后的 SNR
        """
        # 计算频率相关性
        # 如果相干带宽小于总带宽，则存在频率选择性
        if self.coherence_bandwidth < self.total_bandwidth:
            # 频率相关性：不同 RB 之间的相关性
            # 使用指数衰减模型
            rb_indices = np.arange(self.num_rbs)
            freq_corr_matrix = np.exp(-np.abs(rb_indices[:, None] - rb_indices[None, :]) * 
                                     self.bandwidth_per_rb / self.coherence_bandwidth)
            
            # 对每个用户应用频率选择性
            freq_selective_factor = np.zeros((self.num_users, self.num_rbs))
            for u in range(self.num_users):
                # 生成频率相关的衰落
                freq_fading = np.random.multivariate_normal(
                    np.zeros(self.num_rbs),
                    freq_corr_matrix
                )
                freq_selective_factor[u, :] = np.power(10, freq_fading / 10.0)
        else:
            # 平坦衰落（所有 RB 相同）
            freq_selective_factor = np.ones((self.num_users, self.num_rbs))
        
        return base_snr_linear * freq_selective_factor
    
    def get_channel_state(self, current_tti):
        """
        生成当前 TTI 的信道状态
        
        :param current_tti: 当前传输时间间隔索引
        :return: dict 包含 'snr_linear' 和 'snr_db'
        """
        # 更新快衰落（考虑时间相关性）
        if current_tti != self.current_tti:
            self._update_fast_fading()
            
            # 更新用户位置（如果启用移动性）
            if self.enable_mobility and self.enable_distance_based_fading:
                self._update_user_positions()
            
            # 更新阴影衰落（变化较慢，但随时间变化）
            # 阴影衰落的相干时间通常比快衰落长得多（秒级）
            if self.enable_distance_based_fading:
                # 使用 AR(1) 模型更新阴影衰落
                # 阴影衰落的相干时间假设为 1 秒（1000 个 TTI）
                shadowing_coherence_ttis = 1000
                shadowing_time_corr = np.exp(-1.0 / shadowing_coherence_ttis)
                
                # 生成新的阴影衰落分量
                new_shadowing = np.random.normal(0, self.shadowing_std_db, size=self.num_users)
                
                # 应用时间相关性
                self.shadowing_db = (shadowing_time_corr * self.shadowing_db + 
                                     np.sqrt(1 - shadowing_time_corr**2) * new_shadowing)
                
                # 重新计算慢衰落（包括更新的距离和阴影衰落）
                if self.user_distances is not None and self.user_variation_db is not None:
                    path_loss_db = 10 * self.path_loss_exponent * np.log10(
                        self.user_distances / self.reference_distance
                    )
                    # 慢衰落 = 参考SNR - 路径损耗 + 阴影衰落 + 用户间差异
                    # 用户间差异是固定的，阴影衰落随时间缓慢变化，路径损耗随距离变化
                    self.slow_fading_db = (self.mean_snr_db - path_loss_db + 
                                          self.shadowing_db + self.user_variation_db)
            
            self.current_tti = current_tti
        
        # 1. 慢衰落（大尺度衰落）- 在用户间变化，但在短时间内相对稳定
        slow_fading_linear = np.power(10, self.slow_fading_db / 10.0)
        
        # 2. 快衰落（小尺度衰落）- 从复数衰落中提取幅度
        # |h|^2 服从指数分布（Rayleigh 分布）
        fast_fading_power = np.abs(self.fast_fading_complex) ** 2
        
        # 3. 组合慢衰落和快衰落
        # SNR = (慢衰落功率) * (快衰落功率)
        base_snr_linear = slow_fading_linear[:, np.newaxis] * fast_fading_power
        
        # 4. 应用频率选择性衰落（多径效应）
        inst_snr_linear = self._apply_frequency_selective_fading(base_snr_linear)
        
        # 5. 添加额外的快衰落噪声（模拟更复杂的多径环境）
        # 使用较小的随机扰动
        additional_fading = np.random.lognormal(0, 0.1, size=(self.num_users, self.num_rbs))
        inst_snr_linear *= additional_fading
        
        # 转换为 dB
        inst_snr_db = 10 * np.log10(inst_snr_linear + 1e-10)  # 避免 log(0)
        
        return {
            'snr_linear': inst_snr_linear,
            'snr_db': inst_snr_db
        }


# ============================================================================
# 示例：如何添加新的无线环境仿真器
# ============================================================================
#
# 要添加新的无线环境仿真器，只需：
#
# 1. 继承 BaseWirelessEnv 类
# 2. 实现 get_channel_state() 和 reset() 方法
# 3. 使用 @WirelessEnvRegistry.register("YourEnvName") 装饰器注册
#
# 示例：
#
# @WirelessEnvRegistry.register("Rician")
# class RicianWirelessEnv(BaseWirelessEnv):
#     """Rician 衰落信道模型"""
#     
#     def __init__(self, num_users, num_rbs, k_factor=10, **kwargs):
#         super().__init__(num_users, num_rbs, **kwargs)
#         self.k_factor = k_factor
#         self.reset()
#     
#     def reset(self):
#         """重置信道参数"""
#         # 初始化逻辑
#         pass
#     
#     def get_channel_state(self, current_tti):
#         """生成 Rician 信道状态"""
#         # 实现 Rician 信道模型
#         snr_linear = ...  # 你的计算逻辑
#         return {
#             'snr_linear': snr_linear,
#             'snr_db': 10 * np.log10(snr_linear)
#         }
#
# 然后在配置文件中使用：
# {
#   "wireless_env": {
#     "type": "Rician",
#     "params": {
#       "k_factor": 10
#     }
#   }
# }
