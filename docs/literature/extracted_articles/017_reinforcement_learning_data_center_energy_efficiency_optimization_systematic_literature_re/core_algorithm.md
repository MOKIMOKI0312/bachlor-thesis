# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2025_Kahil_Reinforcement_learning_for_data_center_energy_efficiency_optimization_A.pdf`
- 标题：Reinforcement learning for data center energy efficiency optimization: A systematic literature review and research roadmap
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

Reinforcement learning for data center energy efficiency optimization: A systematic literature review and research roadmap Hussain Kahil a,∗ , Shiva Sharma b , Petri Välisuo a , Mohammed Elmusrati a a School of Technology and Innovation, University of Vaasa, Wolffintie 32, Vaasa, 65200, Finland b School of Technology, Vaasa University of Applied Sciences, Wolffintie 30, Vaasa, 65200, Finland
### Page 1

• Discusses using Reinforcement Learning (RL) for data center cooling system. • Discusses using RL for data center information and communication (ICT) system. • Provides a deep critical analysis for the energy optimization results. • Presents a comprehensive data extraction about the experimental setup and benchmarks. • Explores future direction in RL for optimizing energy in data center environments.
### Page 3

RDHX Rear Door Heat Exchangers TDBS Task Duplication-Based Scheduling RES Renewable Energy Systems TPM Traffic Prediction Module RH Relative Humidity TRPO Trust Region Policy Optimization RLR Robust Logistic Regression UP Utilization Prediction-aware RP Residual Physics UPS Uninterruptible Power Supply RR Round Robin VDN Value Decomposition Network RTP Real-Time Pricing VDT-UMC VM-based Dynamic Threshold and Minimum Correlation SAC Soft Actor Critic of Host Utilization VM Virtual Machine SARSA State-Action-Reward-State-Action VMC VM Consolidation SDAEM Stacked De-noising Auto-encoders with Multilayer VMP VM placement Perception VMPMBBO Multi-objective Biogeography-Based Optimization SDN Software-Defined Networking VMTA VM Traffic burst SFC Service Function Chaining VPBAR VM scheduling Based on Poisson Arrival Rate SLA Service Level Agreement VPME VM Placement with Maximizing Energy efficiency SO Snake optimizer WUE Water Usage Effectiveness SSP Single-Set Point
### Page 4

More localized CRAC Chiller comprehensive background on RL/DRL algorithms. Section 4 outlines Liquid In ROW Tower the research methodology. Section 5 explores the relevant literature cooling RDHX in detail. Section 6 offers an overview of additional objectives com- Re-use In Rack bined with energy efficiency. Section 7 discusses the identified research Cold plate Heat pump Immersion gaps, open challenges, and suggests future directions. Finally, Section 8 Spray Direct use concludes this review.
### Page 5

Table 1 Related reviews on DC energy efficiency, and comparison with our review. General focus System specific Review outcomes Reference Data Energy RL/DRL Cooling ICT Joint Energy Algorithm Benchmark Experimental center efficiency approaches system system optimization reporting comparisons comparisons setup
### Page 6

learning process to find the optimal policy that maximizes the expected Deep Reinforcement Learning (DRL), which integrates advancements cumulative reward over time 𝐺𝑡 , considering the environment dynamics in deep neural networks. In DRL algorithms, deep learning techniques defined by the MDP [29–31]. are employed to construct at least one of the following agent compo- However, the aforementioned process is not trivial. This challenge nents: value functions (8), (9), policy function (5), transition model(3), can be addressed recursively by introducing the state value function (V- and the reward function (4). Such representations are essential when function): the RL agent interacts with environments characterized by a high- [ 𝑛 ] dimensional state space and a continuous action space. DRL is a powerful ∑ tool for achieving an end-to-end goal-directed learning process [38,39]. 𝑉𝜋 (𝑠) = E𝑠𝑡 ,𝑎𝑡 ∼𝜏 𝛾 𝑘 𝑅𝑡+𝑘+1 𝑘=0 Figs. 3 and 4 present a comprehensive classification of the most popular RL/DRL algorithms based on their respective model types. ∑ ∑ ∞ (8) = 𝜋(𝑎𝑡 |𝑠𝑡 )𝑃 (𝑠𝑡+1 |𝑠𝑡 , 𝑎𝑡 ) 𝛾 𝑘 𝑅𝑡+𝑘+1 Another crucial aspect of RL/DRL algorithms is the type of policy (𝑠𝑡 ,𝑎𝑡 ,… )∼𝜏 𝑘=0 used during the training process. The focus here is to determine whether [ ] = E𝜋 𝑅𝑡+1 + 𝛾𝑉 (𝑆𝑡+1 ) ∣ 𝑆𝑡 = 𝑠
### Page 6

where 𝜏: (𝑠0 , 𝑎0 , 𝑠1 , 𝑎1 , … , 𝑎𝑡−1 , 𝑠𝑡 ) represents the interaction trajectory of the RL agent. Advanced policy TRPO Similarly, the expected return of taking a specific action 𝑎 in a given Policy-based gradient PPO state 𝑠 while following the policy 𝜋 can be given by the state-action value algorithms Basic policy VPG function (Q-function): gradient REINFORCE [ ] 𝑄𝜋 (𝑠, 𝑎) = E𝜋 𝑅𝑡+1 + 𝛾𝑄(𝑆𝑡+1 , 𝐴𝑡+1 ) ∣ 𝑆𝑡 = 𝑠, 𝐴𝑡 = 𝑎 (9)
### Page 6

Advanced A3C Eqs. (8) and (9) are referred to as the Bellman equations [32], which Actor-critic A2C are considered the fundamental formulas for tackling the decision- making process of an RL agent. The optimal V-function and Q-function Twin delayed TD3 are indicated by the maximum value across all states: 𝑉 ∗ = max𝑣𝜋 (𝑠) , or DDPG in all state-actions: 𝑄∗ (𝑠, 𝑎) = max 𝑄(𝑠, 𝑎). In all MDP cases, at least one RL Actor-critic optimal policy always exists, and the value functions 𝑉 (𝑠) and 𝑄(𝑠, 𝑎) of Model-free algorithms Soft actor critic SAC all optimal policies are the same. As a result, optimizing the Q-function Algorithms yields the optimal policy of the MDP: Deterministic DDPG policy gradient { 1 if 𝑎 = arg max𝑎∈𝐴 𝑄∗ (𝑠, 𝑎) Deep soft 𝜋 ∗ (𝑎|𝑠) = (10) DSAC 0 otherwise actor critic
### Page 7

1. Identification: Studies were retrieved using search queries across • RQ1: What data center subsystems (e.g., cooling, ICT equipment, the selected databases. power supply) are targeted by the RL/DRL algorithms? 2. Screening: The titles and abstracts were screened to eliminate • RQ2: Which RL/DRL algorithms are utilized for energy optimization irrelevant studies and duplicates. in data centers? 3. Eligibility: Full-text articles were reviewed against the inclusion • RQ3: What experimental setups and dataset sources (e.g., real-world and exclusion criteria. deployments or simulations) are commonly used? 4. Inclusion: The final set of studies that met all quality assessment • RQ4: What specific research problems are addressed using RL/DRL criteria was selected for detailed analysis. algorithms? • RQ5: What are the primary objectives addressed in the identified studies? A PRISMA flow diagram (Fig. 6) illustrates the selection process, • RQ6: What benchmarks are used to evaluate the achieved results in documenting the number of studies identified, screened, excluded, and terms of energy efficiency? included.
### Page 12

Table 4 Classification of algorithms by model type and study IDs. Category Algorithm type (RQ2) Study IDs
### Page 12

Number of Benchmarks 10 DRL (CDRL) and reward shaping to satisfy soft constraints through ex- 9 8 tensive online learning. Also, within the same study, hard constraints are 8 7 addressed by a parameterized shielding DRL algorithm (DRL-S), which 7 6 6 projects unsafe actions onto safe action spaces. The ultimate goal of these 6 5 studies in the second category is to design a safe cooling system for 5 4 data centers, reducing energy consumption while effectively maintain- 4 3 3 3 ing thermal constraints. The insights from this section are summarized 3 2 2 in Table A.8. 2 1 0 5.2.2. The energy related outcomes
### Page 14

of individual tasks within a job in a low-level approach. The main objec- address these issues are limited in their adaptability and fail to dynam- tive of the task scheduling studies is to select the optimal DC resource ically handle sudden network traffic fluctuations, leading to substantial for task execution, ensuring compliance with time and QoS constraints. energy waste. RL/DRL algorithms offer effective approaches to tackle Ten studies were identified that discussed the task scheduling problem these challenges. Four studies have been identified that explore solutions highlighting three main approaches: to this problem, each employing a unique structural RL/DRL approach:
### Page 15

the Nottingham University Data Center, were utilized as data sources in 100 Number of Benchmarks the identified studies. Moreover, well-known datasets such as PlanetLab 90 and the CoMon project were also employed for simulation experiments. 78 80 Synthetic datasets were another key data source, enabling controlled 70 and customized testing scenarios. Table 6 provides a comprehensive 60 overview of the experimental setup, encompassing the simulation en- 50 vironment, the sources and types of datasets (RQ3), and the platforms 40 31 used (RQ7) in all the identified studies on ICT systems. 30 23 20 12 5.4. Comparison of RL/DRL algorithms applied to optimizing integrated 10 7 5 data center systems 0 Developing an accurate, intelligent, and real-time DC environment m
### Page 18

Environmental System Reliability Algorithmic Impact Performance Management Performance
### Page 23

S61 DC network traffic Dynamically consolidates traffic without prior Shows that algorithms without FCT constraints (ElasticTree and CARPO) performed control knowledge to enhance DCN energy efficiency better than the proposed approach (SmartFCT). However, when considering FCT, the proposed scheme outperforms the benchmark method (FCTcon) by 11.3 %, 11.7 %, and 12.2 % in traffic datasets 1 to 3, respectively. Additionally, it achieves energy savings very close to the optimal algorithm across all datasets S62 Job schedul- Reduce energy consumption, lower operational Outperform all benchmark algorithms across datasets by achieving lower energy ing/Resource costs, decrease makespan, and optimize resource consumption allocation allocation S63 Task scheduling Reduces energy consumption, while balancing The energy aspect was evaluated in two scenarios: varying task numbers and VM counts. throughput, resource utilization, and makespan In both cases, the proposed algorithm outperformed other methods in energy reduc- in heterogeneous cloud computing environments tion. Simulations showed that as task or VM numbers increased, the algorithm improved load balancing and optimized resource utilization more effectively, minimizing energy consumption S64 Task scheduling The objectives include minimizing makespan, reduc- Reduce energy consumption compared to MCP and ETF benchmarks across all datasets ing energy consumption, lowering operational costs, by optimizing resource count and frequency and maximizing resource utilization
### Page 24

Table A.11 Overview of the main MDP elements in each joint optimization selected work. ID RL elements

## 公式/优化模型候选

### Page 5

```text
[17]              ●             ●                ●            ●         ×              ×                   ●             ◑                    ×                ×
  [18]              ●             ●                ●            ●         ×              ×                   ●             ◑                    ×                ×
```
### Page 5

```text
[17]              ●             ●                ●            ●         ×              ×                   ●             ◑                    ×                ×
  [18]              ●             ●                ●            ●         ×              ×                   ●             ◑                    ×                ×
  [19]              ●             ◑                ●            ×         ◑              ×                   ◑             ●                    ×                ×
```
### Page 5

```text
[18]              ●             ●                ●            ●         ×              ×                   ●             ◑                    ×                ×
  [19]              ●             ◑                ●            ×         ◑              ×                   ◑             ●                    ×                ×
  [20]              ●             ●                ◑            ×         ◑              ×                   ◑             ◑                    ◑                ●
```
### Page 5

```text
[19]              ●             ◑                ●            ×         ◑              ×                   ◑             ●                    ×                ×
  [20]              ●             ●                ◑            ×         ◑              ×                   ◑             ◑                    ◑                ●
  [21]              ●             ◑                ●            ×         ◑              ×                   ◑             ●                    ●                ●
```
### Page 5

```text
[20]              ●             ●                ◑            ×         ◑              ×                   ◑             ◑                    ◑                ●
  [21]              ●             ◑                ●            ×         ◑              ×                   ◑             ●                    ●                ●
  [22]              ●             ●                ●            ×         ◑              ×                   ●             ●                    ●                ●
```
### Page 5

```text
[21]              ●             ◑                ●            ×         ◑              ×                   ◑             ●                    ●                ●
  [22]              ●             ●                ●            ×         ◑              ×                   ●             ●                    ●                ●
  [23]              ●             ◑                ×            ×         ◑              ×                   ◑             ×                    ×                ×
```
### Page 5

```text
[22]              ●             ●                ●            ×         ◑              ×                   ●             ●                    ●                ●
  [23]              ●             ◑                ×            ×         ◑              ×                   ◑             ×                    ×                ×
  [24]              ●             ◑                ◑            ◑         ◑              ×                   ◑             ●                    ×                ×
```
### Page 5

```text
[23]              ●             ◑                ×            ×         ◑              ×                   ◑             ×                    ×                ×
  [24]              ●             ◑                ◑            ◑         ◑              ×                   ◑             ●                    ×                ×
  [25]              ●             ●                ×            ◑         ◑              ×                   ◑             ●                    ×                ×
```
### Page 6

```text
[ 𝑛                      ]                                             dimensional state space and a continuous action space. DRL is a powerful
                       ∑                                                                     tool for achieving an end-to-end goal-directed learning process [38,39].
𝑉𝜋 (𝑠) = E𝑠𝑡 ,𝑎𝑡 ∼𝜏               𝛾 𝑘 𝑅𝑡+𝑘+1
```
### Page 6

```text
∑                                                                     tool for achieving an end-to-end goal-directed learning process [38,39].
𝑉𝜋 (𝑠) = E𝑠𝑡 ,𝑎𝑡 ∼𝜏               𝛾 𝑘 𝑅𝑡+𝑘+1
                            𝑘=0
```
### Page 6

```text
RL/DRL algorithms based on their respective model types.
               ∑                                           ∑
                                                           ∞
```
### Page 6

```text
(8)
       =                    𝜋(𝑎𝑡 |𝑠𝑡 )𝑃 (𝑠𝑡+1 |𝑠𝑡 , 𝑎𝑡 )         𝛾 𝑘 𝑅𝑡+𝑘+1                     Another crucial aspect of RL/DRL algorithms is the type of policy
           (𝑠𝑡 ,𝑎𝑡 ,… )∼𝜏                                  𝑘=0                               used during the training process. The focus here is to determine whether
```
### Page 6

```text
=                    𝜋(𝑎𝑡 |𝑠𝑡 )𝑃 (𝑠𝑡+1 |𝑠𝑡 , 𝑎𝑡 )         𝛾 𝑘 𝑅𝑡+𝑘+1                     Another crucial aspect of RL/DRL algorithms is the type of policy
           (𝑠𝑡 ,𝑎𝑡 ,… )∼𝜏                                  𝑘=0                               used during the training process. The focus here is to determine whether
           [                           ]
```
### Page 6

```text
[                           ]
       = E𝜋 𝑅𝑡+1 + 𝛾𝑉 (𝑆𝑡+1 ) ∣ 𝑆𝑡 = 𝑠
```
### Page 6

```text
[                                        ]
𝑄𝜋 (𝑠, 𝑎) = E𝜋 𝑅𝑡+1 + 𝛾𝑄(𝑆𝑡+1 , 𝐴𝑡+1 ) ∣ 𝑆𝑡 = 𝑠, 𝐴𝑡 = 𝑎                           (9)
```
### Page 6

```text
TD3
are indicated by the maximum value across all states: 𝑉 ∗ = max𝑣𝜋 (𝑠) , or                                                                DDPG
in all state-actions: 𝑄∗ (𝑠, 𝑎) = max 𝑄(𝑠, 𝑎). In all MDP cases, at least one                      RL
```
### Page 8

```text
ACM Digital     5                 Remove           Exc
                                           library           Total=164    duplicates         53
```
### Page 19

```text
ference between total energy and reused energy by the ICT energy               previous studies have highlighted that traditional RL/DRL methods
    consumption. In an ideal scenario where ERE = 0, all waste heat is             face considerable barriers in large-scale applications due to high com-
    effectively recovered within the data center.                                  putational demands and slow convergence rates, which further limit
```

## 符号表/变量定义候选

### Page 2

```text
Nomenclature                                                      GMPR Greedy Minimizing Power consumption and Resource
                                                                              wastage
   A3C Asynchronous advantage actor-critic
                                                                     GRF Generalized Resource-Fair
   AC Actor-critic
                                                                     GRR Generalized Round Robin
   ACO Ant Colony Optimization
                                                                     GRVMP Greedy Randomized VM Placement
   ACS Ant Colony System
                                                                     HDDL Heterogeneous Distributed Deep Learning
   ADVMC Adaptive DRL based VM Consolidation
                                                                     HDRL Hierarchical DRL
   AFED-EF Adaptive Four-threshold Energy-aware VM Deployment
                                                                     HEFT Heterogeneous Earliest Time First
   ARLCA Advanced RL Consolidation Agent
                                                                     HGP Heteroscedastic Gaussian Processes
   ATES Aquifer Thermal Energy Storage
                                                                     HM Host Machine
   AVMC Autonomous VM Consolidation
                                                                     HVAC Heating, Ventilation, and Air Conditioning
   AVT Active Ventilation Tile
                                                                     ICA Imperialist Competitive Algorithm
   BDQ Branching Dueling Q-Network
                                                                     ICO IT Control Optimization
   BF Best Fit
                                                                     ICT Information and communication Technology
   BFD Best Fit Decreasing
                                                                     IGGA Improved Grouping Genetic Algorithm
   CARPO Correlation-AwaRe Power Optimization
                                                                     IQR Inter-Quartile Range
   CCO Cooling Control Optimization
                                                                     ITEE IT Equipment Energy
   CDRL Constrained DRL
                                                                     ITEU IT Equipment Utilization
   CFD Computational Fluid Dynamics
                                                                     JCO Joint IT and Cooling Control Optimization Algorithm
   CFWS Cost and carbon Footprint through Workload Shifting
                                                                     KMI-MRCU K-Means clustering algorithm-Midrange-Interquartile
   CNN Convolutional Neural Network
                                                                              range
   CSLB Crow Search-based Load Balancing
                                                                     LECC Location, Energy, Carbon and Cost-aware vm placement
   CVP Chemical reaction optimization-VMP-Permutation
                                                                     LR Logistic Regression
   CW Chilled Water
                                                                     LRR Local regression robust
   D3QN Dueling Deep Q Network
                                                                     LSTM Long Short-Term Memory
   DAG Directed Acyclic Graph
                                                                     MAD Median Absolute Deviation
   DBC Deadline and Budget Constrained
                                                                     MAGNETIC Multi-AGent machine learNing-based approach for
   DCI Dynamic Control Interval
                                                                              Energy efficienT dynamIc Consolidation
   DCN Data Center Network
                                                                     MBAC Model-Based Actor-Critic
   DDPG Deep Deterministic Policy Gradient
                                                                     MBHC MBRL-based HVAC control
   DL Deep Learning
                                                                     MBRL Model-Based RL
   DPPE Data Center Performance Per Energy
                                                                     MCP Modified Critical Path
   DPSO Discrete Particle Swarm Optimization
                                                                     MCTS Monte Carlo Tree Search
   DQN Deep Q-Network
                                                                     MDP Markov Decision Process
   DRL Deep Reinforcement Learning
                                                                     MFFD Modified First Fit Decreasing
   DSTS Dynamic Stochastic Task Scheduling
                                                                     MGGA Multi-objective Genetic Algorithm
   DTA DRL-based Task Migration
                                                                     MILP Mixed Integer linear programming
   DTH-MF Dynamic Threshold Maximum Fit
                                                                     MIMT Minimization of Migration based on Tesa
   DTM Dynamic Thermal Management
                                                                     MLF Minimum Load First
   DUE De-underestimation Validation Mechanism
                                                                     MMT Minimum Migration Time
   DX Direct Expansion
                                                                     MOACO Multi-Objective Ant Colony Optimization
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
