# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2024_Guo_Optimal_dynamic_thermal_management_for_data_center_via_soft_actor_critic.pdf`
- 标题：Optimal dynamic thermal management for data center via soft actor-critic algorithm with dynamic control interval and combined-value state space
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

Optimal dynamic thermal management for data center via soft actor-critic algorithm with dynamic control interval and combined-value state space Yuxiang Guo a , Shengli Qu a , Chuang Wang a, * , Ziwen Xing a , Kaiwen Duan b a School of Energy and Power Engineering, Xi’an Jiaotong University, Xi’an 710049, China b Zhongxing Telecommunication Equipment Corporation, Shenzhen 518055, China
### Page 1

• The DRL control framework is established, wherein experimentation is conducted using the simulation model. • Utilizing SAC addresses traditional method limitations in data center thermal management. • SAC outperforms PID, MPC, TRPO, PPO and DQN algorithms, affirming its efficacy in thermal management. • DCI-SAC enables dynamic control interval adjustments, exploring greater energy-saving potential. • Novel reward function item and combined-state space can improve energy efficiency and stability.
### Page 4

2.2. Fundamental problems addressed by DRL agent ∫t1 [ ] [ ] (min) ψ = β0 PUE + β1 Tchip,up,τ − Tchip,up + + β1 Tchip,down,τ − Tchip,down + dτ The algorithms embedded within the DRL agent are meticulously designed to prioritize energy efficiency, with the ultimate goal of t0
### Page 4

generating optimal policies to regulate the experimental platform. The initialization of the system entails training the DRL-based algorithms s.t.fct ≤ fct,set ≤ fct within the agent, a process akin to crafting specific Deep Neural Net- works (DNNs). However, once the training phase reaches fruition, the Sp,1 ≤ Sp,1,set ≤ Sp,1 DRL agent becomes adept at furnishing tailored optimal control policies for the respective systems [41]. Sp,2 ≤ Sp,2,set ≤ Sp,2 (1) In this endeavor, the fundamental objective of the DRL agent is to minimize power usage effectiveness (PUE) while simultaneously avert- where [t0,t1] is the optimized time range, [x]+ represents max(x,0), ing overheating in each chip shell temperature. Consequently, the core Tchip, up represents upstream chips and Tchip, down represents downstream optimization problem faced by the DRL agent can be formulated as chips. The term fct stands for cooling tower fan frequency, Sp,1 represents represented by Eq. (1).
### Page 5

In this experimental setup, Q replaces Pit to denote IT equipment 3.2. SAC algorithm power consumption. The cooling equipment power consumption, Pcool, is calculated as the sum of Pct, Pp,1, Pp,2, which represent the power In this study, the Soft Actor-Critic (SAC) was employed as the RL consumption of cooling tower, primary-side water pump and secondary- control algorithm, leveraging its two key features: the off-policy method side water pump, respectively. The terms in Eq. (1) correspond to pen- and the maximum entropy objective [48]. The off-policy method en- alties for overheating in upstream and downstream chips, with β0 and β1 hances data efficiency by utilizing a replay buffer, while the maximum serving as weight factors for these penalties. In addition, limits are entropy objective promotes more exploratory learned strategies. This imposed on three indirect control setpoints within their reasonable approach fosters diversity during training, mitigating the risk of the ranges. The detailed DRL agent algorithm is introduced in Section 3 and algorithm getting trapped in local optima and consequently improving the description and tuning of the parameters are introduced in Appendix overall stability [25]. The objective in SAC is formulated as Eq. (4). D. ∑ J(π) = E(st ,at )∼ρπ γ t [r(st , at ) + αH(π(⋅ |st )] (4) 3. Proposed RL approach t
### Page 8

Fig. 7. Architecture of Actor-Critic in DCI-SAC and formulas for different state variables in different state space representations
### Page 10

In this section, the effectiveness of the proposed RL approach for optimizing data center systems was evaluated through a comprehensive set of simulation experiments categorized into two groups. The first group validates the performance of the RL method in a continuous ac- tion space for data center control by comparing the SAC algorithm with a series of baseline algorithms. The second group assesses the perfor- mance of the proposed DCI-SAC algorithm with a fixed control time interval, while varying the representations of the state space- —considering both the final-value and the combined-value. This multi- faceted evaluation aims to demonstrate the effectiveness of the DCI-SAC algorithm and explore the impact of novel state space representations on its overall performance.
### Page 10

In this study, a meticulous analysis of the impact resulting from variations in the algorithmic form, control time interval, and state space form within specific granularity scenarios was conducted. Temperature limits for both upstream and downstream chips are set at 55 ◦ C and 60 ◦ C, respectively. Considering granular application scenarios, the agent was trained with real environmental temperature, relative humidity, Fig. 9. Learning curves for different algorithms.
### Page 12

Fig. 11. Box plot of upstream and downstream chip temperatures for different algorithms. The result shown here is from the optimal random seed.
### Page 15

Fig. 13. Learning curves for SAC algorithm with the same state space form and different control time interval.
### Page 16

Fig. 14. Real-time PUE for SAC algorithm with the same state space form and different control time interval.
### Page 17

Fig. 16. Learning curves for SAC algorithm with the same control time interval and different state space form.
### Page 18

Fig. 17. Real-time PUE for SAC algorithm with the same control time interval and different state space form. It’s worth noting that the results in Fig. 17 are entirely identical to those presented in Fig. 14, with the only distinction lying in the arrangement mode.
### Page 20

Model Predictive Control (MPC) is a nuanced and systematic control strategy that serves as an effective baseline for various applications. Its core principle involves the calculation of an optimal control sequence, predicting the system’s future behavior within a predefined time horizon at each discrete time step. In its operational process, MPC iteratively formulates an optimal control sequence at each time step by forecasting the system’s trajectory over the specified time horizon. The chosen control action for the current moment is then selected from this sequence. This sequential decision-making process continues for subsequent time steps, ensuring adaptability to the evolving system dynamics. The overall MPC process is visually depicted in Fig. C.1.
### Page 20

In the context of model predictive control, the choice of the time horizon holds increased significance, represented as “nΔt” in Fig. C.1. Furthermore, the implementation of the entire algorithm necessitates the configuration of specific hyperparameters for the genetic algorithm, as detailed in Table C.1.
### Page 20

To ensure the optimal performance of both the proposed and utilized reinforcement learning algorithms’ architectures, hyperparameter tuning is essential. Four types of hyperparameters need to be tuned: common hyperparameters, hyperparameters of the basic reward function, and hyper- parameters of the proposed reward function item. Due to the tuning of the reward function hyperparameters, the reward values are not consistent. Therefore, in this section, the system’s average PUE under test conditions, and the standard deviation of the upstream chip temperatures (Vu) and downstream chip temperatures (Vd) are used as the performance results for each set of hyperparameters. The average PUE represents the energy efficiency of the system, with lower values indicating better efficiency and less wasted energy. The standard deviations of the upstream and down- stream chip temperatures, Vu and Vd respectively, reflect the stability of the thermal environment within the system. Lower values of Vu and Vd suggest more uniform temperature distribution and better thermal management, which are critical for maintaining the reliability and longevity of the chips. Together, these metrics provide a comprehensive assessment of the algorithm’s effectiveness in optimizing both energy efficiency and thermal sta- bility. All results are obtained under 10 different random seeds (0–9).
### Page 21

Among the common hyperparameters in reinforcement learning training, batch size and the number of neurons per layer in the neural network are the most critical to tune (many studies have shown that setting the number of layers to 2 is the most common choice [6,26]). Therefore, in this paper, we optimize the batch size and the number of neurons in the two-layer neural network. The range for the batch size is 32, 64, 128, and 256 and the range for the number of neurons is 64, 128, and 256. The optimization results for batch size are presented in Table D.1. It is evident that, for DQN and SAC, a batch size of 64 demonstrates superior performance, whereas PPO and TRPO perform optimally with a batch size of 256. Regarding the optimization of the number of units in the two-layer neural network, as indicated in Table D.2, PPO exhibits optimal performance with 64 neurons in each layer. For the remaining algorithms, optimal performance is achieved with 128 neurons in the first layer and 64 neurons in the second layer. However, the results suggest that variations in the number of neurons do not significantly impact the algorithms’ performance.
### Page 21

Table D.2 The optimization of the number of units in the two-layer neural network.
### Page 21

According to Eq. (1), the basic reward function has three hyperparameters: β0, β1, and r0. Among these, β0 and r0 do not need to be adjusted because they merely scale the reward function. β1 represents the influence of the chip temperature exceeding the safe range and the proportion of the system’s PUE in the reward value (the actual proportions are β1 / (β0 + β1) and β0 / (β0 + β1), but by fixing β0, adjusting β1 changes the respective proportion). Therefore, only β1 is adjusted here, with chosen values of 0.1, 0.2, and 0.4. The optimization results are shown in Table D.3. It can be observed that excessively high values of β1 tend to prioritize PUE excessively while slightly neglecting the control of chip temperature, whereas excessively low values of β1 exhibit the opposite effect. Therefore, selecting a moderate value of 0.2 for β1 can effectively balance the relationship between the two aspects.
### Page 22

According to Eq. (4) and (15), μ0 represents the proportion of gradual and sudden changes in state variables within the reward function item (μ1 is not considered because μ1 is always equal to 1-μ0). Therefore, optimizing μ0 can determine the impact of different proportions of these two factors on system performance. The results are shown in Table D.4. According to Eq. (16), β2 represents the proportional parameter of the dynamic control interval reward item. Optimizing β2 can determine the impact of the proportion of this item within the reward function on system performance. It should be noted that these two hyperparameters are only used in the discussion of the DCI-SAC with combined value state, so the optimization is performed only for the DCI-SAC with combined value state. The results are shown in Table D.5. From the results, it is evident that excessively high or low values of μ0 are detrimental to algorithm perfor- mance. Selecting a moderate value of 0.5 for μ0 can effectively balance transient and steady-state variations within the control interval. Meanwhile, choosing a relatively higher value for β2 may cause the algorithm to overly focus on controlling the control interval time, thereby neglecting the system’s performance itself. Therefore, selecting a lower value of 1 for β2 is a preferable choice.
### Page 22

Based on the previous hyperparameter selection, the detailed hyperparameter configurations for various algorithms are provided in the following tables. The hyperparameter configuration for DQN is detailed in Table D.6. For PPO, the hyperparameter configuration is outlined in Table D.7. The TRPO hyperparameter configuration can be found in Table D.8. Lastly, the hyperparameter configuration for SAC is detailed in Table D.9. These tables comprehensively list the specific settings used for each algorithm, ensuring clarity and reproducibility of the experimental results.

## 公式/优化模型候选

### Page 3

```text
pump (Sp,2) is tuned with PID control to regulate the secondary-side
                                                                                   fluid pressure differential (Δp2) and adhere to the setpoint (Δp2,set).
                                                                                   To achieve energy conservation, direct control setpoints or indirect
```
### Page 4

```text
[                     ]      [                         ]
                                                                               (min) ψ = β0 PUE +              β1 Tchip,up,τ − Tchip,up + + β1 Tchip,down,τ − Tchip,down + dτ
    The algorithms embedded within the DRL agent are meticulously
```
### Page 4

```text
generating optimal policies to regulate the experimental platform. The
initialization of the system entails training the DRL-based algorithms         s.t.fct ≤ fct,set ≤ fct
within the agent, a process akin to crafting specific Deep Neural Net-
```
### Page 4

```text
within the agent, a process akin to crafting specific Deep Neural Net-
works (DNNs). However, once the training phase reaches fruition, the           Sp,1 ≤ Sp,1,set ≤ Sp,1
DRL agent becomes adept at furnishing tailored optimal control policies
```
### Page 4

```text
DRL agent becomes adept at furnishing tailored optimal control policies
for the respective systems [41].                                               Sp,2 ≤ Sp,2,set ≤ Sp,2                                                                   (1)
    In this endeavor, the fundamental objective of the DRL agent is to
```
### Page 5

```text
represent their set upper limit and set lower limit. The subscript ‘set’                     core tenet of RL control posits that when the system executes an action
indicates that this value is configurable. The subscript ‘τ’ represents the                  and garners positive rewards, it strengthens that action. On the contrary,
real-time value at the current time step, and the same meaning applies to                    if the rewards are lacking, the system diminishes the emphasis on that
```
### Page 5

```text
real-time value at the current time step, and the same meaning applies to                    if the rewards are lacking, the system diminishes the emphasis on that
the occurrences of ‘τ’ in the rest of this paper. The first item PUE is                      action in subsequent processes [47].
formulated as Eq. (2).                                                                           Let π(at|st) represent the policy, and ρπ(st,at) denote the state-action
```
### Page 5

```text
the occurrences of ‘τ’ in the rest of this paper. The first item PUE is                      action in subsequent processes [47].
formulated as Eq. (2).                                                                           Let π(at|st) represent the policy, and ρπ(st,at) denote the state-action
                                                                                             marginals of the trajectory distribution by a policy π(at|st). In the realm
```
### Page 5

```text
marginals of the trajectory distribution by a policy π(at|st). In the realm
         ∫t1                ∫t1
                                                                                             of RL, the overarching goal is to acquire an optimal policy, π(at|st), with
```
### Page 5

```text
of RL, the overarching goal is to acquire an optimal policy, π(at|st), with
               Pit,τ dτ +         Pcool,τ dτ
                                                                                             the aim of maximizing the cumulative rewards for discount factor
```
### Page 5

```text
t0                 t0
PUE =                                                                             (2)        γ∈(0,1), as expressed in Eq.(3).
                   ∫t1
```
### Page 5

```text
∑
                         Pit,τ dτ                                                            R(π) =      E(st ,at )∼ρπ [γt r(st , at ) ]                              (3)
                   t0                                                                                    t
```
### Page 5

```text
and the maximum entropy objective [48]. The off-policy method en-
alties for overheating in upstream and downstream chips, with β0 and β1
                                                                                             hances data efficiency by utilizing a replay buffer, while the maximum
```
### Page 6

```text
t+1 ~ πФ(⋅| st+1) is sampled from the current policy πФ. The weights of
the target networks θi are updated using an exponential moving average                        The SAC learning process alternates between a sequence of data
of prior weights for λ∈(0,1) as Eq. (9).                                                  collection steps (control loop) and policy optimization steps (training
```
### Page 6

```text
the target networks θi are updated using an exponential moving average                        The SAC learning process alternates between a sequence of data
of prior weights for λ∈(0,1) as Eq. (9).                                                  collection steps (control loop) and policy optimization steps (training
                                                                                          loop), as illustrated in Fig. 5. In the control loop, the agent interacts with
```
### Page 6

```text
loop), as illustrated in Fig. 5. In the control loop, the agent interacts with
θ i ←λθi + (1 − λ)θ i                                                          (9)
                                                                                          the simulation model according to the presently trained policy and
```
### Page 6

```text
the simulation model according to the presently trained policy and
    In the policy improvement step, the weights Φ can be updated to                       gathers data, storing it in the replay buffer in the form of tuple (st, at,
minimize the objective according to Eq. (10).                                             st+1, rt+1). Once the memory data size of the replay buffer reaches the
```
### Page 6

```text
[    (                        (           ]            minibatch size B, the training loop initiates, alternating with the control
Jπ (Φ; α) = Est ∼D,a∼ t ∼πΦ (⋅|st ) αlog π Φ (a∼ t |st ) − minQθi st , a∼ t )  (10)       loop. In the training loop, training data is sampled from the replay buffer
                                                           i=1,2
```
### Page 6

```text
Jπ (Φ; α) = Est ∼D,a∼ t ∼πΦ (⋅|st ) αlog π Φ (a∼ t |st ) − minQθi st , a∼ t )  (10)       loop. In the training loop, training data is sampled from the replay buffer
                                                           i=1,2
                                                                                          size of B, and the two soft Q-values, Qθ1(st, at) and Qθ2(st, at), are
```
### Page 6

```text
i=1,2
                                                                                          size of B, and the two soft Q-values, Qθ1(st, at) and Qθ2(st, at), are
                                                                                          computed through the two critic networks. Subsequently, sample ac-
```
### Page 6

```text
computed through the two critic networks. Subsequently, sample ac-
where a~ t is gotten from the current policy πФ. In addition to θi and Φ,
                                                                                          tions a~                    ~
```
### Page 8

```text
tervals and final-value state spaces have certain limitations. Therefore,
st = ssample,te                                                            (12)
                                                                                       this paper proposes a new SAC-based method, DCI-SAC, which dynam-
```
### Page 8

```text
interval), it might mistakenly suggest no significant change, although                 variations. To achieve this goal, in DCI-SAC, changes in ambient tem-
subsequent times will likely not maintain this stable state, leading to                perature (ΔTamb), changes in ambient relative humidity (ΔHamb), and
misjudgment of the current state information. Moreover, when there are                 changes in thermal load (ΔQ) are considered key states for dynamically
```
### Page 8

```text
subsequent times will likely not maintain this stable state, leading to                perature (ΔTamb), changes in ambient relative humidity (ΔHamb), and
misjudgment of the current state information. Moreover, when there are                 changes in thermal load (ΔQ) are considered key states for dynamically
```
### Page 9

```text
left side of Fig. 7. It should be noted that the Critic structure in the figure           Similar to the original state quantities, these three varia-
represents two Critic networks and two target Critic networks                         bles—changes in ambient temperature (ΔTamb), changes in ambient
simultaneously.                                                                       relative humidity (ΔHamb), and changes in thermal load (ΔQ)—also
```
### Page 9

```text
represents two Critic networks and two target Critic networks                         bles—changes in ambient temperature (ΔTamb), changes in ambient
simultaneously.                                                                       relative humidity (ΔHamb), and changes in thermal load (ΔQ)—also
    Obviously, it is essential to devise a novel reward metric that en-               have two forms: the final-value and the combined-value. The final
```
### Page 9

```text
terval. Specifically, the optimal control interval is inversely proportional                 ⃒                       ⃒
                                                                                      Δst = ⃒ssample,te − ssample,ts ⃒                                   (15)
to the maximum value among the three variables. This is warranted as
```
### Page 9

```text
initially applied to synchronize its rate of change with the other three              control interval, which can also be considered another form of the final
variables. Subsequently, ΔTamb, ΔHamb, ΔQ and log(tci) are normalized                 value of state changes. Therefore, the chosen method involves simulta-
as ΔT*amb, ΔH*amb, ΔQ* and log*(tci) individually using min-max                       neously incorporating both the integral mean of the deviation from the
```
### Page 9

```text
variables. Subsequently, ΔTamb, ΔHamb, ΔQ and log(tci) are normalized                 value of state changes. Therefore, the chosen method involves simulta-
as ΔT*amb, ΔH*amb, ΔQ* and log*(tci) individually using min-max                       neously incorporating both the integral mean of the deviation from the
normalization [36]. The determination of maximum and minimum                          mean and the difference between the maximum and average values
```
### Page 9

```text
(         { *                                         }          )
              max ΔTamb    , ΔH*amb , ΔQ* , (1 − log* (tci ) ) + ε                            ∫te
σ = β2        {     { *                      }                  }    − C   (13)                     ⃒                      ⃒
```
### Page 9

```text
max ΔTamb    , ΔH*amb , ΔQ* , (1 − log* (tci ) ) + ε                            ∫te
σ = β2        {     { *                      }                  }    − C   (13)                     ⃒                      ⃒
                                                                                                    ⃒ssample,τ − ssample,τ ⃒dτ
```
### Page 9

```text
σ = β2        {     { *                      }                  }    − C   (13)                     ⃒                      ⃒
                                                                                                    ⃒ssample,τ − ssample,τ ⃒dτ
          min max ΔTamb           *
```
### Page 11

```text
[9–12,15,35]. Detailed explanations of this method are presented in             MPC(300)                        7.67                           1.118
   Appendix C.                                                                     DQN(300) + Final value state    7.80±0.72                      1.120 ± 0.011
3) Deep Q-Network (DQN): Adapting the original DQN for the imple-                  TRPO(300) + Final value state   7.48 ± 0.12                    1.115 ± 0.002
```
### Page 11

```text
Appendix C.                                                                     DQN(300) + Final value state    7.80±0.72                      1.120 ± 0.011
3) Deep Q-Network (DQN): Adapting the original DQN for the imple-                  TRPO(300) + Final value state   7.48 ± 0.12                    1.115 ± 0.002
                                                                                   PPO(300) + Final value state    7.09 ± 0.13                    1.109 ± 0.002
```
### Page 11

```text
3) Deep Q-Network (DQN): Adapting the original DQN for the imple-                  TRPO(300) + Final value state   7.48 ± 0.12                    1.115 ± 0.002
                                                                                   PPO(300) + Final value state    7.09 ± 0.13                    1.109 ± 0.002
   mentation of data center control involves discretizing the continuous
```
### Page 11

```text
mentation of data center control involves discretizing the continuous
                                                                                   SAC(300) + Final value state    6.96 ± 0.20                    1.107 ± 0.003
   action space A used in PPO, TRPO, SAC into a discrete set, as illus-
```
### Page 11

```text
constraining the step size to stay within a trust region [49]. This is         5) Proximal Policy Optimization (PPO): PPO is a simplified and
   achieved by optimizing a surrogate objective function subject to a                computationally efficient variant of TRPO, which uses a clipped
```
### Page 13

```text
than DQN but still not as efficiently as SAC in terms of both learning         compensation for the reward function. In DCI-SAC, the reward function
   stability and energy savings.                                                  is defined as r = r0 - Ψ - σ, where an additional term “σ” is subtracted
5) SAC stands out due to its operation in a continuous action space and           compared to SAC. Thus, adding the term “σ” allows for a comparison of
```
### Page 13

```text
stability and energy savings.                                                  is defined as r = r0 - Ψ - σ, where an additional term “σ” is subtracted
5) SAC stands out due to its operation in a continuous action space and           compared to SAC. Thus, adding the term “σ” allows for a comparison of
   its off-policy approach, which allows for more efficient sample uti-           reward values with SAC. Meanwhile, the value of “σ” also represents the
```
### Page 13

```text
5) SAC stands out due to its operation in a continuous action space and           compared to SAC. Thus, adding the term “σ” allows for a comparison of
   its off-policy approach, which allows for more efficient sample uti-           reward values with SAC. Meanwhile, the value of “σ” also represents the
   lization. The inclusion of an entropy term in SAC encourages ongoing           overall situation of dynamic adjustments in the control time interval.
```
### Page 13

```text
exploration by preventing the policy from becoming deterministic               Additionally, in all subsequent learning curves, the reward values
   too quickly. This balance between exploration and exploitation en-             already incorporate the addition of the term σ.
   sures a more stable learning process and faster convergence. SAC’s                 In real-time control actions shown in Fig. 12, a 300-s control interval
```
### Page 13

```text
SAC utilizes a final-value state space, it achieves up to a 5.25% reduction
  ①             6.70 ± 0.13           1.103 ±       9.73 ± 0.17                   in energy consumption and a 0.006 reduction in PUE compared to SAC
                                      0.002                                       with the same final-value state space.
```
### Page 13

```text
0.002                                       with the same final-value state space.
                6.61 ± 0.09           1.101 ±       9.85 ± 0.12
                                                                                      Similar to the analytical methods used in Section 4.2, Fig. 15 illus-
```
### Page 13

```text
0.001
  ③             6.96±0.20             1.107 ±       9.32 ± 0.26                   trates temperature distribution results, indicating that a 300-s control
                                      0.003                                       interval results in the most unstable distribution of chip temperatures
```
### Page 13

```text
0.003                                       interval results in the most unstable distribution of chip temperatures
  ④             6.72 ± 0.13           1.103 ±       9.71 ± 0.16                   due to delayed responses. Excessive adjustments with a 100-s interval
                                      0.002
```
### Page 19

```text
de(t)
u(t) = Kp e(t) + Ki        e(t)dt + Kd                                                                                                                                   (B.1)
                                          dt
```
### Page 19

```text
C
                                                          Δp2,set                         0.8                     bar
```
### Page 20

```text
In the context of model predictive control, the choice of the time horizon holds increased significance, represented as “nΔt” in Fig. C.1.
Furthermore, the implementation of the entire algorithm necessitates the configuration of specific hyperparameters for the genetic algorithm, as
```
### Page 21

```text
DQN                             32                         1.127±0.017               3.85±1.28            4.29±1.59
                   PPO                             32                         1.117±0.009               2.76±0.16            2.79±0.19
```
### Page 21

```text
DQN                             32                         1.127±0.017               3.85±1.28            4.29±1.59
                   PPO                             32                         1.117±0.009               2.76±0.16            2.79±0.19
                   TRPO                            32                         1.125±0.012               3.04±0.19            3.74±0.20
```
### Page 21

```text
PPO                             32                         1.117±0.009               2.76±0.16            2.79±0.19
                   TRPO                            32                         1.125±0.012               3.04±0.19            3.74±0.20
                   SAC                             32                         1.108±0.004               2.29±0.17            2.38±0.18
```
### Page 21

```text
TRPO                            32                         1.125±0.012               3.04±0.19            3.74±0.20
                   SAC                             32                         1.108±0.004               2.29±0.17            2.38±0.18
                   DQN                             64                         1.120±0.011               3.48±0.87            3.85±1.04
```
### Page 21

```text
SAC                             32                         1.108±0.004               2.29±0.17            2.38±0.18
                   DQN                             64                         1.120±0.011               3.48±0.87            3.85±1.04
                   PPO                             64                         1.114±0.009               2.74±0.14            2.78±0.14
```
### Page 21

```text
DQN                             64                         1.120±0.011               3.48±0.87            3.85±1.04
                   PPO                             64                         1.114±0.009               2.74±0.14            2.78±0.14
                   TRPO                            64                         1.118±0.008               2.93±0.12            3.27±0.15
```
### Page 21

```text
PPO                             64                         1.114±0.009               2.74±0.14            2.78±0.14
                   TRPO                            64                         1.118±0.008               2.93±0.12            3.27±0.15
                   SAC                             64                         1.107±0.003               2.28±0.15            2.32±0.14
```
### Page 21

```text
TRPO                            64                         1.118±0.008               2.93±0.12            3.27±0.15
                   SAC                             64                         1.107±0.003               2.28±0.15            2.32±0.14
                   DQN                             128                        1.125±0.010               3.57±0.84            3.90±1.08
```
### Page 22

```text
Table D.3
                         The optimization of β1.
```
### Page 22

```text
Algorithm               β1            Test performance
```
### Page 22

```text
DQN                     0.1           1.119±0.010                        3.88±0.76               4.23±0.85
                            PPO                     0.1           1.109±0.003                        3.01±0.39               2.97±0.28
```
### Page 22

```text
DQN                     0.1           1.119±0.010                        3.88±0.76               4.23±0.85
                            PPO                     0.1           1.109±0.003                        3.01±0.39               2.97±0.28
                            TRPO                    0.1           1.113±0.002                        3.38±0.25               3.47±0.21
```
### Page 22

```text
PPO                     0.1           1.109±0.003                        3.01±0.39               2.97±0.28
                            TRPO                    0.1           1.113±0.002                        3.38±0.25               3.47±0.21
                            SAC                     0.1           1.107±0.003                        2.51±0.22               2.59±0.28
```
### Page 22

```text
TRPO                    0.1           1.113±0.002                        3.38±0.25               3.47±0.21
                            SAC                     0.1           1.107±0.003                        2.51±0.22               2.59±0.28
                            DQN                     0.2           1.120±0.011                        3.48±0.87               3.85±1.08
```
### Page 22

```text
SAC                     0.1           1.107±0.003                        2.51±0.22               2.59±0.28
                            DQN                     0.2           1.120±0.011                        3.48±0.87               3.85±1.08
                            PPO                     0.2           1.109±0.002                        2.53±0.13               2.52±0.13
```
### Page 22

```text
DQN                     0.2           1.120±0.011                        3.48±0.87               3.85±1.08
                            PPO                     0.2           1.109±0.002                        2.53±0.13               2.52±0.13
                            TRPO                    0.2           1.115±0.002                        2.79±0.13               2.89±0.11
```
### Page 23

```text
Batch size                                                  64
                 Discount factor (γ)                                         0.99
                 Actor learning rate                                         10− 4
```
### Page 23

```text
Replay Buffer Size                                          105
                 Exponential moving average rate (λ)                         0.01
                 Initial temperature coefficient (α)                         1
```
### Page 23

```text
Exponential moving average rate (λ)                         0.01
                 Initial temperature coefficient (α)                         1
                 Target entropy (H0)                                         − 3
```
### Page 23

```text
Target entropy (H0)                                         − 3
                                                                β0           100
                                                                β1           0.2
```
### Page 23

```text
β0           100
                                                                β1           0.2
                   Other hyperparameters                        μ0           0.5
```
### Page 23

```text
β1           0.2
                   Other hyperparameters                        μ0           0.5
                                                                μ1           0.5
```
### Page 23

```text
Other hyperparameters                        μ0           0.5
                                                                μ1           0.5
                                                                r0           120
```
### Page 24

```text
Exponential moving average rate (λ)                                           0.01
                                                      Initial temperature coefficient (α)                                           1
                                                      Target entropy (H0)                                                           − 4
```
### Page 24

```text
Target entropy (H0)                                                           − 4
                                                                                                       β0                           100
                                                                                                       β1                           0.2
```
### Page 24

```text
β0                           100
                                                                                                       β1                           0.2
                                                        Other hyperparameters                          β2                           1
```
### Page 24

```text
β1                           0.2
                                                        Other hyperparameters                          β2                           1
                                                                                                       μ0                           0.5
```
### Page 24

```text
Other hyperparameters                          β2                           1
                                                                                                       μ0                           0.5
                                                                                                       μ1                           0.5
```
### Page 24

```text
μ0                           0.5
                                                                                                       μ1                           0.5
                                                                                                       C                            1
```

## 符号表/变量定义候选

未发现明确 Nomenclature/Acronyms 段。

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
