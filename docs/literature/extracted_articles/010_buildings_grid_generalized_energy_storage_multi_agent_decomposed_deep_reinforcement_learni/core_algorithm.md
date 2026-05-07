# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2026_Jin_Buildings_to_grid_with_generalized_energy_storage_A_multi_agent_decompos.pdf`
- 标题：Buildings-to-grid with generalized energy storage: A multi-agent decomposed deep reinforcement learning approach for delayed rewards
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

• A flexible generalized energy storage model is proposed to capture thermal inertia. • A multi-agent decomposed reinforcement learning algorithm is developed to handle delayed rewards in energy storage. • The proposed model improves temperature-tracking accuracy by 80.91 %. • The proposed algorithm reduces grid costs by 0.94 % and increases building profits by 93.74–104.06 %.
### Page 1

Keywords: The growing penetration of distributed renewable energy and flexible building loads is intensifying the bidirec­ BtG tional building-to-grid (BtG) coupling. However, the inherent heterogeneity between electrochemical batteries GESS and comfort-coupled thermal storage complicates coordinated control. To bridge this gap, the present study pro­ Delayed rewards poses a generalized energy storage system (GESS) that represents both devices with a common state of charge Multi-agent decomposed deep reinforcement and generalized charge/discharge power. An adaptive self-loss term captures both battery self-discharge and learning Sequential partially observable markov temperature-dependent passive heat exchange. The model maps the generalized power of thermal energy storage decision process to equivalent electrical power, while accounting for the thermal inertia of internal spaces and heating, venti­ lation, and air-conditioning systems. To address delayed rewards in the GESS, a multi-agent decomposed deep reinforcement learning approach is developed. The control problem is formulated as a sequential partially observ­ able Markov decision process with a dual-critic architecture that redistributes immediate rewards to construct delayed rewards. Decentralized actors are optimized using a clipped surrogate objective with combined advan­ tage estimates and control variate stabilization. Numerical experiments on the test system demonstrate that the proposed method enhances building profitability and reduces grid operating costs.
### Page 1

1. Introduction grid through services such as load shifting, demand response, and volt­ age stabilization [4,5]. Therefore, effective BtG coordination is essential The global shift toward renewable energy, driven by decarboniza­ for building resilient and intelligent distribution systems. tion goals and falling technology costs, has accelerated the integration The practical urgency for this coordination is intensifying with rising of renewables into the grid [1]. However, this transition introduces renewable penetration and urban decentralization. Distributed energy challenges such as intermittent generation, voltage regulation, and re­ resources introduce challenges to grid security constraints [6], while de­ verse power flows [2]. With buildings accounting for 39 % of global centralized loads introduce operational complexity [7]. Consequently, energy consumption, buildings-to-grid (BtG) integration has emerged recent studies explore building flexibility to address these issues [8,9]. as a promising solution for managing distributed energy resources and However, this coordination exhibits two key gaps. First, more accurate enhancing local flexibility [3]. By integrating real-time renewable gener­ building models are needed to capture complex thermal dynamics [10]. ation, controllable loads, and energy storage, buildings can support the
### Page 5

equilibrium constraints, which introduces significant computational 3.2. Proposed approach challenges due to the need to consider the entire scheduling horizon, Under immediate reward, the state-value function represents the thus failing to meet real-time requirements. To address this, reinforce­ expected return starting from the current observation and following the ment learning is adopted. Since buildings are managed by different policy thereafter: entities, using independent deep reinforcement learning agents for each building leads to non-stationarity. Therefore, the multi-agent deep rein­ [∞ ] ( ) ∑ forcement learning approach is employed, where each building acts as 𝑣𝜋 𝑚 𝑜𝑚 = 𝛾 𝑛 𝑚 𝑟 | 𝑜𝑚 (24) 𝑡+𝑛+1 | 𝑡 𝑡 E𝜋𝑚 an individual agent. 𝑛=0 This section initially introduces the proposed Seq-POMDP. Similarly, under delayed reward, the state-value function is the Section 3.2 presents a return-decomposition method that redistributes expected return starting from the current observation and memory, immediate rewards to construct delayed rewards, while Section 3.3 following the policy thereafter: introduces enhancements to the multi-agent proximal policy optimiza­ [∞ ] tion (MAPPO) algorithm. The key assumption in our algorithm is that ( ) ∑ 𝑣̃𝜋 𝑚 𝑜𝑚 , 𝑀𝑒 = 𝛾 𝑛 𝑚 ̃ 𝑟 |𝑜𝑚 , 𝑀𝑒 (25) the delayed reward and immediate reward formulations are expected 𝑡+𝑛+1 | 𝑡 𝑡 𝑡−1 E𝜋𝑚 𝑡−1 return-equivalent. 𝑛=0
### Page 6

Algorithm 1 Modified MAPPO algorithm for building 𝑚. 1: Input: Number of episodes 𝐸; number of steps 𝑇 ; mini batch size 𝐵; learning rate of network 𝜂 𝑚 ; immediate 2: Initialize: Actor network 𝜃𝑎𝑚 ; delayed critic network 𝜃𝑑𝑐 𝑚 ; memory 𝑀𝑒 critic network 𝜃𝑖𝑐 𝑡 3: for 𝑒 = 1 to 𝐸 do 4: Clear replay buffer 5: Reset observation and memory 6: for 𝑡 = 1 to 𝑇 do 7: Observe observation 𝑜𝑚 𝑡 𝑡 ∼ 𝜋 (𝑎𝑡 |𝑜𝑡 ) Select action 𝑎𝑚 8: 𝑚 𝑚 𝑚
### Page 7

Table 2 Average Daily Operational Cost ($) of Grid and Average Daily Revenue ($) of Buildings over 31 Test Days under the Two Algorithms.
### Page 7

Proposed 14033.18 −129.32 53.48 −1.07 MAPPO 14166.73 −2066.74 −1316.33 −125.44 Fig. 4. Training operational cost of grid under the three algorithms.
### Page 8

Table 3 Table 6 summarizes the average actor inference time for the exam­ Average Period Error Versus EnergyPlus (%) and Daily ined two PDNs in each building. For Buildings 1–3, the average actor Computation Time (min) of Building 1 under the Three Models. inference time differs by less than 1 % between the IEEE 33 and IEEE 123 systems (Table 6). This confirms that actor inference remains inde­ GESS Fixed Integral pendent of the PDN scale, demonstrating the scalability of the proposed Average period error 0.63 3.30 0.52 algorithm within the PDN. Furthermore, the multi-zone buildings 4–6 Daily computation time 0.58 0.53 94.37 increase inference time by 1.72 %, 3.42 %, and 8.62 % compared to their

## 公式/优化模型候选

### Page 2

```text
𝑄𝑚,𝑑𝑖𝑠 Minimum operational generalized discharging power of GESS
   Δ𝑡         Five minutes                                                               𝑡,𝑔𝑒
   𝜋𝑚         Policy of building 𝑚                                                                𝑔𝑒 in building 𝑚 at period 𝑡 (p.u.)
```
### Page 4

```text
⎪ 𝑚,𝑐ℎ    𝑚,𝑑𝑖𝑠                       𝑇 𝑡𝑒 − 𝑇 𝑚,𝑖𝑛
                                                                                                            ⎩𝜇𝑡,𝑏𝑒 + 𝜇𝑡,𝑏𝑒 ≤ 1                                𝑡𝑒
```
### Page 4

```text
𝑚      𝑚       𝑚
𝑃𝑡,𝑔 − 𝑃𝑡,𝑔𝑒 − 𝑃𝑡,𝑙𝑜 − 𝑃𝑡𝑚 = 0                                           (2)       ergy storage, determined by the battery’s chemical capacity for BESS
                  𝑚,𝑓     𝑚,ℎ𝑐
```
### Page 4

```text
𝑚       𝑚
𝑃𝑡,𝑔𝑒 = 𝑃𝑡,𝑏𝑒 + 𝑃𝑡,𝑡𝑒 + 𝑃𝑡,𝑡𝑒                                            (3)       (Row 6) indicates energy loss without external input, representing self-
      𝑚,𝑓     𝑚,𝑓                                                                  discharge for BESS and thermal energy exchange with the environment
```
### Page 4

```text
𝑚,𝑓     𝑚,𝑓                                                                  discharge for BESS and thermal energy exchange with the environment
0 ≤ 𝑃𝑡,𝑡𝑒 ≤ 𝑃 𝑡𝑒                                                         (4)
                                                                                   for TESS. Rated power limits (Rows 7 and 8) set the maximum and min­
```
### Page 4

```text
𝑚,ℎ𝑐
0 ≤ 𝑃𝑡,𝑡𝑒  ≤ 𝑃 𝑡𝑒                                                        (5)       imum energy storage/extraction rates, constrained by battery reactions
                                                                                   for BESS and thermal transfer rates in HVAC systems for TESS. Finally,
```
### Page 4

```text
𝑇 𝑚,𝑖𝑛   𝑚,𝑖𝑛
  𝑡𝑒 ≤ 𝑇𝑡,𝑡𝑒 ≤ 𝑇 𝑡𝑒                                                      (6)       operational power (Row 9) defines the energy storage rate, with release
                𝑚 − 𝐶𝑚
```
### Page 4

```text
𝑚               𝑔𝑒
0 ≤ 𝑆𝑂𝐶𝑡,𝑔𝑒   = 𝑚          ≤1                                            (7)       temperature change due to heat transfer for TESS.
               𝐶 𝑔𝑒 − 𝐶 𝑚
```
### Page 4

```text
(   (          )      ) 𝑚                                      electrical power is essential for assessing TESS’s impact on the power sys­
                ⎛             𝑚 Δ𝑡 𝑆𝑂𝐶 𝑚                  ⎞
 𝑚,𝑐ℎ       ⎜        1 − 1 − 𝜁𝑡,𝑔𝑒    𝑡,𝑔𝑒 𝐶 𝑔𝑒      𝑚,𝑐ℎ ⎟                        tem. In this study, the HVAC system is adopted as the thermal actuator.
```
### Page 5

```text
entities, using independent deep reinforcement learning agents for each
building leads to non-stationarity. Therefore, the multi-agent deep rein­                       [∞                   ]
                                                                                     ( )          ∑
```
### Page 5

```text
building leads to non-stationarity. Therefore, the multi-agent deep rein­                       [∞                   ]
                                                                                     ( )          ∑
forcement learning approach is employed, where each building acts as             𝑣𝜋 𝑚 𝑜𝑚  =          𝛾 𝑛 𝑚
```
### Page 5

```text
( )          ∑
forcement learning approach is employed, where each building acts as             𝑣𝜋 𝑚 𝑜𝑚  =          𝛾 𝑛 𝑚
                                                                                                        𝑟       | 𝑜𝑚
```
### Page 5

```text
𝑡    E𝜋𝑚
an individual agent.                                                                               𝑛=0
    This section initially introduces the proposed Seq-POMDP.
```
### Page 5

```text
introduces enhancements to the multi-agent proximal policy optimiza­
                                                                                                           [∞                        ]
tion (MAPPO) algorithm. The key assumption in our algorithm is that                   (            )        ∑
```
### Page 5

```text
[∞                        ]
tion (MAPPO) algorithm. The key assumption in our algorithm is that                   (            )        ∑
                                                                                 𝑣̃𝜋 𝑚 𝑜𝑚 , 𝑀𝑒       =        𝛾 𝑛 𝑚
```
### Page 5

```text
tion (MAPPO) algorithm. The key assumption in our algorithm is that                   (            )        ∑
                                                                                 𝑣̃𝜋 𝑚 𝑜𝑚 , 𝑀𝑒       =        𝛾 𝑛 𝑚
                                                                                                                 ̃
```
### Page 5

```text
𝑡      𝑡−1     E𝜋𝑚                       𝑡−1
return-equivalent.                                                                                         𝑛=0
```
### Page 6

```text
critic network 𝜃𝑖𝑐            𝑡
                                                                                            3: for 𝑒 = 1 to 𝐸 do
                                                                                            4:    Clear replay buffer
```
### Page 6

```text
5:    Reset observation and memory
                                                                                            6:    for 𝑡 = 1 to 𝑇 do
                                                                                            7:        Observe observation 𝑜𝑚  𝑡
```
### Page 6

```text
11:     end for
                                                                                           12:     for 𝑚𝑖 = 1 to 𝑀𝐼 do
                                                                                           13:        Delayed Critic (Gradient Descent):
```
### Page 6

```text
𝑡,̃         (                      )
                                                                                                           𝑚 ← 𝜃 𝑚 − 𝜂∇ 𝑚             1 ∑𝐵     𝐷      𝐷)
                                                                                           15:            𝜃𝑑𝑐   𝑑𝑐     𝜃     𝑑𝑐       𝐵  𝑡=1 (𝐿𝑡,𝑟 + 𝐿𝑡,̃
```
### Page 6

```text
𝑚 ← 𝜃 𝑚 − 𝜂∇ 𝑚             1 ∑𝐵     𝐷      𝐷)
                                                                                           15:            𝜃𝑑𝑐   𝑑𝑐     𝜃     𝑑𝑐       𝐵  𝑡=1 (𝐿𝑡,𝑟 + 𝐿𝑡,̃
                                                                                                                                                        𝑟
```
### Page 6

```text
17:            Compute 𝐿𝑣𝑡,𝑟 , 𝐿𝑣𝑡,̃𝑟 [(34) and (35)]
                                                                                                                             ( ∑                     )
                                                                                                           𝑚 ← 𝜃𝑚 − 𝜂∇ 𝑚         1  𝐵     𝑣      𝑣 )
```
### Page 6

```text
𝑚 ← 𝜃𝑚 − 𝜂∇ 𝑚         1  𝐵     𝑣      𝑣 )
                                                                                           18:            𝜃𝑖𝑐   𝑖𝑐       𝜃  𝑖𝑐   𝐵  𝑡=1 (𝐿𝑡,𝑟 + 𝐿𝑡,̃
                                                                                                                                                   𝑟
```
### Page 6

```text
20:            Compute 𝐽𝑡𝑚 [(40)]
                                                                                                                           ( ∑         )
                                                                                           21:            𝜃𝑎𝑚 ← 𝜃𝑎𝑚 + 𝜂∇𝜃𝑎𝑚 𝐵1 𝐵
```
### Page 10

```text
robustness.                                                                                       𝑟𝑚
                                                                                                  ̃    =           𝑟𝑡+1 ||𝑜𝑚
                                                                                                            E 𝑚 𝛾 𝑡̃       𝑡 , 𝑀𝑒𝑡−1
```
### Page 10

```text
𝑡+1   𝛾𝑡 𝜋
                                                                                                            (     [∞                          ]         [ 𝑡−1                       ])
                                                                                                          1         ∑                                    ∑
```
### Page 10

```text
(     [∞                          ]         [ 𝑡−1                       ])
                                                                                                          1         ∑                                    ∑
CRediT authorship contribution statement                                                                = 𝑡 E𝜋 𝑚         𝛾 𝑛̃
```
### Page 10

```text
1         ∑                                    ∑
CRediT authorship contribution statement                                                                = 𝑡 E𝜋 𝑚         𝛾 𝑛̃
                                                                                                                            𝑟𝑚   |𝑜𝑚 , 𝑀𝑒       −             𝛾 𝑛 𝑚 | 𝑚
```
### Page 10

```text
𝑡−1     E 𝜋 𝑚                         𝑡−1
                                                                                                         𝛾                    𝑛=0                                             𝑛=0
   Jiahui Jin: Writing – original draft, Visualization, Validation,                                              (          [∞                     ]            [ 𝑡−1                            ])
```
### Page 10

```text
𝛾                    𝑛=0                                             𝑛=0
   Jiahui Jin: Writing – original draft, Visualization, Validation,                                              (          [∞                     ]            [ 𝑡−1                            ])
Software, Methodology, Formal analysis, Data curation. Guoqiang                                           1                  ∑                                   ∑
```
### Page 10

```text
Jiahui Jin: Writing – original draft, Visualization, Validation,                                              (          [∞                     ]            [ 𝑡−1                            ])
Software, Methodology, Formal analysis, Data curation. Guoqiang                                           1                  ∑                                   ∑
                                                                                                        = 𝑡                         𝛾 𝑛 𝑟𝑚   |𝑜𝑚       − E𝜋 𝑚                𝑟𝑚
```
### Page 10

```text
Software, Methodology, Formal analysis, Data curation. Guoqiang                                           1                  ∑                                   ∑
                                                                                                        = 𝑡                         𝛾 𝑛 𝑟𝑚   |𝑜𝑚       − E𝜋 𝑚                𝑟𝑚
                                                                                                                                                                          𝛾 𝑛̃    |𝑜𝑚 , 𝑀𝑒
```

## 符号表/变量定义候选

### Page 2

```text
Nomenclature                                                                     Model Variables
                                                                                    𝑏𝑚
                                                                                     𝑡 Distribution locational marginal price of building 𝑚 ($/p.u.)
   Indices, Sets, and Functions                                                      𝑚
                                                                                    𝐶𝑡,𝑏𝑒 Remaining capacity of BESS 𝑏𝑒 in building 𝑚 at period 𝑡 (p.u.)
   𝑏𝑒         Index of battery energy storage system (BESS)                          𝑚
                                                                                    𝐶𝑡,𝑔𝑒 Remaining capacity of GESS 𝑔𝑒 in building 𝑚 at period 𝑡 (p.u.)
   𝑐𝑙𝑖𝑝       Clipped function
                                                                                      𝑚
                                                                                    𝑓𝑡,𝑡𝑒 Mass flow rate of TESS 𝑡𝑒 in building 𝑚 at period 𝑡 (kg/s)
   𝐶𝑜𝑣        Covariance function
   𝐷𝑡𝑚        Cumulative function in building 𝑚 at period 𝑡                         𝑃𝑡𝑚 Transaction electric power of building 𝑚 at period 𝑡 (p.u.)
   E          Expectation function                                                    𝑚
                                                                                    𝑃𝑡,𝑏𝑒 Operational electric power of BESS 𝑏𝑒 in building 𝑚 at period 𝑡
   𝑔𝑒         Index of generalized energy storage system (GESS)                               (p.u.)
   ℎ𝑣         Index of heating, ventilation, and air conditioning (HVAC)              𝑚
                                                                                    𝑃𝑡,𝑙𝑜 Load in building 𝑚 at period 𝑡 (p.u.)
   𝑚          Index of building in set 𝑀                                              𝑚 Generating electric power in building 𝑚 at period 𝑡 (p.u.)
                                                                                    𝑃𝑡,𝑔
   𝑚𝑖         Index of mini-batch in set 𝑀𝐼
                                                                                      𝑚
                                                                                    𝑃𝑡,𝑔𝑒 Operational electric power of GESS 𝑔𝑒 in building 𝑚 at period 𝑡
   𝑀𝑒𝑚        Memory function
   ̃
   𝑟          Delayed reward function                                                        (p.u.)
   𝑡          Index of the five-minute period                                       𝑄𝑚
                                                                                     𝑡,𝑔𝑒 Operational input generalized power of GESS 𝑔𝑒 in building 𝑚
   𝑡𝑒         Index of thermal energy storage system (TESS)                                  at period 𝑡 (p.u.)
       𝑚
   𝑣𝜋         State-value function of immediate reward under policy 𝜋 𝑚             𝑄𝑡,𝑔𝑒
                                                                                         𝑚,𝑐ℎ
                                                                                                Maximum operational generalized charging power of GESS 𝑔𝑒
       𝑚
   𝑣̃𝜋        State-value function of delayed reward under policy 𝜋 𝑚                             in building 𝑚 at period 𝑡 (p.u.)
   𝑉 𝑎𝑟       Variance function
                                                                                    𝑄𝑚,𝑑𝑖𝑠 Minimum operational generalized discharging power of GESS
   Δ𝑡         Five minutes                                                               𝑡,𝑔𝑒
   𝜋𝑚         Policy of building 𝑚                                                                𝑔𝑒 in building 𝑚 at period 𝑡 (p.u.)
                                                                                      𝑚,𝑓
                                                                                    𝑃𝑡,𝑡𝑒 Operational electric power of the fan in TESS 𝑡𝑒 in building 𝑚
   Parameters and Constants                                                                  at period 𝑡 (p.u.)
   𝑐𝑝        Specific heat capacity (J/(kg⋅K))                                        𝑚,ℎ𝑐
                                                                                    𝑃𝑡,𝑡𝑒  Operational electric power of the compressor in TESS 𝑡𝑒 in
     𝑚
   𝐶 𝑏𝑒          Rated capacity of BESS 𝑏𝑒 in building 𝑚 (p.u.)                              building 𝑚 at period 𝑡 (p.u.)
     𝑚                                                                                 𝑚
                                                                                    𝑆𝑂𝐶𝑡,𝑔𝑒 State of charge of GESS 𝑔𝑒 in building 𝑚 at period 𝑡 (p.u.)
   𝐶 𝑔𝑒          Rated capacity of GESS 𝑔𝑒 in building 𝑚 (p.u.)
                                                                                      𝑚,𝑖𝑛
   𝐶𝑚            Minimum capacity of GESS 𝑔𝑒 in building 𝑚 (p.u.)                   𝑇𝑡,𝑡𝑒  Internal temperature of TESS 𝑡𝑒 in building 𝑚 at period 𝑡 (◦ C)
     𝑔𝑒
                                                                                      𝑚,𝑜𝑢𝑡
   𝐻𝑚            Thermal capacitance of building 𝑚 (p.u./◦ C)                       𝑇𝑡,𝑡𝑒   External temperature of TESS 𝑡𝑒 in building 𝑚 at period 𝑡 (◦ C)
                                                                                      𝑚,𝑠𝑢
   𝐻ℎ𝑣𝑚          Thermal capacitance of HVAC ℎ𝑣 in building 𝑚 (p.u./◦ C)            𝑇𝑡,𝑡𝑒  Supply air temperature of TESS 𝑡𝑒 in building 𝑚 at period 𝑡 (◦ C)
     𝑚,𝑐ℎ                                                                             𝑚,𝑎𝑐𝑡
   𝑃 𝑏𝑒          Rated maximum electric charging power of BESS 𝑏𝑒 in                𝑊𝑡,𝑡𝑒   Active heat transfer rate of TESS 𝑡𝑒 in building 𝑚 at period 𝑡
                 building 𝑚 (p.u.)                                                           (p.u.)
                                                                                      𝑚,𝑝𝑎
   𝑃 𝑚,𝑑𝑖𝑠
     𝑏𝑒
                 Rated minimum electric discharging power of BESS 𝑏𝑒 in             𝑊𝑡,𝑡𝑒  Passive heat transfer rate of TESS 𝑡𝑒 in building 𝑚 at period 𝑡
                 building 𝑚 (p.u.)                                                           (p.u.)
      𝑚,𝑓                                                                            𝑚
   𝑃 𝑡𝑒          Maximum electric power of the fan in TESS 𝑡𝑒 in building           𝜁𝑡,𝑔𝑒 Self-loss coefficient of GESS 𝑔𝑒 in building 𝑚 at period 𝑡 (p.u./h)
                 𝑚 (p.u.)                                                            𝑚,𝑐ℎ 𝑚,𝑑𝑖𝑠
                                                                                    𝜇𝑡,𝑏𝑒 , 𝜇𝑡,𝑏𝑒 Binary variable of BESS 𝑏𝑒 in building 𝑚 at period 𝑡
      𝑚,ℎ𝑐
   𝑃 𝑡𝑒          Maximum electric power of the compressor in TESS 𝑡𝑒 in              𝑚,ℎ𝑒 𝑚,𝑐𝑜𝑜
                                                                                    𝜇𝑡,𝑡𝑒 , 𝜇𝑡,𝑡𝑒 Binary variable of TESS 𝑡𝑒 in building 𝑚 at period 𝑡
                 building 𝑚 (p.u.)
      𝑚,𝑐ℎ
   𝑄𝑔𝑒           Rated maximum generalized charging power of GESS 𝑔𝑒 in             Reinforcement Learning Variables
                 building 𝑚 (p.u.)                                                  𝑎𝑚        Action in building 𝑚 at time period 𝑡
                                                                                     𝑡
   𝑄𝑚,𝑑𝑖𝑠        Rated minimum generalized discharging power of GESS 𝑔𝑒             𝐴𝑣𝑚       Generalized advantage estimation of immediate critic in
      𝑔𝑒                                                                               𝑡
                 in building 𝑚 (p.u.)                                                         building 𝑚 at period 𝑡
   𝑅𝑚            Thermal resistance of building 𝑚 (◦ C/p.u.)                        ̃𝑚
                                                                                    𝐴𝑣        Generalized advantage estimation of delayed critic in build­
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
