# First validation report

运行环境：Windows 主机上的 Python 3.10、NumPy 1.26.4、SciPy 1.15.3。

## 核心检查

`py -m pytest tests -q`：23 项通过。

`py -m compileall -q src examples`：通过。

命令行入口已用随包合成 CSV 实测，输出 `reports/cli_certificate.json`，状态为 `CERTIFIED`。科学拒绝和格式错误使用不同退出语义：前者仍写报告并返回 0，后者返回 2。

## 独立合成块示例

- 校准块与部署块使用不同随机种子和不同块标识；
- 10 bit、8 fractional bits、nearest-even、无饱和；
- 部署块观测计数 `N=158`，曝光 `T=20 s`；
- 点估计原始率 `7.9 Hz`；
- `alpha=0.01` 的单侧 Poisson 上界 `9.4897902928 Hz`；
- 确定性率寄存器 LSB `0.05 Hz`，nearest-even 舍入误差界 `0.025 Hz`，计数器位宽 `32 bit`；
- 部署块观测到的分数阈值步长 `2.0 Hz` 仅作为诊断；
- 预算 `12.0 Hz`；
- 最终安全余量 `2.4852097072 Hz`；
- 部署分数 `0.2071008090`；
- 证书状态：`CERTIFIED`。

## 两个行为性检查

1. 对真实率 `8 Hz`、曝光 `20 s` 的 10,000 个 Poisson 重复样本，`alpha=0.01` 上界的观测覆盖率为 `0.9901`，目标下限为 `0.99`。
2. 一个接近预算的块点估计为 `9.5 Hz`，预算为 `10 Hz`，但精确上界为 `12.025228 Hz`，因此证书返回 `NOT_CERTIFIED`。这验证了工具会拒绝“点估计通过、有限样本上界不通过”的情况。

## 当前限制

`rate_resolution_hz` 现在来自预先声明的率寄存器 LSB，不再从部署样本推断。分数阈值步长保留为诊断量。当前结果证明的是确定性率量化契约的架构可行性；真实硬件接入仍需用固件寄存器规格复核 LSB。

## 公开 HEP 复现

使用 LHC Olympics 2020 R&D 特征文件（Zenodo `10.5281/zenodo.6466204`，
CC-BY-4.0；本地文件 SHA-256
`933b1f11d7b66e6dae0ee2878723f8f5d7ab0f38399806f2d067c5cfd9a502b1`），
从 `label == 0` 的 QCD 背景中按固定种子抽取不重叠的 100k 校准块和 100k
部署块。分数定义为 `hypot(pxj1, pyj1) / 5000 GeV`，没有学习网络。

`py examples/public_lhco_acceptance.py ...` 产生 27 个格子：8/10/12 bit、
10k/50k/100k 部署样本和 0.5%/1%/2% 接受概率预算。将家族错误率 1% 均分
到每格（`alpha = 0.0003703703704`）后，19 格 `CERTIFIED`、8 格
`NOT_CERTIFIED`。这份公开实验的量是背景接受概率；由于数据文件没有 live
time 或代表性输入通量，所有 Hz 字段保持空值，避免伪造探测器速率。

报告同时对每个部署前缀的所有观测代码阈值计算“量化规则 − 未量化规则”
的接受率差异。最大绝对差异随位宽下降：8 bit 为 0.0559、10 bit 为
0.0146、12 bit 为 0.0048；认证阈值处的差异单独记录在
`quantization_acceptance_delta`。该量化审计是数据分布上的诊断，不能被
解释为跨数据分布的统一误差界。

`py examples/coverage_stress.py ...` 以相同的每格 alpha 对四个二项边界场景
各重复 20,000 次，观测覆盖率为 0.99945、0.99965、0.99965、1.00000，均与
名义覆盖率 0.9996296 一致（Monte-Carlo 区间写入
`reports/coverage_stress.json`）。该压力测试只检查实现与数值稳定性，不替代
Clopper–Pearson 的精确覆盖定理。

## 统一基准

`py examples/unified_benchmark.py ...` 将上述 LHCO 接受概率结果与明确曝光
的 Poisson 速率结果写入 `reports/unified_benchmark.json`。速率部分固定真实
背景率 8 Hz，扫描 1/10/100 s 曝光、0.01/0.05/0.1 Hz 率 LSB、8/16 bit
计数器和 10/12 Hz 预算，共 36 格；11 格通过完整契约。8 bit 计数器在
100 s 曝光时因满量程拒绝，1 s 曝光因有限样本上界过宽而拒绝。三种曝光的
覆盖率诊断分别为 1.0000、0.9998、0.9998，名义覆盖率为 0.9997222。

`py examples/make_unified_figure.py ...` 已从统一 JSON 生成 300 dpi PNG、
矢量 PDF 及 `figure_manifest.json`。三幅面板分别展示量化接受率偏差、速率
认证比例和“有限样本上界 + 率分辨率裕度”相对预算的关系；图中没有加入任何
未由报告数据支持的硬件性能指标。

`py examples/make_diagnostic_figures.py ...` 另外生成四张独立诊断图：二项与
Poisson 覆盖率及重复不确定度、公开数据的“上界/目标”认证余量、按曝光时间
分解的显式速率拒绝谓词，以及固定率 Poisson 假设边界。输出同时包含 300 dpi
PNG、矢量 PDF 和带输入哈希的 `diagnostic_figure_manifest.json`。

## 性能诊断

`py examples/performance_benchmark.py` 在 Intel Core i7-10750H、Python 3.10.7、
NumPy 1.26.4、SciPy 1.15.3 上对 100,000 个分数重复 20 次。中位耗时为：
量化 2.37 ms、公开接受概率证书 2.81 ms、明确曝光速率证书 7.20 ms。
`rate_curve` 使用唯一代码的反向累积计数，避免对每个阈值重复扫描整列分数。
这些是软件吞吐诊断，不是探测器或固件时延证明。
