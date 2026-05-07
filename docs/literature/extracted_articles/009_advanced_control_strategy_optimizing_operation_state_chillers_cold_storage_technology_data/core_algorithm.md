# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2023_Zhu_An_advanced_control_strategy_for_optimizing_the_operation_state_of_chill.pdf`
- 标题：An advanced control strategy for optimizing the operation state of chillers with cold storage technology in data center
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

Keywords: Data centers facing huge energy consumption challenges, the chiller is one of the main energy expenditure Data center equipment. This study proposed a novel efficient operation strategy for chillers integrated with cold water Model predictive control (MPC) storage technology. An advanced model predictive control (MPC) was developed to regulate the running pa­ Water storage rameters of the chillers and cold water storage device, targeting the maximum energy efficiency of cooling Mixed integer linear programming (MILP) Model mismatch system. Specifically, the mixed integer linear programming (MILP) algorithm was constructed in MPC with low computer calculation cost to solve the optimization problem. The performance of the MPC strategy was validated through an actual data center test located at Guangzhou city and further comprehensively assessed through annual simulations. The relative error in terms of refrigeration capacity and cooling capacity of cold water storage device between simulation and field test was less than 5 %. During the on-site testing, compared with a Baseline strategy, the coefficient of performance (COP) of the MPC strategy increased by 1.96 on average with the cooling system energy consumption reduced by 5.8 %, and the power usage effectiveness (PUE) was reduced by 0.013. The annual PUE decreased by 0.018 and the annual electricity cost decreased by 21 % when the IT power was 4570 kW based on the simulation. In addition, the effect of model mismatch was quantified by setting the deviation degree of the chiller partial load rate (PLR).
### Page 9

Table 5 7-hour cold storage and release cycle was carried out. Actually, a 24- Conditions for annual simulation. hour cycle for cold storage and release regulation offers more flexi­ Supply temperature of Return temperature of Water IT power bility, which results in more energy savings compared to a 7-hour cycle. chilled water (◦ C) chilled water (◦ C) temperature (kW) A 7-hour Baseline strategy test was conducted from 23:00 on December difference (◦ C) 8, 2022 to 6:00 on December 9, 2022, and the corresponding MPC NC: 18 NC: 24 6 4570/ strategy test was conducted for the same period of next day. The outdoor CSC: 17 CSC: 23 7880/ wet bulb temperature during the MPC and Baseline tests is shown in the 11250 Fig. 4. The temperature of MPC strategy is slightly higher than Baseline strategy, which is unfavorable for the cooling system. The minimum, average temperature and maximum temperature deviations between the two periods is 0.15 ◦ C, 0.37 ◦ C, 0.58 ◦ C, respectively.
### Page 10

In order to further analyze the annual energy-saving performance of 4. Results and analysis the MPC strategy, the annual simulation study at Guangzhou city is conducted. The hourly meteorological data for typical meteorological 4.1. Analysis of experimental results year provided by the National Meteorological Administration and Tsinghua University is selected. The simulation conditions are shown in Fig. 5 shows the refrigeration capacity of the simulation and exper­ Table 5. The annual simulations are conducted for IT powers of 4570 iment. Fig. 6 shows the capacity of the water storage device of the kW, 7880 kW, and 11250 kW. The parameter settings are the same as the simulation and experiment. The average relative errors between the field test: After experimental testing, the approach temperature of the simulated and actual values for both refrigeration capacity and water cold storage plate exchanger is 1 ◦ C, so the chilled water supply tem­ storage device capacity are within 5 %. Fig. 5 shows that the refrigera­ perature of NC and CSC is set to 18 ◦ C and 17 ◦ C, respectively; the chilled tion capacity of the simulation is higher than experiment. The measured water return temperature of NC and CSC is set to 24 ◦ C and 23 ◦ C, cooling capacity is about 0.85 time of the IT power, since the test is respectively. conducted in December when the outdoor temperature is lower and heat
### Page 12

0.013 reduction, so the energy saving effect of the MPC proposed is chillers; Qope is the cooling capacity of all operating chillers (kW); Pope is significant. the energy consumption of all operating chillers (kW). The comprehensive COP for operating chillers is expressed by the following formula: 4.2. Analysis of simulation results Qope CCOP = (14) Pope The simulation analysis based on the MPC and Baseline strategies is where CCOP represents the comprehensive COP for operating carried out at IT power of 4570 kW, 7880 kW and 11250 kW. As shown in Fig. 9, at 4570 kW, both the PUE reduction and the electricity cost
### Page 14

4.3. Influence of model mismatch on system performance 0.1), positive right deviation of 0.2 (PD 0.2), negative left deviation of 0.1 (ND 0.1) and negative left deviation of 0.2 (ND 0.2), as shown in Because the core idea of the MPC strategy is to regulate the operation Fig. 16. of the chiller in the best state through the cold storage and release. The mismatch degree of chiller model is expressed by the following Therefore, the MPC strategy has a strong dependence on the perfor­ formula: mance of the chiller, so it is necessary to quantify the impact of chiller 1 ∑|COPreal − COPdeviation | model mismatch on control performance. The chiller operates at the δ= × 100% (15) n n COPreal optimal PLR state point during cold release mode, the energy con­ sumption of other equipment is calculated accordingly. Therefore, the where δ represents the average mismatch degree of chiller; COPreal is total energy consumption of the system is most dependent on the chiller, the actual COP value; COPdeviation is the COP used in MPC algorithm; n so the mismatch degree of COP is discussed for the proposed model. represents moving windows range, here is 24. The chiller PLR is mismatched by positive right deviation of 0.1 (PD Fig. 17 shows the operation mode of the mismatched model and the

## 公式/优化模型候选

### Page 2

```text
Nomenclature                                                                                (kWh)
                                                                                     α          Cooling capacity loss of the cold water storage device for
    Tcwi          Supply temperature of the cooling water (◦ C)                                 one hour
```
### Page 2

```text
Ppump         Pump power (kW)                                                               release capacity of the cold release mode at time t (kW)
    ηpump         Pump efficiency                                                    Q3,XF,t    Difference between the cold storage capacity and the cold
    ηm            Motor efficiency                                                              release capacity of the normal cooling mode at time t (kW)
```
### Page 2

```text
ηpump         Pump efficiency                                                    Q3,XF,t    Difference between the cold storage capacity and the cold
    ηm            Motor efficiency                                                              release capacity of the normal cooling mode at time t (kW)
    ηv            Converter efficiency                                               Nrated     Rated number of the chiller
```
### Page 2

```text
ηm            Motor efficiency                                                              release capacity of the normal cooling mode at time t (kW)
    ηv            Converter efficiency                                               Nrated     Rated number of the chiller
    kpump         Pump speed ratio                                                   Zt         Decision variable with a value of 0 or 1
```
### Page 2

```text
Xt            Decision variable with a value of 0 or 1                           R          Continuous operation restriction of the chiller
    Ut            Decision variable with a value of 0 or 1                           δT         Decision variable with a value of 0 or 1
    Mt            Decision variable with a value of 0 or 1                           CCOP       Comprehensive COP for operating chillers
```
### Page 2

```text
P2            System energy consumption of the cold release mode (kW)            Pope       Energy consumption of all operating chillers (kW)
    P3            System energy consumption of the normal cooling mode               δ          Average mismatch degree of chiller
                  (kW)                                                               COPreal Actual COP value of chiller
```
### Page 5

```text
◦
                         Thermometer                  − 40–85   ±0.5
  Water velocity (m/s)   Electromagnetic flow meter   0.3–10    ±0.5 %             3. Control strategy
```
### Page 5

```text
Thermometer                  − 40–85   ±0.5
  Water velocity (m/s)   Electromagnetic flow meter   0.3–10    ±0.5 %             3. Control strategy
```
### Page 6

```text
COP = a0 + a1 PLR + a2 PLR2 + a3 (Tcwi                                                 performance simulation. However, this model may not be accurate due
                                                                                       to the difference between the real and rated conditions. Therefore, the
```
### Page 6

```text
(◦ C). The coefficients obtained according to the performance curve of                 The total energy consumption is calculated as shown in the Eq. (2);
the chiller provided by the manufacturer are as follows: a0 = 15.4115,                 Bernier [39] provides the relationship between pump speed, pump
a1 = 31.5538, a2 = -21.7164, a3 = -1.6674, a4 = 0.0502, a5 = -0.1831.                  motor efficiency, and converter efficiency, as shown in the Eq. (3), Eq.
```
### Page 6

```text
the chiller provided by the manufacturer are as follows: a0 = 15.4115,                 Bernier [39] provides the relationship between pump speed, pump
a1 = 31.5538, a2 = -21.7164, a3 = -1.6674, a4 = 0.0502, a5 = -0.1831.                  motor efficiency, and converter efficiency, as shown in the Eq. (3), Eq.
The R2 is 0.990. The above obtained COP curve is used for the annual                   (4).
```
### Page 7

```text
maximum
                                                                     temperature ≥
                                                                                             supply temperature supplied to the computer room, the NC cannot
```
### Page 7

```text
gmw Hw                                                                          volume, 15 min emergency cold storage capacity, and the continuous
Ppump =                                                                            (2)
          1000ηpump ηm ηv                                                                    operating time of the chiller. In the MILP method, the system energy
```
### Page 7

```text
Ppump =                                                                            (2)
          1000ηpump ηm ηv                                                                    operating time of the chiller. In the MILP method, the system energy
                                                                                             consumption for three modes at each time during the optimization
```
### Page 7

```text
(                   )
ηm = 0.94187 1 − e− 9.04kpump                                                      (3)       period is calculated in advance, and a selection is made among the three
                                                                                             modes during the optimization process. By optimizing the hourly cold
```
### Page 7

```text
2
ηv = 0.5087 + 1.283kpump − 1.42kpump          3
                                     + 0.5834kpump                                 (4)       storage and release mode, the duration cold storage and release mode
```
### Page 7

```text
where Hw is pump head (m); mw is mass flow rate (kg/s); Ppump is                              The objective function of the MILP is to minimize energy consump­
pump power (kW); ηpump is pump efficiency; ηm is motor efficiency; ηv is                     tion, as follows:
converter efficiency; kpump is pump speed ratio, that is, the ratio between                      ∑T (                          )
```
### Page 7

```text
pump power (kW); ηpump is pump efficiency; ηm is motor efficiency; ηv is                     tion, as follows:
converter efficiency; kpump is pump speed ratio, that is, the ratio between                      ∑T (                          )
the current and the rated flow rate.                                                         min t Xt P1,t + Ut P2,t + Mt P3,t                                        (6)
```
### Page 7

```text
optimized time domain.                                                                       have the condition that only one of them can be 1 at time t, which can be
                                                                                             expressed as Xt + Ut + Mt = 1.
    Step 4: The MILP algorithm for the cooling system is established. The
```
### Page 8

```text
the cooling capacity calculated as the smaller value between the                       (                                         ) (                               )
maximum flow rate of the cold release pipeline and the maximum                         ( Xt+1 N1,t+1 + Ut+1 N2,t+1 + Mt+1 N3,t+1 ) − ( Xt N1,t + Ut N2,t + Mt N3,t ) ≤ Pt
                                                                                      ≤ Xt+1 N1,t+1 + Ut+1 N2,t+1 + Mt+1 N3,t+1 − Xt N1,t + Ut N2,t + Mt N3,t + H*δt
```
### Page 8

```text
maximum flow rate of the cold release pipeline and the maximum                         ( Xt+1 N1,t+1 + Ut+1 N2,t+1 + Mt+1 N3,t+1 ) − ( Xt N1,t + Ut N2,t + Mt N3,t ) ≤ Pt
                                                                                      ≤ Xt+1 N1,t+1 + Ut+1 N2,t+1 + Mt+1 N3,t+1 − Xt N1,t + Ut N2,t + Mt N3,t + H*δt
release flow rate of the cold water storage device (1500 m3/h). H is a
```
### Page 8

```text
age capacity in the modes of cold storage, cold release and normal                     ( Xt N1,t +Ut N2,t +Mt N)3,t ( − Xt+1 N1,t+1 +Ut+1 N2,t+1 +Mt+1 N3,t+1
                                                                                                                                                         ) ≤Pt
                                                                                      ≤ Xt N1,t +Ut N2,t +Mt N3,t − Xt+1 N1,t+1 +Ut+1 N2,t+1 +Mt+1 N3,t+1 +H*(1− δt )
```
### Page 8

```text
) ≤Pt
                                                                                      ≤ Xt N1,t +Ut N2,t +Mt N3,t − Xt+1 N1,t+1 +Ut+1 N2,t+1 +Mt+1 N3,t+1 +H*(1− δt )
cooling at time t; Q1,dis,t, Q2,dis,t, and Q3,dis,t respectively represent the
```
### Page 8

```text
cold release capacity in the modes of cold storage, cold release and
normal cooling at time t.                                                             ∑R− 1
                                                                                         k=1
```
### Page 8

```text
k=1
                                                                                               Zt+k ≤ H*(1 − Zt )                                                  (13)
2) The constraint conditions for the volume of the cold water storage                     where Nrated is the total number of chillers in the system; Zt, Pt and δT
```
### Page 8

```text
Zt+k ≤ H*(1 − Zt )                                                  (13)
2) The constraint conditions for the volume of the cold water storage                     where Nrated is the total number of chillers in the system; Zt, Pt and δT
   device are as follows:                                                             is the decision variable; Zt is 0 or 1, which indicates whether the number
```
### Page 8

```text
device are as follows:                                                             is the decision variable; Zt is 0 or 1, which indicates whether the number
             ∑t (                                        )                            of chillers starts changes from t to t + 1. If Zt is 0, it indicates that the
QV,L ≤ S*α +         Xt Q1,XF,t + Ut Q2,XF,t + Mt Q3,XF,t *α ≤ QV,S (9)
```
### Page 12

```text
Qope
CCOP =                                                              (14)
       Pope                                                                         The simulation analysis based on the MPC and Baseline strategies is
```
### Page 14

```text
mance of the chiller, so it is necessary to quantify the impact of chiller
                                                                                       1 ∑|COPreal − COPdeviation |
model mismatch on control performance. The chiller operates at the                δ=                                × 100%                                 (15)
```
### Page 14

```text
1 ∑|COPreal − COPdeviation |
model mismatch on control performance. The chiller operates at the                δ=                                × 100%                                 (15)
                                                                                       n n       COPreal
```
### Page 14

```text
optimal PLR state point during cold release mode, the energy con­
sumption of other equipment is calculated accordingly. Therefore, the                where δ represents the average mismatch degree of chiller; COPreal is
total energy consumption of the system is most dependent on the chiller,          the actual COP value; COPdeviation is the COP used in MPC algorithm; n
```

## 符号表/变量定义候选

### Page 2

```text
Nomenclature                                                                                (kWh)
                                                                                     α          Cooling capacity loss of the cold water storage device for
    Tcwi          Supply temperature of the cooling water (◦ C)                                 one hour
    Tchws         Supply temperature of the chilled water (◦ C)                      Q1,XF,t    Difference between the cold storage capacity and the cold
    Hw            Pump head (m)                                                                 release capacity of the cold storage mode at time t (kW)
    mw            Mass flow rate (kg/s)                                              Q2,XF,t    Difference between the cold storage capacity and the cold
    Ppump         Pump power (kW)                                                               release capacity of the cold release mode at time t (kW)
    ηpump         Pump efficiency                                                    Q3,XF,t    Difference between the cold storage capacity and the cold
    ηm            Motor efficiency                                                              release capacity of the normal cooling mode at time t (kW)
    ηv            Converter efficiency                                               Nrated     Rated number of the chiller
    kpump         Pump speed ratio                                                   Zt         Decision variable with a value of 0 or 1
    PDC,total     Total energy consumption of the data center (kWh)                  Pt         Absolute value of the change quantity of the chillers at
    PIT           Total power of IT (kWh)                                                       time t + 1 and time t
    Xt            Decision variable with a value of 0 or 1                           R          Continuous operation restriction of the chiller
    Ut            Decision variable with a value of 0 or 1                           δT         Decision variable with a value of 0 or 1
    Mt            Decision variable with a value of 0 or 1                           CCOP       Comprehensive COP for operating chillers
    P1            System energy consumption of the cold storage mode (kW)            Qope       Cooling capacity of all operating chillers (kW)
    P2            System energy consumption of the cold release mode (kW)            Pope       Energy consumption of all operating chillers (kW)
    P3            System energy consumption of the normal cooling mode               δ          Average mismatch degree of chiller
                  (kW)                                                               COPreal Actual COP value of chiller
    T             Moving windows range (hours)                                       COPdeviation Deviation COP used in MPC algorithm
    Qsto,flow,L   Minimum cooling capacity calculated by the minimum                 n          Moving windows range
                  cold storage flow rate (kW)
    Qsto,flow,S   Maximum cooling capacity calculated by the minimum                 Acronyms
                  cold storage flow rate (kW)                                        MPC      Model predictive control
    Qdis,flow,L   Minimum cooling capacity calculated by the minimum                 MILP     Mixed integer linear programming
                  cold release flow rate (kW)                                        COP      Coefficient of performance
    Qdis,flow,S   Maximum cooling capacity calculated by the minimum                 PUE      Power usage effectiveness
                  cold release flow rate (kW)                                        IT       Information technology
    H             A sufficiently large positive constant                             PLR      Partial load rate
    Y1            Decision variable with a value of 0                                FCSC     Full cold storage control
    Y2            Decision variable with a value of 1                                PCSC     partial cold storage control
    Y3            Decision variable with a value of 0.5                              TES      Thermal energy storage
    Q1,sto,t      Cold storage capacity of cold storage mode at time t (kW)          MINLP Mixed integer nonlinear programming
    Q2,sto,t      Cold storage capacity of cold release mode at time t (kW)          CSC      Cold storage chiller
    Q3,sto,t      Cold storage capacity of normal cooling mode at time t             NC       Normal chiller
                  (kW)                                                               pPUE     Partial PUE
    Q1,dis,t      Cold release capacity of cold storage mode at time t (kW)          CRAC     Computer room air conditioner
    Q2,dis,t      Cold release capacity of cold release mode at time t (kW)          PDS      Power distribution system
    Q3,dis,t      Cold release capacity of normal cooling mode at time t             PD 0.1   Positive right deviation of 0.1
                  (kW)                                                               PD 0.2   Positive right deviation of 0.2
    QV,L          Lower limit of the capacity of the cold water storage device       ND 0.1 Negative left deviation of 0.1
                  (kWh)                                                              ND 0.2 Negative left deviation of 0.2
    QV,S          Upper limit of the capacity of the cold water storage device
IT load rate of data centers across the country is currently 50.1 %, and             algorithm [21], improved sparrow search algorithm [22], improved
some western regions are lower than 40 % [13]. Due to the rapid                      parallel particle swarm optimization algorithm [23] and other improved
establishment and expansion of data centers [1,2], the IT load rate of               algorithms. However, subjected to the existed cooling system configu­
newly built data centers is even far below 30 %. Thus, in the initial                ration, the adjustment range of chiller PLR is relatively limited, and
period, the chiller always runs under low PLR with low energy efficiency             chillers could not always operate at peak efficiency. In order to further
of the cooling system [14,15].                                                       improve the chillers working efficiency, the storage cooling technology
    In order to improve energy efficiency, simply adjusting the running              could be coordinated to adjust the PLR to achieve better energy con­
number of chillers to match the actual load demand is an effective PLR               servation [24–26].
management strategy. The optimized chiller sequencing control ach­                       Data center cooling systems are always equipped with cold water
ieves lower energy consumption without sacrificing the cooling demand                storage devices, which runs for 15 min emergency cooling in power
[16,17]. Huang et al. [18] optimized the number of operating chillers by             outage period [27]. However, due to the low IT load rate of newly built
switching critical point and the cooling water set point, which resulted             data centers, cold storage devices will still have sufficient capacity to
in a 5.3 % reduction in energy consumption of the chiller. Liu et al. [19]           participate in tuning chillers PLR without sacrificing 15 min emergency
further studied the optimized PLR operation strategy of the chillers                 cooling. Therefore, under safety requirements, cold storage devices
considered the chiller maximum cooling capacity under different                      could cooperate with chillers for their higher efficiency.
working conditions. Intelligent algorithms combined with the chiller                     The full cold storage control (FCSC) strategy and partial cold storage
sequencing control were also widely investigated, such as the improved               control (PCSC) strategy are widely used for load regulation. The cold
firefly algorithm approach [20], improved artificial fish swarm                      storage capacity of FCSC meets all the cooling loads of the daytime, but
                                                                                 2
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
