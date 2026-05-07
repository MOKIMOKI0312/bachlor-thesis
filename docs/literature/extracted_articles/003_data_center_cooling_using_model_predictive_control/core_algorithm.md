# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2018_Lazic_Data_center_cooling_using_model_predictive_control.pdf`
- 标题：Data center cooling using model-predictive control
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

p4 model predictive control; p4.1 model structure; p6 control optimization constraints.

真实数据中心冷却 MPC/安全部署参考；不含 TES/PV/TOU，但支撑 MPC 论证。

## 算法/控制流程候选

### Page 1

Despite the impressive recent advances in reinforcement learning (RL) algorithms, their deployment to real-world physical systems is often complicated by unexpected events, limited data, and the potential for expensive failures. In this paper, we describe an application of RL “in the wild” to the task of regulating temperatures and airflow inside a large-scale data center (DC). Adopting a data-driven, model- based approach, we demonstrate that an RL agent with little prior knowledge is able to effectively and safely regulate conditions on a server floor after just a few hours of exploration, while improving operational efficiency relative to existing PID controllers.
### Page 2

Recently, DeepMind demonstrated that it is possible to improve DC power usage efficiency (PUE) using a machine learning approach [13]. In particular, they developed a predictive model of PUE in a large-scale Google DC, and demonstrated that it can be improved by manipulating the temperature of the water leaving the cooling tower and chilled water injection setpoints. In this work, we focus on a complementary aspect of DC cooling: regulating the temperature and airflow inside server floors by controlling fan speeds and water flow within air handling units (AHUs). Our approach to cooling relies on model-predictive control (MPC). Specifically, we learn a linear model of the DC dynamics using safe, random exploration, starting with little or no prior knowledge. We subsequently recommend control actions at each time point by optimizing the cost of model- predicted trajectories. Rather than executing entire trajectories, we re-optimize at each time step. The resulting system is simple to deploy, as it does not require historical data or a physics-based model. The main contribution of the paper is to demonstrate that a controller relying on a coarse-grained linear dynamics model can safely, effectively, and cost-efficiently regulate conditions in a large-scale commercial data center, after just a few hours of learning and with minimal prior knowledge. By contrast, characterizing and configuring the cooling control of a new data center floor typically takes weeks of setup and testing using existing techniques.
### Page 4

4 Model predictive control We consider the use of MPC to remove some of the inefficiencies associated with the existing PID control system. We: (i) model the effect of each AHU on state variables in a large neighborhood (up to 5 server rows) rather than on just the closest sensors; (ii) control CAT directly rather using LAT as a proxy; and (iii) jointly optimize all controls instead of using independent local controllers. We identify a model of DC cooling dynamics using only a few hours of exploration and minimal prior knowledge. We then control using this learned model, removing the need for manual tuning. As we show, these changes allow us to operate at less conservative setpoints and improve the cooling operational efficiency.
### Page 4

Let x[t], u[t], and d[t] be the vectors of all state, control, and disturbance variables at time t, respectively. We model data center dynamics using a linear auto-regressive model with exogeneous variables (or ARX model) of the following form: T X T X x[t] = Ak x[t − k] + Bk u[t − k] + Cd[t − 1] . (1) k=1 k=1
### Page 4

where Ak , Bk , and Ck are parameter matrices of appropriate dimensions. Since we treat sensor observations as state variables, our model is T -Markov to capture relevant history and underlying latent state. Each time step corresponds to a period of 30s, and we set T = 5 based on cross-validation. While the true dynamics are not linear, we will see that a linear approximation in the relevant region of state-action space suffices for effective control. We use prior knowledge about the DC layout to impose a block diagonal-like sparsity on the learned parameter matrices. The large size of the server floor allows us to assume that temperatures and DPs at each location directly depend only states, controls, and disturbances at nearby locations (i.e., are conditionally independent of more distant sensors and AHUs given the nearby values).1 Additional parameter sparsity can be imposed based on variable types; for example, we know that DP directly 1 In other words, the nearby sensors and controls form a Markov blanket [26] for specific variables in a graphical model of the dynamical system.
### Page 6

Given our model and an initial condition (the T past states, controls, and disturbances for the M AHUs), we optimize the cost of a length-L trajectory with respect to control inputs at every step. Let xssp denote the setpoint (or target value) for a state variable s, where s ∈ {DP, CAT, LAT}. Let xsi [t] denote the value of the state variable s for the ith AHU at time t. We set controls by solving the following optimization problem: t+L XX M X X  min qs (xsi [τ ] − xssp )2 + rc (uci [τ ] − ucmin )2 (3) u τ =t i=1 s c s.t. uci ∈ [ucmin , ucmax ], |uci [τ ] − uci [τ − 1]| ≤ ∆c , d[τ ] = d[τ − 1] (4) T X T X x[τ ] = Ak x[τ − k] + Bk u[τ − k] + Cd[τ − 1] (5) k=1 k=1 t ≤ τ ≤ t + L, c ∈ {fan, valve}, s ∈ {DP, CAT, LAT}. (6)
### Page 6

Here qs and rc are the weights for the loss w.r.t. state and control variables s and c, respectively, and i ranges over AHUs. We assume that disturbances do not change over time. Overall, we have a quadratic optimization objective in 2M L ≃ 1.2K variables, with a large number of linear and range constraints. While we optimize over the entire trajectory, we only execute the optimized control action at the first time step. Re-optimizing at each step enables us to react to changes in disturbances and compensate for model error. We specify the above objective as a computation graph in TensorFlow [1] and optimize controls using the Adam [19] algorithm. In particular, we implement constraints by specifying controls as uci [τ ] = max(ucmin , min(ucmax , uci [τ − 1] + ∆c tanh(zic [τ ]))) (7) where zic [τ ] is an unconstrained optimization variable. The main motivation for this choice is its simplicity and speed—the optimization converges well before our re-optimization period of 30s.
### Page 6

5 Experiments We evaluate the performance of our MPC approach w.r.t. the existing local PID method on a large- scale DC. Since the quality of MPC depends critically on the quality of the underlying model, we first compare our system identification strategy to two simple alternatives. One complication in comparing the performance of different methods on a physical system is the inability to control environmental disturbances which affect the achievable costs and steady-state behavior. In our DC cooling setting, the main disturbances are the EWT (temperature of entering cold water) and server power usage (a proxy for generated heat). These variables also reflect other factors (e.g., weather, time of day, server hardware, IT load). To facilitate a meaningful comparison, we evaluate the cost of control (i.e., cost of power and water used by the AHUs) for different ranges of states and disturbances.
### Page 7

Figure 4: Histograms of state variables and disturbances over time and AHUs during steady-state operation of MPC controllers using three different models.
### Page 7

The existing local PID controllers differ from ours in that they regulate LAT to a constant offset relative to EWT, rather than controlling CAT directly. To compare the two approaches, we ran our MPC controller with the same LAT-offset setpoints for one day, and compared it to a week of local PID control. As before, we treat measurements at each group of sensors as depending only on the closest AHU, and ignore time lags (assuming reasonable control consistency during steady-state operation). Histograms of states and disturbances during the operation of the two controllers are
### Page 8

Figure 5: Histograms of state variables and disturbances over time and AHUs during steady-state operation of the MPC (Model 1) and local PID controllers.
### Page 8

We have presented an application of model-based reinforcement learning to the task of regulating data center cooling. Specifically, we have demonstrated that a simple linear model identified from only a few hours of exploration suffices for effective regulation of temperatures and airflow on a large-scale server floor. We have also shown that this approach is more cost effective than commonly used local controllers and controllers based on non-exploratory data. One interesting question is whether the controller performance could further be improved by using a higher-capacity model such as a neural network. However, such a model would likely require more than a few hours of exploratory data to identify, and may be more complicated to plan with. Perhaps the most promising direction for model improvement is to learn a mixture of linear models that could approximate dynamics better under different disturbance conditions. In terms of overall data center operational efficiency, further advantages are almost certainly achievable achieved by jointly controlling AHUs and the range of disturbance variables if possible, or by planning AHU control according to known/predicted disturbances values rather than treating them as noise.
### Page 10

[19] Diederik Kingma and Jimmy Ba. Adam: A method for stochastic optimization. In International Conference on Learning Representations (ICLR), 2015.
### Page 10

[22] Yudong Ma, Francesco Borrelli, Brandon Hencey, Brian Coffey, Sorin Bengea, and Philip Haves. Model predictive control for the operation of building cooling systems. IEEE Transactions on control systems technology, 20(3):796–803, 2012.

## 公式/优化模型候选

### Page 2

```text
[8, 2, 17] use optimism in the face of uncertainty, where at each iteration the algorithm selects
the dynamics with lowest attainable cost from some confidence set.    √ While optimistic control is
asymptotically optimal [8] and has a finite-time regret bound of O( T ) [2], it is highly impractical
```
### Page 4

```text
X
                        x[t] =         Ak x[t − k] +         Bk u[t − k] + Cd[t − 1] .                (1)
                                 k=1                   k=1
```
### Page 4

```text
x[t] =         Ak x[t − k] +         Bk u[t − k] + Cd[t − 1] .                (1)
                                 k=1                   k=1
```
### Page 4

```text
observations as state variables, our model is T -Markov to capture relevant history and underlying
latent state. Each time step corresponds to a period of 30s, and we set T = 5 based on cross-validation.
While the true dynamics are not linear, we will see that a linear approximation in the relevant region
```
### Page 5

```text
each control variable:
             uci [t + 1] = max(ucmin , min(ucmax , uci [t] + vic )), vic ∼ Uniform(−∆c , ∆c ).                   (2)
This strategy ensures sufficient frequency content for system identification and respects safety and
```
### Page 5

```text
control phase, we update parameters selectively so as not to overwhelm the model with steady-state
data. In particular, we estimate the noise standard deviation σs for each variable s as the root
mean squared error on the training data, and update the model with an example only if its (current)
```
### Page 5

```text
mean squared error on the training data, and update the model with an example only if its (current)
prediction error exceeds 2σs .3
    2
```
### Page 6

```text
XX   M X                                X                         
                 min                   qs (xsi [τ ] − xssp )2 +   rc (uci [τ ] − ucmin )2              (3)
                 u
```
### Page 6

```text
u
                      τ =t i=1       s                          c
                s.t. uci ∈ [ucmin , ucmax ], |uci [τ ] − uci [τ − 1]| ≤ ∆c , d[τ ] = d[τ − 1]         (4)
```
### Page 6

```text
τ =t i=1       s                          c
                s.t. uci ∈ [ucmin , ucmax ], |uci [τ ] − uci [τ − 1]| ≤ ∆c , d[τ ] = d[τ − 1]         (4)
                               T
```
### Page 6

```text
X
                     x[τ ] =         Ak x[τ − k] +         Bk u[τ − k] + Cd[τ − 1]                    (5)
                               k=1                   k=1
```
### Page 6

```text
x[τ ] =         Ak x[τ − k] +         Bk u[τ − k] + Cd[τ − 1]                    (5)
                               k=1                   k=1
                     t ≤ τ ≤ t + L, c ∈ {fan, valve}, s ∈ {DP, CAT, LAT}.                             (6)
```
### Page 6

```text
k=1                   k=1
                     t ≤ τ ≤ t + L, c ∈ {fan, valve}, s ∈ {DP, CAT, LAT}.                             (6)
```
### Page 6

```text
the Adam [19] algorithm. In particular, we implement constraints by specifying controls as
                     uci [τ ] = max(ucmin , min(ucmax , uci [τ − 1] + ∆c tanh(zic [τ ])))             (7)
where zic [τ ] is an unconstrained optimization variable. The main motivation for this choice is its
```
### Page 6

```text
uci [τ ] = max(ucmin , min(ucmax , uci [τ − 1] + ∆c tanh(zic [τ ])))             (7)
where zic [τ ] is an unconstrained optimization variable. The main motivation for this choice is its
simplicity and speed—the optimization converges well before our re-optimization period of 30s.
```
### Page 7

```text
temperature (C)           (fraction of max)            cost (% data)                cost (% data)            cost (% data)
       ≤ 20.5                    ≤ 0.7                        84.3 (31%)                   94.4 (29.9%)             99.6 (13.7%)
       > 20.5                    ≤ 0.7                        85.8 (17.6 %)                93.8 (14.1 %)            112.7 (36.0 %)
```
### Page 7

```text
≤ 20.5                    ≤ 0.7                        84.3 (31%)                   94.4 (29.9%)             99.6 (13.7%)
       > 20.5                    ≤ 0.7                        85.8 (17.6 %)                93.8 (14.1 %)            112.7 (36.0 %)
       ≤ 20.5                    > 0.7                        142.4 (21.9 %)               149.4 (20.4 %)           178.2 (8.3 %)
```
### Page 7

```text
> 20.5                    ≤ 0.7                        85.8 (17.6 %)                93.8 (14.1 %)            112.7 (36.0 %)
       ≤ 20.5                    > 0.7                        142.4 (21.9 %)               149.4 (20.4 %)           178.2 (8.3 %)
       > 20.5                    > 0.7                        144.6 (15.3 %)               148.9(12.8 %)            182 .1 (29.9 %)
```
### Page 8

```text
temperature (C)            (frac. max)           cost (% data)                     cost (% data)
                       ≤ 20.5                     ≤ 0.7                 95.3 (19.8 %)                     106.4 (22.6 %)
                       > 20.5                     ≤ 0.7                 107.9 (13.8 %)                    104.9 (15.0 %)
```
### Page 8

```text
≤ 20.5                     ≤ 0.7                 95.3 (19.8 %)                     106.4 (22.6 %)
                       > 20.5                     ≤ 0.7                 107.9 (13.8 %)                    104.9 (15.0 %)
                       ≤ 20.5                     > 0.7                 170.3 (20.1%)                     130.5 (18.8 %)
```
### Page 8

```text
> 20.5                     ≤ 0.7                 107.9 (13.8 %)                    104.9 (15.0 %)
                       ≤ 20.5                     > 0.7                 170.3 (20.1%)                     130.5 (18.8 %)
                       > 20.5                     > 0.7                 187.8 (20.4 %)                    128.7 (18.0 %)
```
### Page 9

```text
forecasting and control. John Wiley & Sons, 2015.
[10] Jie Chen and Guoxiang Gu. Control-oriented system identification: an H∞ approach, volume 19. Wiley-
     Interscience, 2000.
```
### Page 9

```text
[16] Arthur J Helmicki, Clas A Jacobson, and Carl N Nett. Control oriented system identification: a worst-
     case/deterministic approach in H∞ . IEEE Transactions on Automatic control, 36(10):1163–1176, 1991.
[17] Morteza Ibrahimi, Adel Javanmard, and Benjamin V. Roy. Efficient reinforcement learning for high
```

## 符号表/变量定义候选

未发现明确 Nomenclature/Acronyms 段。

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
