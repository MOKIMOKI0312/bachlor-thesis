# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2024_Zhu_The_influence_of_uncertainty_parameters_on_the_double_layer_model_predic.pdf`
- 标题：The influence of uncertainty parameters on the double-layer model predictive control strategy for the collaborative operation of chiller and cold storage tank in data center
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

The influence of uncertainty parameters on the double-layer model predictive control strategy for the collaborative operation of chiller and cold storage tank in data center Yiqun Zhu a, Quan Zhang a,*, Gongsheng Huang b, Jiaqiang Wang c , Sikai Zou d a College of Civil Engineering, Hunan University, Changsha, 410082, China b Department of Architecture and Civil Engineering, City University of Hong Kong, Hong Kong, 999077, China c School of Energy Science and Engineering, Central South University, Changsha, 410083, China d School of Civil Engineering and Architecture, East China JiaoTong University, Nanchang, 330013, China
### Page 4

Where P is the power (kW); G represents the water flow rate (m3/h); N represents the number of cooling units; H represents the deadline of one cycle optimization time domain; h is the time; D and U are values of 0 or 1. The meaning of the subscripts is as follows: sys represents the cooling system; m indicates that the cooling mode is MC mode or HC mode; f indicates that the cooling mode is FC mode; u is the upper limit; l is the lower limit. The constraints of the first-layer optimization are as follows.
### Page 4

(1) The constraint conditions of cold storage/release flow rate are as follows: Fig. 2. Performance curve of chiller. ( ) Qm + Qf + Z*Y h − dh ≥ Qs,l (6) cooling unit can operate in a high efficiency zone. The objective function ( ) is the lowest energy consumption during the optimization period. Qm + Qf − Z*(1 − Y) h − dh ≤ − Qr,l (7) Optimization is carried out under constraints such as cold storage/r­ ( ) elease flow rate, cold storage tank volume, and emergency cold storage − Qr,u ≤ Qm + Qf h − dh ≤ Qs,u (8) capacity. Before entering the optimization process, pre-calculations are ∑PLRu ∑Nu performed first. In MC mode, the energy consumption of the cooling Qm = i=PLRl k=0 Dk,i *Qk,i (9) system is pre-calculated for all combinations of PLR and chiller quantity. In FC mode, the same pre-calculation is performed for all combinations ∑Gu ∑Nu Qf = Uk,j *Qk,j (10) of chilled water flow rate and heat exchanger quantity. And in HC mode, j=Gl k=0
### Page 5

where Q represents the cooling capacity (kW); Z is a sufficiently large (1) Initialize set parameters and operating parameters, including Tapp positive constant; The value of Y indicates the cold storage/release and ΔTct. operational status of either the CR mode or the CS mode, where 1 sig­ (2) Calculate the objective function, aiming to minimize system en­ nifies the CR mode is operation, and 0 signifies the CS mode is operation; ergy consumption. The objective function is the same as the first- d is the cooling demand (kW). The meaning of the subscripts is as fol­ layer optimization. The constraint conditions are: lows: s,l and s,u are the lower and upper limits of the cold storage water Tct,o ≥ Twet + Tapp,l (12) flow rate, respectively; r,l and r,u are the lower and upper limits of the cold release water flow rate, respectively. where the T represents the temperature (◦ C). The meaning of the sub­ scripts is as follows: ct,o represents the cooling tower outlet water; wet (2) The constraint condition for the cold storage tank volume is as represents the wet-bult; app,l represents the minimum approach tem­ follows: perature of cooling tower. The minimum approach temperature of ( ) ∑h ( ) cooling tower is 1 ◦ C [10]. QV,l ≤ S*α + Qm + Qf h − dh *α ≤ QV,u (11) n=1 ΔTct,l ≤ ΔTct ≤ ΔTct,u (13)
### Page 5

Supply temperature of chilled water 18 18 18 Table 4 Return temperature of chilled water 24 24 24 Critical value in objective function and constraints. Tct,o (winter) 17 17 Optimized Tapp (summer) 3 3 Optimized PLRu PLRl Gu Gd GV,s,l/GV,r,l GV,s,u/GV,r,u α ΔTct 6 6 Optimized 3 3 3 3 (%) (%) m /h m /h m /h m /h ​ Tsmh 20 20 Optimized 100 30 600 200 40 2000 5 %/24 Tshf 14 14 Optimized
### Page 6

1 strategy and the DMPC strategy are shown in Table 5: (1) The supply uses random input samples to simulate runs repeatedly, gener­ temperature of chilled water for three strategies is 18 ◦ C and return ating multiple sets of outputs. temperature is 24 ◦ C. (2) For both the traditional control strategy and (3) The data results are analyzed, and a probability density map is MPC-1 strategy, the Tct,o is17 ◦ C in winter; the Tapp is 3 ◦ C in summer; created. Statistical characteristics such as mean value, interme­ and the ΔTct is 6 ◦ C. For DMPC strategy, the Tapp is more than 1 ◦ C; the diate value and standard deviation can be obtained. The mean range of ΔTct is 4–8 ◦ C; and the Tct,o, Tapp, and ΔTct are optimized. (3) For value reflects the effect of the control performance, while the both the traditional control strategy and MPC-1 strategy, the switch wet- standard deviation indicates the robustness of the control strat­ bulb temperature of MC mode and HC mode (Tsmh) is 20 ◦ C; and the egy. A smaller standard deviation implies that the control strat­ switch wet-bulb temperature of HC mode and FC mode (Tshf) is 14 ◦ C. egy is less affected by parameter uncertainty and has better For DMPC strategy, the Tsmh and Tshf are optimized. robustness.
### Page 12

shown in Fig. 11. For the traditional control strategy, the cooling ca­ approaching temperature (3), the cooling capacity of water tank (5) also pacity of water tank (5) and the cold release pump water flow rate (9) has a significant impact. Due to the impact of approaching temperature have no impact on the system. This is because the traditional control (3) on the COP of the chiller, it has a significant impact on the system. strategy does not perform cold storage/release regulation. For MPC-1 The cooling capacity of water tank (5) can affect the cooling capacity of and DMPC strategies, in addition to COP (6) and cooling tower the chiller and affect the regulation of cold storage/release in the later

## 公式/优化模型候选

### Page 2

```text
T           Temperature (◦ C)                                               MILP      Mixed integer linear programming
    ΔT          Temperature difference (◦ C)                                    PSO       Particle swarm optimization
    P           Power (kW)                                                      MPC-1     A benchmark MPC strategy compared to DMPC
```
### Page 2

```text
d           Cooling demand (kW)                                             sys        Cooling system
    α           Cooling capacity loss of the cold water storage tank            m          Cooling mode is mechanical or hybrid cooling mode
    k           Number of input factors with uncertainty                        f          Cooling mode is free cooling mode
```
### Page 2

```text
k           Number of input factors with uncertainty                        f          Cooling mode is free cooling mode
    Δ           Quantile variation of uncertain input parameters                u          Upper limit
    x           Normalized values of uncertain input parameters                 l          Lower limit
```
### Page 2

```text
EE          Fundamental effect of uncertain input parameters                s,u        Upper limit of the cold storage water flow rate
    μ           Mean value                                                      r,l        Lower limit of the cold release water flow rate
    σ           Standard deviation                                              r,u        Upper limit of the cold release water flow rate
```
### Page 2

```text
μ           Mean value                                                      r,l        Lower limit of the cold release water flow rate
    σ           Standard deviation                                              r,u        Upper limit of the cold release water flow rate
                                                                                V          Volume of cold water storage tank
```
### Page 3

```text
(pPUE) values for the cooling equipment in the computer room and the              temperature of cooling tower (Tapp) (1–5 ◦ C), temperature difference
power distribution system are fixed, being 0.054 and 0.06 respectively.           between supply and return water of cooling tower (ΔTct) (4–8 ◦ C) [10];
    The schematic diagram of the studied data center cooling system is            The optimization domain is 24 h; In this case, the solution space is
```
### Page 4

```text
Air flow rate: 651132 m3/h
                                                                                               optimization include the Tapp, and ΔTct.
  Cold water storage          3000m3                                           1                   The objective function of the first-layer optimization is to minimize
```
### Page 4

```text
∑H
                                                                                               min h=h Psys,h                                                         (1)
                                                                                                                1
```
### Page 4

```text
Psys = Pm + Pf                                                                            (2)
                                                                                                       ∑PLRu ∑Nu
```
### Page 4

```text
Psys = Pm + Pf                                                                            (2)
                                                                                                       ∑PLRu ∑Nu
                                                                                               Pm =           i=PLRl         k=0
```
### Page 4

```text
∑PLRu ∑Nu
                                                                                               Pm =           i=PLRl         k=0
                                                                                                                                    Dk,i Pk,i                                            (3)
```
### Page 4

```text
∑Gu ∑Nu
                                                                                               Pf =           j=Gl         k=0
```
### Page 4

```text
∑Gu ∑Nu
                                                                                               Pf =           j=Gl         k=0
                                                                                                                                 Uk,j Pk,j                                               (4)
```
### Page 4

```text
∑PLRu ∑Nu                            ∑Gu ∑Nu
                                                                                                     i=PLRl          k=0
```
### Page 5

```text
where Q represents the cooling capacity (kW); Z is a sufficiently large              (1) Initialize set parameters and operating parameters, including Tapp
positive constant; The value of Y indicates the cold storage/release                         and ΔTct.
operational status of either the CR mode or the CS mode, where 1 sig­                    (2) Calculate the objective function, aiming to minimize system en­
```
### Page 5

```text
lows: s,l and s,u are the lower and upper limits of the cold storage water
                                                                                      Tct,o ≥ Twet + Tapp,l                                                    (12)
flow rate, respectively; r,l and r,u are the lower and upper limits of the
```
### Page 5

```text
(                     )
               ∑h (         )                                                         cooling tower is 1 ◦ C [10].
QV,l ≤ S*α +         Qm + Qf h − dh *α ≤ QV,u                   (11)
```
### Page 5

```text
∑h (         )                                                         cooling tower is 1 ◦ C [10].
QV,l ≤ S*α +         Qm + Qf h − dh *α ≤ QV,u                   (11)
                 n=1
```
### Page 5

```text
n=1
                                                                                      ΔTct,l ≤ ΔTct ≤ ΔTct,u                                                   (13)
```
### Page 5

```text
where the subscript V is the volume of cold storage tank. α is the cooling            where ΔT subscript represents the temperature difference (◦ C); The
capacity loss of the water tank for 1 h. S is the initial cold storage ca­            subscript ct,l represents the minimum ΔTct (4 ◦ C); The subscript ct,u
```
### Page 5

```text
capacity loss of the water tank for 1 h. S is the initial cold storage ca­            subscript ct,l represents the minimum ΔTct (4 ◦ C); The subscript ct,u
pacity of the cold storage tank before entering each optimization.                    represents the maximum ΔTct (8 ◦ C).
    Table 4 presents the critical values for the MILP algorithm. In
```
### Page 5

```text
The optimization variables of second-layer optimization (PSO algo­                The working conditions for three strategies.
rithm) include Tapp and ΔTct. The specific steps are as follows.
                                                                                                                              Strategy
```
### Page 6

```text
MPC-1 strategy, the Tct,o is17 ◦ C in winter; the Tapp is 3 ◦ C in summer;                 created. Statistical characteristics such as mean value, interme­
and the ΔTct is 6 ◦ C. For DMPC strategy, the Tapp is more than 1 ◦ C; the                 diate value and standard deviation can be obtained. The mean
range of ΔTct is 4–8 ◦ C; and the Tct,o, Tapp, and ΔTct are optimized. (3) For             value reflects the effect of the control performance, while the
```
### Page 6

```text
and the ΔTct is 6 ◦ C. For DMPC strategy, the Tapp is more than 1 ◦ C; the                 diate value and standard deviation can be obtained. The mean
range of ΔTct is 4–8 ◦ C; and the Tct,o, Tapp, and ΔTct are optimized. (3) For             value reflects the effect of the control performance, while the
both the traditional control strategy and MPC-1 strategy, the switch wet-                  standard deviation indicates the robustness of the control strat­
```
### Page 7

```text
[ (                                           )       ]
           f x1 , x2 , …, xj− 1 , xj + Δi , xj+1 , …, xk − f(X)                             chiller, resulting in reduced cooling capacity. The cold storage tank is
EEj (X) =                                                                        (14)       utilized to supplement the cooling capacity required in the computer
```
### Page 7

```text
f x1 , x2 , …, xj− 1 , xj + Δi , xj+1 , …, xk − f(X)                             chiller, resulting in reduced cooling capacity. The cold storage tank is
EEj (X) =                                                                        (14)       utilized to supplement the cooling capacity required in the computer
                                      Δi
```
### Page 7

```text
room. The COP of MPC-1 strategy is 9.66 by optimizing the number of
    where any x is the normalized value of uncertain input parameters. Δ                    chillers through the cold storage technology. The COP of DMPC strategy
is the quantile variation of uncertain input parameters. f is the objective                 is 10.26 by optimizing the PLR and number of chillers through the cold
```
### Page 7

```text
rameters. The Morris analysis method provides two sensitivity measures                      COP of the chiller of MPC-1 and DMPC strategies increased by 11.55 %
for each input factor [36], which are the mean value (μ) and standard                       and 18.48 %, respectively. Studies have shown that the cooperative
deviation (σ). The μ gauges the importance of input factors. Larger μ                       operation of cold storage tank and chillers can effectively reduce energy
```
### Page 7

```text
for each input factor [36], which are the mean value (μ) and standard                       and 18.48 %, respectively. Studies have shown that the cooperative
deviation (σ). The μ gauges the importance of input factors. Larger μ                       operation of cold storage tank and chillers can effectively reduce energy
means more significant impact to model output. The σ characterizes                          consumption [14,32]. In addition, experiments have demonstrated that
```
### Page 7

```text
deviation (σ). The μ gauges the importance of input factors. Larger μ                       operation of cold storage tank and chillers can effectively reduce energy
means more significant impact to model output. The σ characterizes                          consumption [14,32]. In addition, experiments have demonstrated that
nonlinear effects and interactions between input factors.                                   such strategies can improve the COP of chillers [16].
```
### Page 7

```text
Both uncertainty analysis and Morris analysis use the same distri­                          In Fig. 5 (c), the Tapp of traditional and MPC-1 strategy is 3 ◦ C. The
bution of input parameters. The quantification of probability distribu­                     average Tapp of DMPC strategy is around 1.8 ◦ C, and the ΔTct is adjusted
tion for each input uncertainty parameter adheres to a normal                               to 8 ◦ C. In Fig. 5 (d), both MPC-1 and DMPC strategies have a PLR of
```
### Page 7

```text
Monte-Carlo simulations is 80 (sampling times) * 3 (3 control strategies)                   traditional control strategy, and DMPC strategy further improved the
= 240 times. In Morris sensitivity analysis, the minimum number of                          chiller COP. Although reducing the Tapp increases the energy con­
samples for each control strategy is 200 [37], and the number of simu­                      sumption of the cooling tower fan, it has a greater impact on the
```
### Page 8

```text
strategies is around 17 ◦ C, indicating that setting the Tct,o for FC mode to       4.2. Quantification of the impact of uncertainty on control performance
17 ◦ C is optimal. The ΔTct of the DMPC strategy is 8 ◦ C, which is the main
reason why the DMPC strategy reduces PUE in Fig. 7 (d).                                 The histograms of energy consumption and mode prediction error
```
### Page 11

```text
temperature between free and hybrid cooling modes. Due to un­                     control strategies on August 25th, February 1st, and January 13th is
certainties in the outdoor Twet and the Tapp, there is cooling mode pre­          33.18 × 103~39.10 × 103 kWh, 16.56 × 103~19.86 × 103 kWh, 9.08 ×
diction error when the cooling mode switching occurs. Therefore, the              103~10.51 × 103 kWh, the coefficient of variation reached 3.53, 4.25,
```
### Page 11

```text
certainties in the outdoor Twet and the Tapp, there is cooling mode pre­          33.18 × 103~39.10 × 103 kWh, 16.56 × 103~19.86 × 103 kWh, 9.08 ×
diction error when the cooling mode switching occurs. Therefore, the              103~10.51 × 103 kWh, the coefficient of variation reached 3.53, 4.25,
errors in cooling mode prediction are concentrated within these 2–4 h.            and 3.22. This means that the control performance of traditional, MPC-1
```
### Page 12

```text
Summary of the results of uncertainty performance.
  Index                      System energy consumption × 103(kWh)        Cold storage/release mode prediction error (%)       Cooling mode prediction error (%)
```
### Page 12

```text
Coefficient of variation = (Standard deviation/Mean) × 100 %.
```

## 符号表/变量定义候选

### Page 2

```text
Nomenclature                                                                CR        Cold release
                                                                                CN        Cold normal
    T           Temperature (◦ C)                                               MILP      Mixed integer linear programming
    ΔT          Temperature difference (◦ C)                                    PSO       Particle swarm optimization
    P           Power (kW)                                                      MPC-1     A benchmark MPC strategy compared to DMPC
    G           Water flow rate (m3/h)
    N           Number of the cooling unit                                      Subscripts
    H           Deadline of one cycle optimization time domain                  wet        Wet-bulb temperature
    h           Time                                                            smh        Switch wet-bulb temperature of mechanical and hybrid
    D           A value of 0 or 1                                                          cooling mode
    U           A value of 0 or 1                                               shf        Switch wet-bulb temperature of hybrid and free cooling
    Q           Cooling capacity (kW)                                                      mode
    Z           A sufficiently large positive constant                          app        Approach temperature
    Y           A value of 0 or 1                                               ct         Cooling tower
    d           Cooling demand (kW)                                             sys        Cooling system
    α           Cooling capacity loss of the cold water storage tank            m          Cooling mode is mechanical or hybrid cooling mode
    k           Number of input factors with uncertainty                        f          Cooling mode is free cooling mode
    Δ           Quantile variation of uncertain input parameters                u          Upper limit
    x           Normalized values of uncertain input parameters                 l          Lower limit
    f           Objective estimation function                                   s,l        Lower limit of the cold storage water flow rate
    EE          Fundamental effect of uncertain input parameters                s,u        Upper limit of the cold storage water flow rate
    μ           Mean value                                                      r,l        Lower limit of the cold release water flow rate
    σ           Standard deviation                                              r,u        Upper limit of the cold release water flow rate
                                                                                V          Volume of cold water storage tank
    Acronyms                                                                    cow        Cooling water flow rate
    MPC      Model predictive control                                           chw        Chilled water flow rate
    DMPC     Double-layer model predictive control                              csw        Cold storage water flow rate
    PUE      Power usage effectiveness                                          crw        Cold release water flow rate
    COP      Coefficient of performance                                         ct,i       Cooling tower inlet water temperature
    EER      Energy efficiency ratio                                            ct,o       Cooling tower outlet water temperature
    IT       Information technology                                             app,l      Minimum approach temperature of cooling tower
    PLR      Partial load rate                                                  ct,l       Minimum temperature difference of cooling tower
    pPUE     Partial PUE                                                        ct,u       Maximum temperature difference of cooling tower
    MC       Mechanical cooling                                                 wt         Water tank
    FC       Free cooling                                                       a,in       Inlet air temperature
    HC       Hybrid cooling                                                     a,re       Return air temperature
    CS       Cold storage
storage technology in data center. In addition to improving the control         like outdoor temperature, outdoor relative humidity, and the rate of air
strategy, optimizing set parameters can also improve energy efficiency          exchange exert considerable impact on the cooling load. Wang et al.
[17,18]. Wang et al. [19] optimized the indoor temperature setting              [25] used the Morris method to conduct sensitivity analysis on uncertain
value for switching between mechanical and hybrid cooling mode using            parameters, and found that uncertainty has a greater impact on the
MPC strategy. Compared to baseline strategy with the fixed setting              control performance of optimization strategy than traditional control
value, the energy savings of air conditioner reached 48.75 %. Zou et al.        strategy.
[20] find that when the condenser inlet water temperature ranges from               Most research focuses primarily on less than three uncertain pa­
10 to 22 ◦ C, R32 exhibits a cooling capacity that is 5.4 %–15.6 % higher       rameters affecting the cooling system in conventional buildings
compared to R22 and R134a. However, in hybrid cooling systems using             [26–28]. Only a few studies have mentioned the impact of multiple
cold storage technology, there has been little research on optimizing           parameter uncertainties on the cooling system in data center [25].
both the setting and operating parameters simultaneously with the MPC           However, the impact of model parameters uncertainty, measurement
strategy.                                                                       parameters uncertainty, and execution parameters uncertainty on the
    This MPC strategy is a supervisory control [9]. However, unavoid­           performance of MPC methods using cold storage technology has not
able factors such as uncertainty and errors can hinder the control per­         been studied for data centers.
formance and lead to suboptimal solutions [21,22]. Only a few studies               The control of hybrid cooling systems using cold storage technology
have addressed the uncertainty of MPC strategies for data center cooling        in data centers is complex and influenced by many factors. The uncer­
systems. Huang et al. [23] used stochastic optimization methods to solve        tainty of data center cooling systems mainly comes from three sources:
the uncertainty problem in temperature prediction, and found that the           uncertainty of model parameters, uncertainty of measurement param­
operation cost of scheduling varied with the level of temperature pre­          eters (measurement error), and uncertainty of execution parameters
diction uncertainty. Lin et al. [24] used uncertainty analysis and              (execution error) [29]. Minor variations in some uncertain parameters
Bayesian calibration to reveal and compare the effects of primary pa­           can result in considerable fluctuations in energy usage. However, some
rameters on cooling loads, and found that outdoor temperature, outdoor          negligible uncertain parameters hardly affect performance [30]. Striv­
relative humidity, and air exchange rate have significant effects on the        ing for pinpoint precision in every parameter invariably amplifies the
cooling load in different regions. Lin et al. [24] compared and analyzed        computational burden on the model and necessitates greater in­
the impact of key parameters on cooling load, and indicated that factors        vestments in sensors and actuators [25]. Therefore, we must identify the
                                                                            2
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
