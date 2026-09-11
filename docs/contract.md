# RateCert-HEP 最小认证契约

这个原型只认证一个明确对象：**固定阈值、固定定点格式、独立部署曝光块上的触发率**。
它不训练模型，也不把一个网页图形当作科学证据。

## 输入

- `deployment_scores`：部署实现产生的事件级分数流；本原型会按 `FixedPointSpec` 量化。
- `threshold_code`：部署端实际使用的整数阈值，必须在校准块确定后固定。
- `exposure_s`：部署块的有效曝光时间，单位为秒。
- `alpha`：单侧 Poisson 上界的尾概率。
- `rate_budget_hz`：需要满足的原始触发率预算。
- `prescale`：触发后记录率的整数 prescale；原始率和记录率必须分开报告。
- `rate_lsb_hz`：部署计数器或固件率寄存器的确定性最小率步长，单位为 Hz；必须预先声明，不能由部署样本反推。
- `rate_rounding`：率寄存器的舍入规则。本原型支持 `nearest_even`、`floor` 和 `trunc`。
- `rate_counter_bits`：无符号率计数器位宽；声明后会自动得到最大可表示计数和最大率，并在溢出时拒绝认证。
- `calibration_block_id` 与 `deployment_block_id`：两个不同的块标识。

## 保证和边界

若部署块的计数服从 Poisson 模型，且阈值由独立校准块确定，则

\[
P(\lambda \le U_\alpha(N,T)) \ge 1-\alpha.
\]

定点实现的代码范围、舍入、饱和和 tie 行为必须明确。证书使用实际整数部署分数计数，并额外保留 `rate_lsb_hz` 对应的确定性舍入误差作为配置裕度。部署块中由分数直方图观测到的阈值步长只作为诊断，不能参与认证条件。

对于固定窗口计数器，若窗口为 `T_w` 秒、计数器为 `B` 位无符号整数，则

\[
\Delta r_q = 1/T_w,\qquad C_{\max}=2^B-1,\qquad R_{\max}^{\rm counter}=C_{\max}/T_w.
\]

`RateQuantizationSpec.from_counter_window(T_w, counter_bits=B)` 会按这个关系生成率规格。

证书只有在

\[
U_\alpha(N,T)+\epsilon_{r,q} \le R_{\max},
\qquad
\epsilon_{r,q}=\begin{cases}
\Delta r_q/2 & \text{nearest-even}\\
\Delta r_q & \text{floor or trunc}
\end{cases}
\]

且没有结构化拒绝原因时才为 `CERTIFIED`。

证书同时给出无量纲部署分数

\[
S_{\rm deploy}=1-\frac{U_\alpha+\epsilon_{r,q}}{R_{\max}}.
\]

它只是上述不等式的归一化安全余量，不含人为权重；`S_deploy >= 0` 才有可能通过。

## 必须拒绝的情况

- 校准块和部署块缺少标识或标识相同；
- 分数包含 NaN/无穷值或不是一维事件流；
- 定点溢出而没有显式允许饱和；
- 有限样本上界超过率计数器的满量程；
- `exposure_s`、`alpha`、预算或 prescale 非法；
- 有限样本上界加定点率裕度超过预算；
- 缺少预先声明的确定性率分辨率；只有一个可观测分数等级只会使诊断字段为空，不再导致认证公式改用经验步长。

本契约中的 Poisson 假设、独立块假设和率寄存器 LSB 都必须在最终论文中单独列出，不能隐藏在 API 默认值中。

## 公开 HEP 样本模式

公开数据通常只有固定数量的事件，没有有效曝光时间。此时使用
`choose_acceptance_threshold` 与 `certify_acceptance`：校准块固定整数阈值，
部署块上令 `K` 为通过事件数、`n` 为部署样本数，并计算

\[
U_\alpha(K,n)=\operatorname{Beta}^{-1}(1-\alpha;K+1,n-K).
\]

只有当 `U_alpha <= target_acceptance` 时才给出通过结论。阈值可以按校准块
经验尾部选择；论文实验使用校准块的同一单侧上界选择，以避免把抽样波动
误报为部署保证。对位宽、样本量或预算的多格扫描，报告把 alpha 按格数做
Bonferroni 分配。分数定点 LSB 是可复现的代码分辨率；它不会被擅自当作
接受概率误差或 Hz 误差。只有在外部明确给出输入通量、率预算和率寄存器
LSB 时，二项上界才会换算为原始/记录 Hz。

当前公开复现实验使用 LHC Olympics 2020 R&D 特征文件的 QCD 背景（Zenodo
`10.5281/zenodo.6466204`，CC-BY-4.0，Pythia8+Delphes），并明确标记其
触发选择和“无 live-time/flux”的限制。因此该实验验证的是固定点分数和
有限样本接受概率链路，不声称已经测得 CMS/ATLAS 硬件触发率。
