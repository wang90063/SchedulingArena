import numpy as np

class FairnessCalculator:
    """
    处理论文中的公平性逻辑，包括 CDF 计算、状态判断 (Algorithm 1) 和 State Values (Algorithm 2)。
    """
    
    def __init__(self, num_users, lambda_param=0.2, xi=0.1, psi=0.1):
        """
        :param lambda_param: 最佳用户百分比 (e.g., 20%)
        :param xi: 容忍度/置信因子 (confidence factor)
        :param psi: 异常值(outliers)百分比 (e.g., 10%)
        """
        self.M = num_users
        self.lambda_p = lambda_param
        self.xi = xi
        self.psi = psi
        
        # 预计算所需的索引
        self.idx_best = int(np.ceil(self.lambda_p * self.M))
        self.idx_worst_start = int(np.ceil(self.lambda_p * self.M))
        self.idx_outliers_start = self.M - int(np.ceil(self.psi * self.M))

    def compute_normalized_delay(self, delays):
        """
        Eq. 7: W_tilde = W / mean(W)
        """
        avg_delay = np.mean(delays)
        if avg_delay == 0:
            return np.ones_like(delays)
        return delays / avg_delay

    def get_fairness_case(self, norm_delays):
        """
        Algorithm 1: 判断当前是 OF (Over-Fair), UF (Unfair), 还是 FF (Feasible-Fair)
        """
        # 1. 排序 normalized delays
        w_sorted = np.sort(norm_delays)
        
        # 2. 计算要求值 w^(R) = j/M + 0.5 (Eq. 6 的逆函数推导)
        # j 从 1 到 M
        j_indices = np.arange(1, self.M + 1)
        w_required = (j_indices / self.M) + 0.5
        
        # 3. 检查条件
        # 偏差: w_sorted - w_required
        # 只需要检查是否 > xi
        violation = (w_sorted > (w_required + self.xi))
        
        # Case OF: Check best users (indices 0 to idx_best-1)
        # 论文伪代码: sum(I(...)) > 1 (意味着只要有一个违反或者多于一个？通常 >0 即视为违反)
        # 这里假设只要有一个违反
        is_of = np.any(violation[:self.idx_best])
        
        if is_of:
            return "OF"
            
        # Case UF: Check worst users (excluding outliers)
        # range: [idx_best, idx_outliers_start)
        # 注意：算法1伪代码 line 4 检查的是 w_sorted > w_required + xi 是否发生
        # 但 UF 的定义通常是延迟过大。
        # 论文文本描述: "system is labeled as UF if any of the worst users do not fulfill the delay requirement"
        # 且 requirement 是 w < w_req + xi. 
        # 所以如果 worst user 的延迟 > req + xi，那就是 UF。
        if self.idx_outliers_start > self.idx_best:
            is_uf = np.any(violation[self.idx_best : self.idx_outliers_start])
            if is_uf:
                return "UF"
                
        return "FF"

    def get_state_distances(self, norm_delays, fairness_case):
        """
        Algorithm 2: 计算 d_inf 和 d_sup
        """
        w_sorted = np.sort(norm_delays)
        j_indices = np.arange(1, self.M + 1)
        w_required = (j_indices / self.M) + 0.5
        
        delta_w = w_sorted - (w_required + self.xi)
        
        # Indices for groups
        group_best = delta_w[:self.idx_best]
        group_worst = delta_w[self.idx_best:] # 包含 outliers 用于计算 state 吗？
        # 论文 Algorithm 2 中 line 3 和 6 的下标似乎是剩下的所有用户
        
        if fairness_case == "OF":
            d_inf = np.max(group_best)
            d_sup = np.min(group_worst)
        elif fairness_case == "UF":
            d_inf = np.min(group_best)
            d_sup = np.max(group_worst)
        else: # FF
            d_inf = np.min(group_best)
            d_sup = np.max(group_worst)
            
        return d_inf, d_sup
