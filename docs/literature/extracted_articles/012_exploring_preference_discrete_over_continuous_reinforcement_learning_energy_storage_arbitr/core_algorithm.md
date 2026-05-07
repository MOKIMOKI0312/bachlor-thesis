# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2024_Jeong_Exploring_the_Preference_for_Discrete_over_Continuous_Reinforcement_Lear.pdf`
- 标题：Exploring the Preference for Discrete over Continuous Reinforcement Learning in Energy Storage Arbitrage
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 3

2.1. Traditional Optimization-Based Energy Arbitrage Traditional optimization techniques, such as linear programming [7], mixed-integer linear programming [19], and dynamic programming [20], have been widely used to solve energy arbitrage problems by optimizing the charging and discharging schedules of ESSs. These methods provide optimal solutions in well-defined environments, but struggle to adapt to the high variability and uncertainty of real-time energy markets. Although effective under deterministic conditions, they require detailed system models, which can be computationally expensive and may not respond well to sudden market changes. Despite these limitations, traditional optimization approaches have laid a solid foundation for energy arbitrage and are still used as benchmark methods in the field. Furthermore, using stochastic dynamic programming, a form of stochastic optimization, can partially address the uncertainty challenges when solving the energy arbitrage problem [21]. However, with the growing complexity and uncertainty in energy systems due to increased distributed energy resources, traditional optimization methods face significant challenges.
### Page 4

3. Methods In this section, we present the methodologies used to approach the energy arbitrage problem using both discrete and continuous RL strategies. We first describe the energy arbi- trage problem and the battery model employed, followed by the specific implementations of the discrete RL and continuous RL methods. Although this paper focuses on batteries, other types of ESS, such as thermal storage systems, can be effectively modeled as well [23].
### Page 4

3.1. Energy Arbitrage and Battery Model The overall system model shown in Figure 1a mainly consists of the battery and the real-time energy market. The model to calculate the profit at time t can be expressed as
### Page 5

(a) (b) Figure 1. System models.(a) Energy storage arbitrage process. (b) Steady-state battery cell equivalent circuit.
### Page 5

Since there are the charging and discharging efficiencies, denoted by ηtc and ηtd , re- spectively, all charging power cannot be stored in the battery, and all discharging power cannot be sold to the real-time market. To calculate the ηtc and ηtd , a steady-state equivalent electrical circuit of the lithium ion battery cell shown in Figure 1b can be used [24]. The circuit consists of an open circuit voltage, voc s ts tl t , and series resistors, Rt , Rt , and Rt , which ts represent ohmic losses, charge transfer, and membrane diffusion, respectively. Rt and Rtlt are each connected in parallel with a capacitor, but for simplicity SoC is treated as constant within one time slot, which makes direct current during the time duration and enables ignoring of the capacitors [25]. The open circuit voltage, voc s ts tl t , and the three resistors, Rt , Rt , and Rt , are determined by the battery SoC at time slot t, denoted by SoCt , where the relations are described as −a1 SoCt voc t = a0 e + a2 + a3 SoCt − a4 (SoCt )2 + a5 (SoCt )3 , (2a) Rst = b0 e−b1 SoCt + b2 + b3 SoCt − b4 (SoCt )2 + b5 (SoCt )3 , (2b) −c1 SoCt Rts t = c0 e + c2 , (2c) tl −e1 SoCt Rt = e0 e + e2 , (2d) Rt = Rst + Rts tl t + Rt , (2e)
### Page 5

where all Fraktur typefaces in the equations are constant battery cell parameters. Then, icell t can be obtained by solving the following quadratic equations,   Ncell · voc · icell + icell 2 · Rt , if Pt < 0 (charging),   
### Page 5

where Ncell is the number of battery cells. The charging efficiency, ηtc , is determined by the ratio of the absorbing power of the voltage source and the charging power. Likewise, the discharging efficiency, ηtd , is determined by the ratio of the discharging power and the supplying power of the voltage source. Then, ηtc and ηtd are given by
### Page 6

where Emax is a total battery capacity. In general, the efficiency of battery lies in [0.96, 0.995] and becomes high for high SoC and low charging/discharging power. When determining Pt , the charging and discharging power limitations, denoted by Ptmin and Ptmax , should be examined first, and are determined by the SoCt . Battery degradation is known to be severe at both ends of the SoC, which implies that SoCt should be constrained as SoCmin ≤ SoCt ≤ SoCmax . Then, Ptmin and Ptmax are determined by the following equations: Pt SoCmax = SoCt − ηtc ∆t, when Pt = Ptmin (charging limitation), (6a) Emax 1 Pt SoCmin = SoCt − d ∆t, when Pt = Ptmax (discharging limitation). (6b) ηt Emax
### Page 6

3.2. Discrete RL Method: Deep Q-Network (DQN) We first explore discrete RL. One of the most widely used algorithms in discrete RL is the deep Q-network (DQN) [8]. DQN combines the traditional Q-learning algorithm with deep neural networks, allowing it to efficiently learn in environments with large state spaces. DQN uses a neural network to approximate Q-values, outputting the Q-values for all possible actions given the current state. The action with the highest Q-value is then selected. Additionally, DQN introduces two key techniques—experience replay and the target network—to improve the stability of learning. Let Qω (st , at ) be the action-value function when taking action at in state st , where the parameter ω represents the weights of the neural network used to approximate the Q-function. The loss function, LQ (ω ), is then defined as the mean squared error (MSE) between the predicted Q-value and the target Q-value, which is computed as:
### Page 7

State Q-value for each action Fully-charged Select the action Agent Idle with the largest Q-value within the constraints. Fully-discharged energy price SoC
### Page 8

Due to this issue, constrained RL is often employed when controlling ESSs with continuous RL [16–18]. In constrained RL, an additional condition is imposed to ensure that the action values remain within the range of Ptmin and Ptmax for every time step t [14]. This means that the agent must not only learn to maximize the cumulative reward but also satisfy the imposed constraints. Given that the constraint in this study was limited to maintaining the SoC within a defined range, we selected the Lagrangian multiplier method due to its simplicity and effectiveness in handling this specific requirement [15]. The Lagrangian multiplier effectively penalizes the agent whenever the action exceeds the allowable bounds, providing a penalty to the reward proportionate to the extent to which the constraints are violated. When applying constrained RL to our model, the reward function is modified accordingly. In addition to maximizing the original reward from energy arbitrage, the agent receives a penalty when the action value exceeds the Ptmin or Ptmax . This adjustment to the reward structure ensures that the agent learns to operate within the allowable charge and discharge rates while optimizing its long-term performance in terms of cumulative reward. The modified reward function in our model, denoted by rtc , is expressed as follows.
### Page 9

Now, we explore continuous RL, where the most fundamental algorithm is advantage actor–critic (A2C) [8]. A2C is a policy gradient-based method that separates the decision- making process into two components: the actor and the critic. The actor is responsible for selecting actions based on the current policy, while the critic evaluates the performance of the actor’s actions by estimating the value function. A2C introduces the concept of advantage, which measures how much better an action is compared with the average action taken from a given state. The objective of A2C is to maximize the advantage of the actions chosen by the actor. The critic helps stabilize the training by providing feedback to the actor, ensuring that the agent learns more efficiently in environments with continuous action spaces. This separation of roles allows A2C to handle more complex environments and policies compared with traditional value-based methods. Let πθ ( at |st ) be the probability density of taking action at in state st with parameter θ, which is learned by the actor. Also, let Vθ (st ) be the state-value function in state st approximated by parameter θ, which is learned by the critic. Note that parameter θ is shared between the actor and the critic since the inputs include only the state. The actor loss function, Jπ (θ ), and the critic loss function, LV (θ ), are then defined as follows:
### Page 13

150 175 Energy Price ($/MWh) Charging/Discharging Energy in Battery (MWh) Stored Energy in Battery(MWh) 150 100
### Page 13

(a) Continuous RL (λ = 0). 150 175 Energy Price ($/MWh) Charging/Discharging Energy in Battery (MWh) Stored Energy in Battery(MWh) 150 100
### Page 13

(b) Continuous RL (λ = 1). 150 175 Energy Price ($/MWh) Charging/Discharging Energy in Battery (MWh) Stored Energy in Battery(MWh) 150 100
### Page 13

(c) Continuous RL (λ = 0.1). 150 175 Energy Price ($/MWh) Charging/Discharging Energy in Battery (MWh) Stored Energy in Battery(MWh) 150 100 Energy Amount [MWh] Energy Price ($/MWh)
### Page 13

Figure 5. The charging/discharging results for four cases (green bar represents electricity prices; the red curve with the right axis represents the charging(−)/discharging(+) actions; the violet curve and filling represent the SoC; and the black line represents the minimum/maximum stored energy).
### Page 14

While reaching fully charged or discharged states may not always be ideal, our results suggest that this approach is generally beneficial. Reflecting these benefits, other studies using discrete RL have also included fully charged or discharged states within the action space [4,11–13]. However, concerns may arise about its tendency to perform full charge and discharge cycles, potentially overusing the ESS and accelerating its degradation. Since frequent charge/discharge cycles shorten the ESS lifespan, it is essential to examine the cumulative charge and discharge volumes over the entire dataset. Figure 8 presents these findings. Contrary to expectations, continuous RL with λ = 0.1 had the highest cumulative ESS usage, followed by discrete RL, with continuous RL using λ = 1 closely behind. When λ = 1, the charge/discharge volume was only 18% lower than when λ = 0.1, yet the profit was reduced by 36%, indicating that the policy with λ = 1 was overly conservative. The reason discrete RL did not have the highest usage is that it often opted for idle actions instead of smaller charge or discharge operations. In real-world energy arbitrage applications, it would be necessary to impose constraints on ESS charge/discharge volumes to avoid excessive wear. As shown in Figure 8, the lifespan impact of discrete RL is comparable to that of continuous RL, indicating that the performance advantage of discrete RL does not come at the cost of increased ESS degradation.
### Page 16

ESS Energy storage system SoC State of charge RL Reinforcement learning DQN Deep Q-network A2C Advantage actor–critic PPO Proximal policy optimization TinyML Tiny machine learning

## 公式/优化模型候选

### Page 4

```text
rt = ct · Pt · ∆t,                                   (1)
```
### Page 5

```text
Since there are the charging and discharging efficiencies, denoted by ηtc and ηtd , re-
                          spectively, all charging power cannot be stored in the battery, and all discharging power
```
### Page 5

```text
spectively, all charging power cannot be stored in the battery, and all discharging power
                          cannot be sold to the real-time market. To calculate the ηtc and ηtd , a steady-state equivalent
                          electrical circuit of the lithium ion battery cell shown in Figure 1b can be used [24]. The
```
### Page 5

```text
voc
                                                t = a0 e          + a2 + a3 SoCt − a4 (SoCt )2 + a5 (SoCt )3 ,                                    (2a)
                                                Rst = b0 e−b1 SoCt + b2 + b3 SoCt − b4 (SoCt )2 + b5 (SoCt )3 ,                                   (2b)
```
### Page 5

```text
t = a0 e          + a2 + a3 SoCt − a4 (SoCt )2 + a5 (SoCt )3 ,                                    (2a)
                                                Rst = b0 e−b1 SoCt + b2 + b3 SoCt − b4 (SoCt )2 + b5 (SoCt )3 ,                                   (2b)
                                                         −c1 SoCt
```
### Page 5

```text
Rts
                                                t = c0 e          + c2 ,                                                                          (2c)
                                                tl       −e1 SoCt
```
### Page 5

```text
tl       −e1 SoCt
                                               Rt = e0 e          + e2 ,                                                                         (2d)
                                                Rt = Rst + Rts   tl
```
### Page 5

```text
Rt = e0 e          + e2 ,                                                                         (2d)
                                                Rt = Rst + Rts   tl
                                                            t + Rt ,                                                                              (2e)
```
### Page 5

```text
Pt =            t     t       t
                                                                                                                    (3)
```
### Page 6

```text

                                                    SoCt − η c Pt ∆t, if Pt < 0 (charging),
                                                                t Emax
```
### Page 6

```text
t Emax
                                           SoCt+1 =                Pt                                                     (5)
                                                    SoCt − 1d Emax    ∆t, if Pt ≥ 0 (discharging),
```
### Page 6

```text
SoCt+1 =                Pt                                                     (5)
                                                    SoCt − 1d Emax    ∆t, if Pt ≥ 0 (discharging),
                                                                    ηt
```
### Page 6

```text
be severe at both ends of the SoC, which implies that SoCt should be constrained as
                          SoCmin ≤ SoCt ≤ SoCmax . Then, Ptmin and Ptmax are determined by the following equations:
                                                            Pt
```
### Page 6

```text
Pt
                                    SoCmax = SoCt − ηtc   ∆t,            when Pt = Ptmin (charging limitation),         (6a)
                                                     Emax
```
### Page 6

```text
1 Pt
                                   SoCmin = SoCt − d      ∆t,            when Pt = Ptmax (discharging limitation).      (6b)
                                                  ηt Emax
```
### Page 6

```text
SoCmin = SoCt − d      ∆t,            when Pt = Ptmax (discharging limitation).      (6b)
                                                  ηt Emax
```
### Page 6

```text
ot =(ct−1 , SoCt ),                                       (7a)
                                                              st =(o0 , o1 , · · · , ot−1 , ot ).                       (7b)
```
### Page 7

```text
                                                2 
                                      LQ (ω ) = E(st ,at ,rt ,st+1 )∼ D        rt + γ max Qω − (st+1 , a) − Qω (st , at )                    (9)
                                                                                         a
```
### Page 7

```text
where γ is the discount factor that determines the importance of future rewards, D is the
                          replay buffer, and ω − is the parameters of the target network.
```
### Page 7

```text
where γ is the discount factor that determines the importance of future rewards, D is the
                          replay buffer, and ω − is the parameters of the target network.
                               To apply DQN to the energy arbitrage problem, it is necessary to discretize the action
```
### Page 8

```text
rtc = ct · Pt · ∆t − λ| at − Pt |.                         (10)
```
### Page 9

```text
preventing the learning stagnation that can occur when constraints are ignored. A critical
                          point in this approach is the proper tuning of the Lagrangian multiplier, λ [26]. If λ is
                          too large, the agent may focus excessively on satisfying the constraints at the expense
```
### Page 9

```text
too large, the agent may focus excessively on satisfying the constraints at the expense
                          of maximizing the cumulative reward. Conversely, if λ is too small, the constraints may
                          become insignificant, allowing the agent to frequently violate them. Therefore, it is essential
```
### Page 9

```text
become insignificant, allowing the agent to frequently violate them. Therefore, it is essential
                          to find an appropriate balance for λ to ensure the agent optimizes its policy while adhering
                          to the system’s operational limits.
```
### Page 9

```text
Clipped to 75%
                                             with a negative reward of λ·(-5)%
```
### Page 9

```text
spaces. This separation of roles allows A2C to handle more complex environments and
                          policies compared with traditional value-based methods. Let πθ ( at |st ) be the probability
                          density of taking action at in state st with parameter θ, which is learned by the actor. Also,
```
### Page 9

```text
policies compared with traditional value-based methods. Let πθ ( at |st ) be the probability
                          density of taking action at in state st with parameter θ, which is learned by the actor. Also,
                          let Vθ (st ) be the state-value function in state st approximated by parameter θ, which is
```
### Page 9

```text
density of taking action at in state st with parameter θ, which is learned by the actor. Also,
                          let Vθ (st ) be the state-value function in state st approximated by parameter θ, which is
                          learned by the critic. Note that parameter θ is shared between the actor and the critic since
```
### Page 9

```text
let Vθ (st ) be the state-value function in state st approximated by parameter θ, which is
                          learned by the critic. Note that parameter θ is shared between the actor and the critic since
                          the inputs include only the state. The actor loss function, Jπ (θ ), and the critic loss function,
```
### Page 10

```text
to further stabilize the learning process, the policy update can be clipped within a range
                          of 1 ± ϵ, preventing excessively large policy changes during training. This clipping mech-
                          anism ensures that the updates are constrained, reducing the likelihood of destabilizing
```
### Page 10

```text
methods. For the continuous RL approach, we experimented with three different values of
                          the Lagrangian multiplier, λ: a very small value (λ = 0), a very large value (λ = 1), and the
                          most appropriate value (λ = 0.1). The value of λ = 0.1 was selected based on empirical
```
### Page 10

```text
the Lagrangian multiplier, λ: a very small value (λ = 0), a very large value (λ = 1), and the
                          most appropriate value (λ = 0.1). The value of λ = 0.1 was selected based on empirical
                          results showing the best performance during testing. We demonstrated the effectiveness
```
### Page 11

```text
conducted using a 100 MWh battery, with the SoC at time slot t = 0 initialized to 0.5,
                          representing 50% of the battery’s capacity. To prevent battery degradation, the SoCmin and
```
### Page 11

```text
Learning rate                                     0.001
                                            Discount factor (γ)                                  0.99
                                        Minibatch size (discrete RL)                              32
```
### Page 11

```text
results. The findings show that selecting an appropriate value for the Lagrangian multiplier
                          (λ = 0.1) in continuous RL maximizes profits, as opposed to using values that are either
                          too small (λ = 0) or too large (λ = 1). However, regardless of the λ value chosen, discrete
```
### Page 11

```text
(λ = 0.1) in continuous RL maximizes profits, as opposed to using values that are either
                          too small (λ = 0) or too large (λ = 1). However, regardless of the λ value chosen, discrete
                          RL outperformed continuous RL in terms of profitability. Although it might be expected
```
### Page 11

```text
30 min Averaged Profit (USD)
                                          Continuous RL (λ = 0)                               5.369
                                          Continuous RL (λ = 1)                              14.569
```
### Page 11

```text
Continuous RL (λ = 0)                               5.369
                                          Continuous RL (λ = 1)                              14.569
                                         Continuous RL (λ = 0.1)                             22.823
```
### Page 11

```text
Continuous RL (λ = 1)                              14.569
                                         Continuous RL (λ = 0.1)                             22.823
                                               Discrete RL                                   32.392
```
### Page 12

```text
range can increase arbitrage profits, though these limits should be set carefully to minimize
                          battery degradation. In the case of continuous RL with λ = 0, the model quickly discharges
                          all the initially stored energy and takes no further actions, effectively missing out on
```
### Page 12

```text
actions, charging when prices are low and discharging when prices are high. For continuous
                          RL with λ = 1, the agent’s actions are overly conservative, avoiding states where the
                          SoC approaches its minimum or maximum limits. This results in suboptimal utilization
```
### Page 12

```text
of the energy storage system (ESS), as the model fails to engage in aggressive energy
                          arbitrage. Setting λ to 0.1 was found to provide an optimal balance between energy
                          arbitrage opportunities and SoC boundary constraints. This value allows the model to
```
### Page 12

```text
Paradoxically, this limitation appears to lead to more efficient utilization of the ESS for
                          energy arbitrage. The optimal λ = 0.1 in continuous RL still struggles with fully leveraging
                          the ESS due to the constraint imposed by the penalty mechanism, while discrete RL,
```
### Page 12

```text
The cumulative profits of all methods over the entire test set are shown in Figure 6.
                          In the case of continuous RL with λ = 0, the model initially achieves high profits by
                          discharging and selling the all stored energy, but it fails to recharge and take further
```
### Page 12

```text
remaining three models continue to generate profits steadily throughout the test period.
                          When λ = 0.1, the model effectively balances immediate profit opportunities with SoC
                          constraints, unlike λ = 0, which overly emphasizes short-term gains, or λ = 1, which
```
### Page 12

```text
When λ = 0.1, the model effectively balances immediate profit opportunities with SoC
                          constraints, unlike λ = 0, which overly emphasizes short-term gains, or λ = 1, which
                          limits arbitrage potential by overly restricting charge and discharge actions. Once again,
```
### Page 13

```text
(a) Continuous RL (λ = 0).
                                                                                                                                                               150
```
### Page 13

```text
(b) Continuous RL (λ = 1).
                                                                                                                                                               150
```
### Page 13

```text
(c) Continuous RL (λ = 0.1).
                                                                                                                                                               150
```
### Page 14

```text
20        Continuous RL ( =0)
                                                                       Continuous RL ( =1)
```
### Page 14

```text
Cumulative Revenue [k$]
                                                                       Continuous RL ( =0.1)
                                                             15        Discrete RL
```
### Page 14

```text
1.0       Continuous RL ( =0)
                          Cumulative Distribution Function
```
### Page 14

```text
Continuous RL ( =1)
                                                             0.8       Continuous RL ( =0.1)
```
### Page 14

```text
Continuous RL ( =1)
                                                             0.8       Continuous RL ( =0.1)
                                                                       Discrete RL
```
### Page 14

```text
cumulative charge and discharge volumes over the entire dataset. Figure 8 presents these
                          findings. Contrary to expectations, continuous RL with λ = 0.1 had the highest cumulative
                          ESS usage, followed by discrete RL, with continuous RL using λ = 1 closely behind.
```
### Page 14

```text
findings. Contrary to expectations, continuous RL with λ = 0.1 had the highest cumulative
                          ESS usage, followed by discrete RL, with continuous RL using λ = 1 closely behind.
                          When λ = 1, the charge/discharge volume was only 18% lower than when λ = 0.1,
```
### Page 14

```text
ESS usage, followed by discrete RL, with continuous RL using λ = 1 closely behind.
                          When λ = 1, the charge/discharge volume was only 18% lower than when λ = 0.1,
                          yet the profit was reduced by 36%, indicating that the policy with λ = 1 was overly
```
### Page 15

```text
Cumulative Charge/Discharge Energy [MWh]
                                                                                Continuous RL ( =0)
                                                                     2500       Continuous RL ( =1)
```
### Page 15

```text
Continuous RL ( =0)
                                                                     2500       Continuous RL ( =1)
                                                                                Continuous RL ( =0.1)
```
### Page 15

```text
2500       Continuous RL ( =1)
                                                                                Continuous RL ( =0.1)
                                                                     2000       Discrete RL
```

## 符号表/变量定义候选

未发现明确 Nomenclature/Acronyms 段。

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
