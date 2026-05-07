# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2026_Zhang_Physics_guided_deep_reinforcement_learning_for_optimized_data_center_coo.pdf`
- 标题：Physics-guided deep reinforcement learning for optimized data center cooling and waste heat recovery utilizing aquifer thermal energy storage
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

Physics-guided deep reinforcement learning for optimized data center cooling and waste heat recovery utilizing aquifer thermal energy storage Yingbo Zhang a , Zixuan Wang a, Konstantin Filonenko c , Dominik Franjo Dominković c , Shengwei Wang a,b,* a Department of Building Environment and Energy Engineering, The Hong Kong Polytechnic University, Hong Kong b Research Institute for Smart Energy, The Hong Kong Polytechnic University, Hong Kong c Department of Applied Mathematics and Computer Science, Technical University of Denmark, Denmark
### Page 2

Nomenclature B Balance state R Reward AI Artificial intelligence BN Normalized balance state HPC High-performance computing a Coefficient for energy consumption term ATES Aquifer Thermal Energy Storage β Coefficient for balance term RL Reinforcement learning λ Scaling factor (kWh) DRL Deep reinforcement learning COP Coefficient of performance Subscripts PUE Power usage effectiveness sys System UPS Uninterruptible power supply t Time (h) MDP Markov Decision Process cool Cooling system DQN Deep Q network heat Heating system CCOP Coefficient of cooling system performance ATEScool Cooling load when using ATES cooling HCOP Coefficient of heating system performance ATESheat Heating load when using ATES heating E Energy consumption (kWh) diff ATES balance difference P Power consumption (kW) guide Guided function L Load (kW) IT IT equipment T Temperature (◦ C)
### Page 7

where Esys is the energy consumption of the system, measured in kWh; system; HCOP is the coefficient of heating performance of the heating system; LtATEScool denotes the cooling load of the data center at time t BATES is the balanced state of the ATES, which is dimensionless; λ is a scaling factor (with unit kWh) that ensures dimensional consistency when using ATES cooling; LtATESheat represents thermal energy delivered between the two terms and reflects the relative weight of the ATES by ATES to the heat pump evaporator at time t when using ATES heat­ balance in the objective function. ing; t = 1,2…,N denotes discrete time steps. The primary constraint for this optimization problem is that the N N N ∑ ∑ ∑ ATES system needs to achieve balance after one year of operation. Etsys = Etcool + Etheat (11) t=1 t=1 t=1 Additionally, for the free cooling operational mode, the outdoor wet bulb temperature must be below 13 ◦ C to effectively handle 100 % of the Ltcool cooling loads for the data center. This requirement constitutes an Etcool = ×t (12) CCOPt additional constraint.
### Page 7

N ∑ N ∑ ( ) 3.4.1. State space and action space simplification BtATES = LtATEScool − LtATESheat (14) In this reinforcement learning problem, the state is defined by vari­ 1 1 ables such as outdoor wet bulb temperature, cooling load, heating load, and hourly time progression throughout the year. The actions corre­ where Ecool is the electricity consumption for cooling of the data center; spond to the operational modes of the system, encompassing both Eheat is the electricity consumption for heating of the office building; Lcool heating and cooling modes. Typically, the cooling mode includes three is the cooling load of the data center; Lheat is the heating load of the office options: free cooling, ATES cooling, and chiller cooling. The heating building; CCOP is the coefficient of cooling performance of the cooling mode includes two options: electric heater and ATES heating. In
### Page 9

3.4.2.2. Components and structure of the reward function. The reward function is informed by domain knowledge and fundamental principles. For instance, it is common practice to initiate ATES cooling at the onset of summer, which serves as the initial state. As the summer progresses, the groundwater temperature rises due to cooling operations. During transitional seasons or winter, the system switches to heating the office building using groundwater via heat pumps, leveraging the higher groundwater temperature to achieve a relatively high COP value for the heating system. This continuous cooling/heating reward structure aligns with practical engineering requirements by minimizing system switching. The reward function consists of two components: an electricity consumption term, which represents the optimization objective, and an ATES balance term, which addresses the primary constraint of the problem. The reward function is structured as follows: N ∑ ⃒ ⃒ ⃒ ⃒ Rt = α* Etsys + β*⃒BNtdiff ⃒ (15) t=1
### Page 11

4. Results and discussion 3.5. Framework for DRL agent training and validation 4.1. Algorithm convergence analysis The training and evaluation framework for deep reinforcement learning (DRL) agents is elaborated in Fig. 3. The process begins with Fig. 4 compares the convergence performance of different rein­ training the DRL agents on the 2019 dataset, and comparing perfor­ forcement learning agents (DQN, D3QN, QRDQN, Double DQN, and mance across five DRL agents. Subsequently, the proposed control Dueling DQN) across 10 training runs with different initial random

## 公式/优化模型候选

### Page 1

```text
ventional systems. Additionally, system validation via Dymola simulations demonstrates that groundwater
                                                           temperatures return to initial conditions (±0.5 ◦ C) after annual cycling. The developed framework establishes a
                                                           generalizable methodology for AI-driven optimization of sustainable data center cooling systems integrated with
```
### Page 2

```text
HPC             High-performance computing                                             a         Coefficient for energy consumption term
   ATES            Aquifer Thermal Energy Storage                                         β         Coefficient for balance term
   RL              Reinforcement learning                                                 λ         Scaling factor (kWh)
```
### Page 2

```text
ATES            Aquifer Thermal Energy Storage                                         β         Coefficient for balance term
   RL              Reinforcement learning                                                 λ         Scaling factor (kWh)
   DRL             Deep reinforcement learning
```
### Page 4

```text
cations. To enhance energy efficiency, this system has undergone                           Total Facility Power EIT + Ecool + Eothers
                                                                                   PUE =                       =                                              (1)
energy-saving renovations and has been integrated into an energy sys­                      IT Equipment Power           EIT
```
### Page 4

```text
Scenario 2 (Fig. 2B): The data center has two cooling options: the use                  Lcool
                                                                                   CCOP =                                                                     (2)
of a chiller or the implementation of free cooling via a cooling tower.                     Pcool
```
### Page 4

```text
Scenario 4 (Fig. 2D): In this scenario, ATES is used for both cooling                   Lheat
and heating. In summer, cold water from the cold well supplies cooling             HCOP =                                                                     (3)
                                                                                            Pheat
```
### Page 5

```text
where Lheat is the heating load in kilowatts and Pheat is the power con­           [32]:
sumption of the office building in kilowatts.                                      Qtarget = r + γQ(sʹ, argmaxaʹ Q(sʹ, aʹ; θ) ; θ− )                               (6)
```
### Page 5

```text
3. Physics-guided deep reinforcement learning framework                            where arg maxaʹ Q(sʹ, aʹ; θ) denotes the action selection performed by the
                                                                                   online network with parameters θ; Q(sʹ, ⋅; θ− ) denotes the action evalu­
```
### Page 5

```text
online network with parameters θ; Q(sʹ, ⋅; θ− ) denotes the action evalu­
3.1. Algorithm selection and comparison                                            ation performed by the target network with parameters θ− . The online
                                                                                   network θ is responsible for proposing the best action in the next state sʹ,
```
### Page 5

```text
3.1. Algorithm selection and comparison                                            ation performed by the target network with parameters θ− . The online
                                                                                   network θ is responsible for proposing the best action in the next state sʹ,
    The selection of Deep Q-Networks (DQN) as the deep reinforcement               while the target network θ− provides a more stable estimate of the Q-
```
### Page 5

```text
network θ is responsible for proposing the best action in the next state sʹ,
    The selection of Deep Q-Networks (DQN) as the deep reinforcement               while the target network θ− provides a more stable estimate of the Q-
learning algorithm for this study is motivated by their demonstrated               value for that selected action, thereby reducing the overestimation bias
```
### Page 5

```text
1 ∑
                                                                                   Q(s, a) = V(s) + A(s, a) −        A(s, a )
                                                                                                                           ʹ                         (7)
```
### Page 5

```text
kov Decision Process (MDP) framework, defined by the                               where V(s) captures novel state value independent of actions; A(s, a)
tuple (S, A, P, R, γ) [31],                                                        measures relative action advantage; |A| is the cardinality of the action
   where: S represents the state space (system operating conditions); A            space. This decomposition allows the network to learn which states are
```
### Page 5

```text
probability of moving from state s to s’ given action a; R(s, a) is the            states.
reward received after taking action a in state s; γ is the discount factor,
γ ∈ [0,1], which balances immediate and future rewards.                            3.1.2.4. Quantile Regression DQN (QR-DQN). Quantile Regression DQN
```
### Page 6

```text
typical cooling system model for data centers using equipment-                               8
                                                                                             ∑ 760
                                                                                                               ⃒
```
### Page 6

```text
⃒
                                                                                                               ⃒ 8∑760
                                                                                                                              ⃒
```
### Page 6

```text
⃒              ⃒
measured data and typical control strategies. The energy efficiency for                 Min        Etsys + λ • ⃒       BtATES ⃒                            (10)
                                                                                                               ⃒              ⃒
```
### Page 6

```text
⃒              ⃒
cooling systems across various ambient temperatures, such as the                              t=1                 t=1
```
### Page 7

```text
system; LtATEScool denotes the cooling load of the data center at time t
BATES is the balanced state of the ATES, which is dimensionless; λ is a
scaling factor (with unit kWh) that ensures dimensional consistency                     when using ATES cooling; LtATESheat represents thermal energy delivered
```
### Page 7

```text
between the two terms and reflects the relative weight of the ATES                      by ATES to the heat pump evaporator at time t when using ATES heat­
balance in the objective function.                                                      ing; t = 1,2…,N denotes discrete time steps.
                                                                                            The primary constraint for this optimization problem is that the
```
### Page 7

```text
N               N                N
∑               ∑                ∑                                                      ATES system needs to achieve balance after one year of operation.
      Etsys =         Etcool +         Etheat                                (11)
```
### Page 7

```text
∑               ∑                ∑                                                      ATES system needs to achieve balance after one year of operation.
      Etsys =         Etcool +         Etheat                                (11)
t=1             t=1              t=1
```
### Page 7

```text
Etsys =         Etcool +         Etheat                                (11)
t=1             t=1              t=1
                                                                                        Additionally, for the free cooling operational mode, the outdoor wet
```
### Page 7

```text
Ltcool                                                                      cooling loads for the data center. This requirement constitutes an
Etcool =           ×t                                                        (12)
           CCOPt                                                                        additional constraint.
```
### Page 7

```text
Ltheat
Etheat =           ×t                                                        (13)       3.4. State-action-reward design
           HCOPt
```
### Page 7

```text
N
∑                 N
                  ∑ (                               )                                   3.4.1. State space and action space simplification
```
### Page 9

```text
N
                                                                                            ∑               ⃒        ⃒
                                                                                                            ⃒        ⃒
```
### Page 9

```text
⃒        ⃒
                                                                                  Rt = α*         Etsys + β*⃒BNtdiff ⃒                                  (15)
                                                                                            t=1
```
### Page 10

```text
minus a guiding function.                                                                              followed by heating operations. The processing of the period of the sine
BNtdiff = BNtATES − BNtguide                                                               (16)        function is to make its half period exactly 8760 h.
```
### Page 10

```text
8
                                 ∑ 760                 8
                                                       ∑ 760
```
### Page 10

```text
∑ 760                 8
                                                       ∑ 760
BNtATES = BtATES       Max               LATEScool ,           LATESheat                   (17)        cess employed a sophisticated neural network architecture consisting of
```
### Page 10

```text
∑ 760
BNtATES = BtATES       Max               LATEScool ,           LATESheat                   (17)        cess employed a sophisticated neural network architecture consisting of
                                  1                     1
```
### Page 10

```text
dueling streams for value and advantage estimation. The agent was
BNtguide = sin(2*π *t/17520)                                                               (18)
                                                                                                       trained for 100 episodes totaling 876,000 timesteps using minibatch
```
### Page 10

```text
gradient descent, with the loss function between the temporal difference
where Rt is the reward at time t; The parameters α and β control the
                                                                                                       target and current Q-values. Dynamic exploration is implemented
```
### Page 10

```text
through a call-back mechanism that exponentially decays the explora­
that all rewards have equal importance, we set α = 1 and β = 105. The
                                                                                                       tion rate after each completed episode, facilitating a smooth transition
```
### Page 10

```text
balance stable convergence with efficient learning, while a replay buffer
between actual and guiding function. Therefore, β = 105 is selected to
                                                                                                       size of 100,000 transitions ensures sufficient experience diversity for
```
### Page 12

```text
from − 20 % to +24 %. Similarly, Dueling DQN agent shows worse
performance, typically maintaining imbalances within ±20 % after one                 Fig. 10 presents a comparative analysis of energy consumption per­
year of operation.                                                               formance through box plot visualization for different DRL agents (DQN,
```

## 符号表/变量定义候选

### Page 2

```text
Nomenclature                                                                           B         Balance state
                                                                                          R         Reward
   AI              Artificial intelligence                                                BN        Normalized balance state
   HPC             High-performance computing                                             a         Coefficient for energy consumption term
   ATES            Aquifer Thermal Energy Storage                                         β         Coefficient for balance term
   RL              Reinforcement learning                                                 λ         Scaling factor (kWh)
   DRL             Deep reinforcement learning
   COP             Coefficient of performance                                             Subscripts
   PUE             Power usage effectiveness                                              sys        System
   UPS             Uninterruptible power supply                                           t          Time (h)
   MDP             Markov Decision Process                                                cool       Cooling system
   DQN             Deep Q network                                                         heat       Heating system
   CCOP            Coefficient of cooling system performance                              ATEScool Cooling load when using ATES cooling
   HCOP            Coefficient of heating system performance                              ATESheat Heating load when using ATES heating
   E               Energy consumption (kWh)                                               diff       ATES balance difference
   P               Power consumption (kW)                                                 guide      Guided function
   L               Load (kW)                                                              IT         IT equipment
   T               Temperature (◦ C)
                  Fig. 1. Estimated data center electricity consumption and its share in total electricity demand in selected regions in 2022 and 2026 [2].
enormous computational demand [3] is expected to further exacerbate                       implemented using both air-cooled and liquid-cooled systems. There
the increase in cooling energy consumption [4]. Enhancing the sus­                        have been some successful applications for waste heat recovery from air-
tainability of cooling technologies is imperative to mitigate their envi­                 cooled data centers. For example, Chen et al. conducted experimental
ronmental impact and improve overall energy efficiency.                                   research and energy-saving analysis of an air-cooled data center for
                                                                                          waste heat recovery [13]. They found that the proposed system can save
1.2. Waste heat recovery opportunities in data centers                                    152.7 MWh of electricity, 56.4 tons of standard coal, and 244.7 tons of
                                                                                          CO2 emissions in Beijing annually. Waste heat from liquid-cooled data
    Existing studies on data center cooling systems primarily focus on                    centers typically exhibits higher energy efficiency due to the higher-
improving cooling efficiency and developing innovative cooling tech­                      grade waste heat they produce. A study [14] demonstrated that chip
nologies [5]. To enhance cooling efficiency, strategies often involve                     cooling technology could yield waste heat in the form of water at tem­
maximizing the use of free cooling [6], optimizing system design and                      peratures around 45 ◦ C or even higher. The waste heat temperature
control [7], and advocating for higher operating temperatures within                      range is consistent with the operating temperature range of certain low-
data centers [8]. The development of novel cooling technologies, such as                  temperature building heating systems [15]. For instance, as early as
two-phase liquid cooling technology [9] or immersion cooling [10],                        2010, IBM implemented direct waste heat utilization from liquid-cooled
offers higher cooling efficiency and can significantly reduce the cooling                 supercomputers, showcasing the potential for energy recovery [16]. In
energy footprint of data centers.                                                         2013, a German air-cooled data center was converted into a liquid-
    Beyond improving the energy efficiency and performance of cooling                     cooled facility, incorporating waste heat recovery systems. The upgra­
technologies, integrating data center cooling systems into broader en­                    ded system enabled the use of waste heat for powering an adsorption
ergy systems presents a promising opportunity to mitigate environ­                        chiller, thereby enhancing energy efficiency [17]. In 2016, Davies et al.
mental impact [11]. This integration transforms data centers from mere                    investigated the utilization of data centers for combined heating and
energy consumers to active prosumers [12], capable of contributing to                     cooling in London. Their findings revealed that a 3.5 MW data center
energy systems through waste heat recovery. The waste heat generated                      could lead to savings of over 4000 tons of CO2e and nearly £1 million per
by data centers serves as a valuable thermal resource for various ap­                     annum [18]. In 2023, the latest update to the EU Energy Efficiency
plications, such as building heating systems.                                             Directive highlights and promotes the reuse of waste heat from data
    Waste heat recovery from data centers can be effectively                              centers, indicating that policymakers are now taking action as well [19].
                                                                                      2
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
