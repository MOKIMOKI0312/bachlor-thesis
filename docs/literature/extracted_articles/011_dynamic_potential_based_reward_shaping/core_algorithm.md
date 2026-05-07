# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2012_Devlin_Dynamic_Potential_Based_Reward_Shaping.pdf`
- 标题：Dynamic Potential-Based Reward Shaping
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

未在可抽取文本中发现明确的算法流程段落。

## 公式/优化模型候选

### Page 2

```text
An MDP is a tuple hS, A, T, Ri, where S is the state space,      receive their maximum reward. Instead some compromise
A is the action space, T (s, a, s0 ) = P r(s0 |s, a) is the prob-   must be made, typically the system is designed aiming to
ability that action a in state s will lead to state s0 , and        converge to a Nash equilibrium [18].
```
### Page 2

```text
from states to actions) which maximises the accumulated             hS, A1 , ..., An , T, R1 , ..., Rn i, where S is the state space, Ai
reward. When the environment dynamics (transition prob-             is the action space of agent i, T (s, ai...n , s0 ) = P r(s0 |s, ai...n )
abilities and reward function) are available, this task can be      is the probability that joint action ai...n in state s will lead
```
### Page 2

```text
Q(s, a) ← Q(s, a) + α[r + γ max Q(s0 , a0 ) − Q(s, a)]   (1)   2.2     Reward Shaping
                                  0a
```
### Page 2

```text
The idea of reward shaping is to provide an additional re-
where α is the rate of learning and γ is the discount factor.       ward representative of prior knowledge to reduce the number
It modifies the value of taking action a in state s, when           of suboptimal actions made and so reduce the time needed
```
### Page 2

```text
Provided each state-action pair is experienced an infinite
                                                                    Q(s, a) ← Q(s, a) + α[r + F (s, s0 ) + γ max Q(s0 , a0 ) − Q(s, a)]
number of times, the rewards are bounded and the agent’s                                                      0   a
```
### Page 2

```text
joint action learners [6]. The latter is a group of multi-          proposed [15] as the difference of some potential function
agent specific algorithms designed to consider the existence        Φ defined over a source s and a destination state s0 :
of other agents. The former is the deployment of multiple                                F (s, s0 ) = γΦ(s0 ) − Φ(s)                     (3)
```
### Page 2

```text
agent specific algorithms designed to consider the existence        Φ defined over a source s and a destination state s0 :
of other agents. The former is the deployment of multiple                                F (s, s0 ) = γΦ(s0 ) − Φ(s)                     (3)
agents each using a single-agent reinforcement learning al-
```
### Page 2

```text
agents each using a single-agent reinforcement learning al-
gorithm.                                                            where γ must be the same discount factor as used in the
   Multiple individual learners assume any other agents to          agent’s update rule (see Equation 1).
```
### Page 3

```text
based reward shaping including those presented in this pa-         dynamic potential function we extend Equation 3 to include
per, require actions to be selected by an advantage-based          time as a parameter of the potential function Φ. Informally,
policy [23]. Advantage-based policies select actions based on      if the difference in potential is calculated from the potentials
```
### Page 3

```text
2.2.1    Reward Shaping In Multi-Agent Systems
   Incorporating heuristic knowledge has been shown to also                           F (s, t, s0 , t0 ) = γΦ(s0 , t0 ) − Φ(s, t)               (4)
be beneficial in multi-agent reinforcement learning [2, 13, 14,       where t is the time the agent arrived at previous state s
```
### Page 3

```text
Since this time, theoretical results [8] have shown that
whilst Wiewiora’s proof [23] of equivalence to Q-table ini-                                                       ∞
                                                                                                                  X
```
### Page 3

```text
X
tialisation holds also for multi-agent reinforcement learning                                     Ui (s̄) =             γ j rj,i                (5)
Ng’s proof [15] of policy invariance does not. Multi-agent                                                        j=0
```
### Page 3

```text
tialisation holds also for multi-agent reinforcement learning                                     Ui (s̄) =             γ j rj,i                (5)
Ng’s proof [15] of policy invariance does not. Multi-agent                                                        j=0
potential-based reward shaping can alter the final policy a          where rj,i is the reward received at time j by agent i from
```
### Page 3

```text
Reward shaping is typically implemented bespoke for each                                               X
new environment using domain-specific heuristic knowledge                                 Q∗i (s, a) =            P r(s̄|s, a)Ui (s̄)           (6)
                                                                                                            s̄
```
### Page 3

```text
All of these existing methods alter the potential of states     tion of the form given in Equation 4. The return of the
online whilst the agent is learning. Neither the existing          shaped agent Ui,Φ experiencing the same sequence s̄ is:
single-agent [15] nor the multi-agent [8] proven theoretical
```
### Page 3

```text
single-agent [15] nor the multi-agent [8] proven theoretical
results considered such dynamic shaping.                                                    ∞
                                                                                            X
```
### Page 4

```text
Q0 (s, a) ← Q0 (s, a) + α (ri + γ max Q0 (s0 , a0 ) − Q0 (s, a))
                      X
```
### Page 4

```text
X
 Q∗i,Φ (s, a)   =           P r(s̄|s, a)Ui,Φ (s̄)                                                                     a0
                       s̄                                                                                    |               {z                   }
```
### Page 4

```text
s̄                                                                                    |               {z                   }
                      X                                                                                                            δQ0 (s,a)
                =           P r(s̄|s, a)(Ui (s̄) − Φ(s, t))                                                                            (12)
```
### Page 4

```text
X                                                                                                            δQ0 (s,a)
                =           P r(s̄|s, a)(Ui (s̄) − Φ(s, t))                                                                            (12)
                       s̄                                                          And its current Q-values can be represented formally as:
```
### Page 4

```text
X                             X
                =           P r(s̄|s, a)Ui (s̄) −        P r(s̄|s, a)Φ(s, t)
                       s̄                           s̄
```
### Page 4

```text
s̄                           s̄
                                                                                              Q0 (s, a) = Q0 (s, a) + Φ(s, t0 ) + ∆Q0 (s, a)      (13)
                =     Q∗i (s, a) − Φ(s, t)                                (8)
```
### Page 4

```text
Q0 (s, a) = Q0 (s, a) + Φ(s, t0 ) + ∆Q0 (s, a)      (13)
                =     Q∗i (s, a) − Φ(s, t)                                (8)
                                                                                   where Φ(s, t0 ) is the potential for state s before learning
```
### Page 4

```text
=     Q∗i (s, a) − Φ(s, t)                                (8)
                                                                                   where Φ(s, t0 ) is the potential for state s before learning
   where t is the current time.                                                  begins.
```
### Page 5

```text
isation.                                                             ploration and a tabular representation of the environment.
   Therefore, we conclude that there is not a method of              Experimental parameters were set as α = 0.05,γ = 1.0 and 
initialising an agent’s Q-table to guarantee equivalent be-          begins at 0.4 and reduces linearly over the first 500 episodes
```
### Page 5

```text
At each time step, if the agent is receiving uniform random        1
                                                                       If γ was less than 1 then this value would be discounted by
shaping, the state entered will be given a random potential          γ, as we will demonstrate in the multi-agent example.
```
### Page 5

```text
If γ was less than 1 then this value would be discounted by
shaping, the state entered will be given a random potential          γ, as we will demonstrate in the multi-agent example.
```
### Page 6

```text
*,*
                F (s, s0 ) = γΦ(s0 , t0 ) − Φ(s, t)                                       b,*
                                                                                                      s3             s6   +5
```
### Page 6

```text
common in previous published examples [7, 15, 24], the              a new state upon entering it and be rewarded that poten-
agent will learn quicker but the lesser published alternative       tial discounted by γ less the potential of the previous state
is that a poor heuristic is used and the agent learns slower.2      at the time it was entered. Therefore, each agent receives
```
### Page 6

```text
to a state where they must co-ordinate to receive the highest       tion of the environment. Experimental parameters were set
reward (s2 ). However, in state s2 the agents are at risk of        as α = 0.5,γ = 0.99 and  begins at 0.3 and decays by 0.99
receiving a large negative reward if they do not choose the         each episode.
```
### Page 7

```text
F (s, t, s0 , t0 ) = γΦ(s0 , t0 ) − Φ(s, t)
         Figure 4: Without Reward Shaping
```

## 符号表/变量定义候选

未发现明确 Nomenclature/Acronyms 段。

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
