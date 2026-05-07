# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2009_Ma_Model_Predictive_Control_of_Thermal_Energy_Storage_in_Building_Cooling_S.pdf`
- 标题：Model Predictive Control of Thermal Energy Storage in Building Cooling Systems
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

p2-p4 hybrid/TES tank model; p5 MPC problem formulation; p6 Algorithm 1 Moving Window Blocking and invariant set.

TES-MPC 经典建模与终端可行性参考；非数据中心但高度支撑 MILP/MPC 叙事。

## 算法/控制流程候选

### Page 1

Model Predictive Control of Thermal Energy Storage in Building Cooling Systems Yudong Ma⋆ , Francesco Borrelli⋆ , Brandon Hencey⋄ , Andrew Packard⋆ , Scott Bortoff⋄
### Page 3

P = P ower(TCHW S , TCW S , ṁCHW S , Twb , TCHW R ). (2) where Twb is the temperature read from a wet bulb ther- mometer. The wet bulb temperature physically reflects the Fig. 1: Scheme plot of the chilling system temperature and humidity of the ambient air. The function P ower(·) is implemented as a 5-D look-up table (7 × 6 × 6 × 5 × 7) obtained by extensive simulations Temperature spectrum of water in the tank of a high fidelity model under various initial conditions. 10 2) Thermal Energy Storage Tank: We use assumption A1, 9 and also assume that the tank is part of a closed hydronic loop, that is, the mass flow rate entering (exiting) the tank Temperature (celcius Degree)
### Page 3

Ḣb = ṁb Cp TCHW S (3a) Fig. 2: Temperature distribution of water in the tank Ḣa = ṁa Cp Ta (3b) Tcmp,s = TCHW S (3c) Tcmp,r ṁcmp,r − Ta ṁa TCHW R = (3d) [A2] Lower-level controllers actuate chillers and cooling ṁCHW R towers in order to achieve a desired temperature of ṁCHW S ≥ ṁcmp,s (3e) condensed water produced by cooling towers TCW S,ref , mass flow rate of chilled water supplied by chillers where the variables have been defined in Tables I, II, III. ṁCHW S,ref and chilled water temperature TCHW S,ref . b) Discharging: If the flow rate produced by the chiller We neglect the dynamics of controlled chillers and is less than campus flow rate ṁcmp,s , tank will be discharged. cooling towers and assume that there is no tracking error The following equations model the dynamic of the tank in
### Page 4

Independently of the mode, the mass and internal energy 5) Zb : Height of the cool water in the tank below the conservation laws always hold: thermocline. żb = (ṁCHW S − ṁcmp,s )/ρ/Ac ; (5a) ża + żb = 0; (5b) F. Operation Constraints U̇a = Ḣa + Q̇b>a + Q̇Amb>a ; (5c) The following constraints avoid the malfunction of the system components. U̇b = Ḣb + Q̇a>b + Q̇Amb>b ; (5d) • TCW S,ref ∈ [285, 295]K.
### Page 4

and Q̇a>b (Q̇b>a ) is the heat conducted from warmer (cooler) • TCHW R ∈ [283, 295]K. water to cooler (warmer) water in the tank: 2 • Zb ∈ [0.1, 1]ztank . Q̇a>b = (Ta − Tb )(πrtank )k2 3) Campus Model: We use assumption A4 along with a G. Model Summary simple energy balance equation, and the campus load can be By collecting Equations (3)–(6), and also descretizing the represented as: system with sampling time of 1 hour, the dynamic equations can be compacted as following: Q̇cmp = ṁcmp Cp (Tcmp,r − Tcmp,s ) (6) x(t + 1) = f (x(t), u(t), d(t)) (7a) Where ṁcmp is mass flow rate to the campus; Tcmp,s is the temperature of water supplied to the campus; Tcmp,r denotes y(t) = g(x(t), u(t), d(t)); (7b) the temperature of water returning to the campus; Q̇cmp is where the summation of the heat load required from each campus  building. We use historical data of Tcmp,s , Tcmp,r and ṁcmp f1 (x(t), u(t), d(t)); if ṁCHW S ≤ ṁcmp f= in order to compute the possible range of Q̇cmp . Figure 3 f2 (x(t), u(t), d(t)); if ṁCHW S > ṁcmp plots historical daily campus load during Sep. 2008, and we u(t) = [TCW S,ref ; ṁCHW S ; TCHW S,ref ] ∈ U observe that the load has a period of one day. It is reasonable x(t) = [Ua ; Ub ; za ; zb ] to model the load as a periodic disturbance with periodic d(t) = [ṁcmp,s ] ∈ D(t) envelope constraints (the bounds are represented with thicker lines in Figure 3). y(t) = [TCHW R ; zb ] ∈ Y.
### Page 5

SUMMER Period A (May 1st though Oct. 31st) Peak 12:00–18:00 except holidays III. MPC PROBLEM FORMULATION Partial-peak 8:30–12:00 except holidays AND 18:00–9:30 This section presents the design of a MPC control whose Off-peak 21:30–8:30 Mon. through Fri. objective is to find the optimal control sequence so that we ALL DAY Sat., Sun, and holidays can satisfy the required cooling load while receiving the WINTER Period B (Nov. 1st though Apr. 30st) Partial-peak 8:30–21:30 except holidays lowest electricity bills. Consider the following optimization Off-peak 21:30–8:30 Mon. through Fri. problem: ALL DAY Sat., Sun, and holidays TABLE IV: Definition of time periods N X −1 ⋆ J (x(t), t) = min {kC(t + i)E(xi|t , ui|t )kS û0|t ,··· ,ûM −1|t Total Demand Rates ($ per kW) i=1 Maximum Peak Demand Summer $ 12.40 + kui|t kR } (9a) Maximum Part-Peek Demand Summer $ 2.74 Maximum Demand Summer $ 7.52 s.t. Maximum Part-Peak Demand Winter $ 1.04 yi|t ∈ Y, ∀i = 1, 2, · · · , N (9b) Maximum Demand Winter $ 7.52 TABLE V: Total Demand Rates ui|t ∈ U, ∀i = 1, 2, · · · , N (9c) yN |t ∈ Yf (t); (9d) Total Energy Rates ($ per kWh) E(xi|t , ui|t ) = P ower(xi|t , ui|t )∆T (9e) Peak Summer $ 0.13593 ′ ′ ′ ′ ′ Part-Peak Summer $ 0.09204 [u0|t , · · · , uN −1|t ] = B ⊗ Im [û0|t , · · · , ûM −1|t ] Off-Peak Summer $ 0.07392 (9f) Part-Peak Winter $ 0.08155 Off-Peak Winter $ 0.07118 xk+1|t = f (xk|t , uk|t , d(k)); (9g) TABLE VI: Total Energy Rates yk|t = g(xk|t , uk|t , d(k)); (9h) d(k) ∈ D(k), ∀k = 1, 2, · · · , N (9i)
### Page 7

replaced by the data from weather stations in future work. 276 0 20 40 60 80 100 120 140 160 180 1) Current Manual Operation: The cooling system in time (hour) UC Merced is operated manually with following control input sequences. The temperatures set-points TCW S,ref and Fig. 7: Simulation result of MPC controller TCHW S,ref are kept constant to 286.26K and 277.04K respectively, and the chiller will be ON around 10pm to 2am TCWS every two days to charge the tank to full with a constant mass 292 MPC flow rate of 138Kg/s and the chiller is off the rest of time. Heuristic Simulation results plotted in Figure 6 shows that the system 290 TCWS (K)
### Page 7

0 mdotCHWS 0 20 40 60 80 100 120 140 160 180 time (hour) 250 MPC 30 mass flow rate (Kg/s) Zb (m)
### Page 7

277.5 (b) Control input ṁCHW S 277 0 20 40 60 80 100 120 140 160 180 TCHWS time (hour) MPC 280 Heuristic Fig. 6: Simulation results of the heuristic controller TCHWS (K)
### Page 7

278 2) Operation With MPC Controller: Simulation results plotted in Figure 7 shows that the system converges to a 276 periodic operation. Figure 8 reports the control inputs of heuristic control logic and MPC controller. The system states 274 evolution is shown in Figure 7. We can observe that the 0 20 40 60 80 100 120 140 160 180 time (hour) height and the temperature of the cold water in the tank (c) Control input TCHW S behaves periodically over the time. The optimal MPC policy does not charge the tank to the full capacity an thus avoiding Fig. 8: MPC Control Sequence

## 公式/优化模型候选

### Page 2

```text
parameters         description
     vary building cooling demand. Persistent feasibility is               ρ:             fluid density [kg/m3 ]
     obtained in our scheme by using a time-varying periodic              Ac :            cross sectional area of tank [m2 ]
```
### Page 2

```text
to the tank. Figure 1 shows the main scheme of the system. B. Simplifying Assumptions
   The system consists of a condenser loop, a primary loop, [A1] The water in the tank is subject to minor mixing
a secondary (campus) loop, and several tertiary (building)          and thus can be modeled as a stratified system with
```
### Page 3

```text
TCW S = TCW S,ref                     (1a)
                                                                                                                                ṁCHW S = ṁCHW S,ref                 (1b)
```
### Page 3

```text
TCW S = TCW S,ref                     (1a)
                                                                                                                                ṁCHW S = ṁCHW S,ref                 (1b)
                                                                                                                                TCHW S = TCHW S,ref                   (1c)
```
### Page 3

```text
ṁCHW S = ṁCHW S,ref                 (1b)
                                                                                                                                TCHW S = TCHW S,ref                   (1c)
```
### Page 3

```text
P = P ower(TCHW S , TCW S , ṁCHW S , Twb , TCHW R ).
                                                                                                                                                                      (2)
```
### Page 3

```text
The function P ower(·) is implemented as a 5-D look-up
                                                                                                           table (7 × 6 × 6 × 5 × 7) obtained by extensive simulations
                                                Temperature spectrum of water in the tank                  of a high fidelity model under various initial conditions.
```
### Page 3

```text
Ḣb = ṁb Cp TCHW S                           (3a)
                                             Fig. 2: Temperature distribution of water in the tank
```
### Page 3

```text
Fig. 2: Temperature distribution of water in the tank
                                                                                                                        Ḣa = ṁa Cp Ta                               (3b)
                                                                                                                        Tcmp,s = TCHW S                               (3c)
```
### Page 3

```text
Ḣa = ṁa Cp Ta                               (3b)
                                                                                                                        Tcmp,s = TCHW S                               (3c)
                                                                                                                                  Tcmp,r ṁcmp,r − Ta ṁa
```
### Page 4

```text
the chiller.
                                   Ḣa = ṁa Cp Tcmp,r                             (4a)
                                   Ḣb = ṁb Cp Tb                                 (4b)     2) Ta : Temperature of the cool water in the tank.
```
### Page 4

```text
Ḣa = ṁa Cp Tcmp,r                             (4a)
                                   Ḣb = ṁb Cp Tb                                 (4b)     2) Ta : Temperature of the cool water in the tank.
                                             TCHW S ṁCHW S − Tb ṁb
```
### Page 4

```text
TCHW S ṁCHW S − Tb ṁb
                                   Tcmp,s =                                        (4c)
                                                      ṁcmp                                 3) Tb : Temperature of the warm water in the tank.
```
### Page 4

```text
ṁcmp                                 3) Tb : Temperature of the warm water in the tank.
                                   TCHW R = Tcmp,r                                 (4d)
                                                                                            4) Za : Height of the warm water in the tank above the
```
### Page 4

```text
4) Za : Height of the warm water in the tank above the
                                   ṁCHW S ≤ ṁcmp,s                               (4e)
                                                                                               thermocline.
```
### Page 4

```text
conservation laws always hold:                                                                 thermocline.
                                    żb = (ṁCHW S − ṁcmp,s )/ρ/Ac ;              (5a)
                                    ża + żb = 0;                                 (5b)   F. Operation Constraints
```
### Page 4

```text
żb = (ṁCHW S − ṁcmp,s )/ρ/Ac ;              (5a)
                                    ża + żb = 0;                                 (5b)   F. Operation Constraints
                                    U̇a = Ḣa + Q̇b>a + Q̇Amb>a ;                  (5c)     The following constraints avoid the malfunction of the
```
### Page 4

```text
ża + żb = 0;                                 (5b)   F. Operation Constraints
                                    U̇a = Ḣa + Q̇b>a + Q̇Amb>a ;                  (5c)     The following constraints avoid the malfunction of the
                                                                                          system components.
```
### Page 5

```text
⋆
                                                                        J (x(t), t) =          min                     {kC(t + i)E(xi|t , ui|t )kS
                                                                                         û0|t ,··· ,ûM −1|t
```
### Page 5

```text
û0|t ,··· ,ûM −1|t
           Total Demand Rates ($ per kW)                                                                        i=1
           Maximum Peak Demand Summer                      $ 12.40                       + kui|t kR }                                            (9a)
```
### Page 5

```text
Maximum Demand Summer                           $ 7.52                 s.t.
           Maximum Part-Peak Demand Winter                 $ 1.04                     yi|t ∈ Y, ∀i = 1, 2, · · · , N                             (9b)
           Maximum Demand Winter                           $ 7.52
```
### Page 5

```text
TABLE V: Total Demand Rates
                                                                                      ui|t ∈ U, ∀i = 1, 2, · · · , N                             (9c)
                                                                                      yN |t ∈ Yf (t);                                         (9d)
```
### Page 5

```text
yN |t ∈ Yf (t);                                         (9d)
               Total Energy Rates ($ per kWh)                                         E(xi|t , ui|t ) = P ower(xi|t , ui|t )∆T                (9e)
               Peak Summer                         $ 0.13593
```
### Page 5

```text
′              ′       ′            ′               ′
               Part-Peak Summer                    $ 0.09204                          [u0|t , · · · , uN −1|t ] = B ⊗ Im [û0|t , · · · , ûM −1|t ]
               Off-Peak Summer                     $ 0.07392                                                                                   (9f)
```
### Page 5

```text
Part-Peak Winter                    $ 0.08155
               Off-Peak Winter                     $ 0.07118                          xk+1|t = f (xk|t , uk|t , d(k));                           (9g)
                       TABLE VI: Total Energy Rates                                   yk|t = g(xk|t , uk|t , d(k));                              (9h)
```
### Page 5

```text
Off-Peak Winter                     $ 0.07118                          xk+1|t = f (xk|t , uk|t , d(k));                           (9g)
                       TABLE VI: Total Energy Rates                                   yk|t = g(xk|t , uk|t , d(k));                              (9h)
                                                                                      d(k) ∈ D(k), ∀k = 1, 2, · · · , N                          (9i)
```
### Page 6

```text
Tank operation mode profile
                                                                      length matrices for each step. In this work, we choose L0 =
  1
```
### Page 6

```text
[2, 2, 18, 1, 1, 0], and Algorithm 1 will give
  0                                                                                      L1 = [1, 2, 18, 1, 1, 1]
                                                                                         L2 = [2, 18, 1, 1, 2, 0]
```
### Page 6

```text
0                                                                                      L1 = [1, 2, 18, 1, 1, 1]
                                                                                         L2 = [2, 18, 1, 1, 2, 0]
 −1
```
### Page 6

```text
−1
   0              5               10              15        20                          L3 = [1, 18, 1, 1, 2, 1]
                                    time(hour)
```
### Page 6

```text
time(hour)
                                                                                        L4 = [18, 1, 1, 2, 2, 0]
                      Fig. 4: Tank Operation Mode Profile
```
### Page 6

```text
.
                                                                                        L24 = [2, 2, 18, 1, 1, 0]
B. Move Blocking Strategy
```
### Page 6

```text
paper, we are using the Moving Window Blocking approach
                                                                      feasible for t ≥ 0.
proposed in [20], We first need the following definitions
```
### Page 6

```text
is said to be a robust control invariant set for system (7) if
B ∈ {0, 1}N ×M is an admissible blocking matrix if
                                                                      for every
```

## 符号表/变量定义候选

### Page 2

```text
A. Nomenclature
following day, the chilled water is pumped from the tank and
distributed throughout the campus. Secondary pumps draw           The following variables, parameters and subscripts will be
water from the distribution system into each building, where used in this paper.
it runs through a set of air-handler units (AHUs) and returns
to the tank. Figure 1 shows the main scheme of the system. B. Simplifying Assumptions
   The system consists of a condenser loop, a primary loop, [A1] The water in the tank is subject to minor mixing
a secondary (campus) loop, and several tertiary (building)          and thus can be modeled as a stratified system with
loops. The chilled water is generated via chillers and cooling      layers of warmer water (285 K) at the top and cooler
towers within the the primary and condenser loops. The              water (277 K) at the bottom. Figure 2 depicts the
chilled water is stored in a stratified thermal energy stor-        temperature of the water measured inside the tank
age tank. The chilled water is distributed to the buildings         at different heights at 8:30am on the 29th of Nov.
throughout campus via the secondary loop. The tertiary loop         2007. One can observe a steep temperature gradient
uses pumps and valves within each building to distribute the        over the height of the tank, which is known as a
chilled water for consumption by the cooling coils and air          thermocline. For this reason we lump warmer water
handling units (AHUs). The chilled water is warmed by the           above the thermocline and cooler water below the
air-side cooling load of the buildings and returned to the          thermocline to obtain a 4-state system describing the
secondary loop.                                                     height and temperature of the warmer and cooler water,
   The next section presents a dynamic model of the system.         respectively. Note that in this paper cooler (warmer)
Our objective is to develop a simplified yet descriptive model      water means water that is cooler (warmer) than the
which can be used for real time optimization in a MPC               thermocline.
scheme.
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
