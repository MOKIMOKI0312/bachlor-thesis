# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2022_Kim_Site_demonstration_and_performance_evaluation_of_MPC_for_a_large_chiller.pdf`
- 标题：Site demonstration and performance evaluation of MPC for a large chiller plant with TES for renewable energy integration and grid decarbonization
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

p6-p8 MPC formulation/MILP/constraints; p10-p12 PV/TES performance; p14-p15 appendix tank and power model.

最接近当前 TES + PV + MPC + 冷站验证主线，虽非数据中心但方法迁移价值高。

## 算法/控制流程候选

### Page 1

Title Site demonstration and performance evaluation of MPC for a large chiller plant with TES for renewable energy integration and grid decarbonization
### Page 2

Site demonstration and performance evaluation of MPC for a large chiller plant with TES for renewable energy integration and grid decarbonization Donghun Kim a ,∗, Zhe Wang a,b , James Brugger c , David Blum a , Michael Wetter a , Tianzhen Hong a , Mary Ann Piette a a Building Technology & Urban Systems Division, Lawrence Berkeley National Laboratory, Berkeley, CA, USA b The Hong Kong University of Science and Technology, Hong Kong c University of California, Merced, CA, USA
### Page 2

Keywords: Thermal energy storage (TES) for a cooling plant is a crucial resource for load flexibility. Traditionally, simple, MPC demonstration heuristic control approaches, such as the storage priority control which charges TES during the nighttime and Building optimal control discharges during the daytime, have been widely used in practice, and shown reasonable performance in the Model predictive control past benefiting both the grid and the end-users such as buildings and district energy systems. However, the District energy system increasing penetration of renewables changes the situation, exposing the grid to a growing duck curve, which Carbon reduction Renewable energy encourages the consumption of more energy in the daytime, and volatile renewable generation which requires dynamic planning. The growing pressure of diminishing greenhouse gas emissions also increases the complexity of cooling TES plant operations as different control strategies may apply to optimize operations for energy cost or carbon emissions. This paper presents a model predictive control (MPC), site demonstration and evaluation results of optimal operation of a chiller plant, TES and behind-meter photovoltaics for a campus-level district cooling system. The MPC was formulated as a mixed-integer linear program for better numerical and control properties. Compared with baseline rule-based controls, the MPC results show reductions of the excess PV power by around 25%, of the greenhouse gas emission by 10%, and of peak electricity demand by 10%.
### Page 4

Reynders et al. [9] Residential in TABS, ASHP Minimize the Temperature Temperature setpoint is Simulation in Peak use is reduced by 89.2% Belgium with PV grid setpoint determined by predicted Modelica for the 4 ◦ C comfort band, or dependency of heat loss and peak hour, 67.3% for the 2 ◦ C comfort nZEB not-optimized band Kircher and Zhang Office HVAC with Minimize Operation of MPC policy is computed Monte Carlo 25% peak reduction and 50% [3] building in ice tank, no energy bill chiller and ice implicitly at each stage Simulation under demand charge saving New York renewable tank through online convex different weather optimization and utility price structure
### Page 4

Tarragona et al. Detached ASHP, PV, Minimize Operation of HP MPC formed as mixed Simulation with MPC saves 58% energy cost [16] house in TES operating costs integer non-linear heating load compared to RBC Spain programming from EnergyPlus
### Page 5

Fig. 3. The equipment configuration and schematic diagram of the central cooling plant at University of California, Merced: the black dashed box indicates the physical boundary of the cooling plant including EMS that manages device level controls. The primary water flow rate setpoint and plant mode marked in red are the variables to be determined by the MPC in this study. Power flow directions at the campus grid connection point (the circle) are shown in the upper right corner: The sum of the imported power from the grid and PV power generation should be the same as the sum of plant and non-plant power consumption.
### Page 9

The presented MPC has been implemented for the campus cooling TES plant for several test periods, and sample test results for a week in May 2021 are shown and discussed in this section. We start describing our approach to evaluate performance of MPC compared with the baseline control described in Section 2.3.
### Page 10

Fig. 7. Comparisons of outdoor air temperature, solar generation and CO2 emission rate between the selected baseline control period and MPC period.
### Page 11

Fig. 8. Comparisons of experimental net power consumption and state of charge between the baseline and MPC at UC-Merced (red: baseline, blue: MPC).
### Page 11

Fig. 9. Comparisons of representative (daily averaged) net power profiles between the baseline control and MPC at the UC-Merced for the weeks of evaluation in May.
### Page 12

Fig. 10. Comparisons of GHG emission rate between MPC and baseline storage-priority control at the UC-Merced.
### Page 15

Table 6 Configuration of MPC parameters. Symbol Description Value 𝑁𝑝 Prediction horizon 48 𝐽 The total number of plant modes 4 𝜔𝑑 A weight on peak power 200 𝜔𝑥 A weight on SOC violation 200 𝑂𝑇𝑗 Minimal ON and OFF time periods 2 𝑥𝑚𝑖𝑛 The minimum charge limit 55% 𝑥𝑚𝑎𝑥 The maximum charge limit 98% 𝑇ℎ0 A reference temperature for a warm water 58 ◦ F (14.4 ◦ C) 𝑇𝑐0 A reference temperature for a cold water 40 ◦ F (4.4 ◦ C) 𝑅 Overall thermal resistance between water and outdoor air 8.68 [◦ C/MW] temperature 𝐶𝑠 Thermal capacitance 391 220.52 [MJ] 𝑄𝑚𝑖𝑛,𝑗 Cooling capacity lower bound for each plant mode [4.33, 5.21, 8.99, 13.38] [MW] 𝑄𝑚𝑎𝑥,𝑗 Cooling capacity upper bound for each plant mode [4.82, 8.69, 13.08, 17.48] [MW] 𝑎𝑗 A plant power coefficient for each plant mode (see Appendix A.2) [0.126, 0.127, 0.126, 0.127] [–] 𝑐𝑗,0 A plant power coefficient for each plant mode (see Appendix A.2) [0.118, 0.191, 0.173, 0.318] [MW] 𝑐𝑗,1 A plant power coefficient for each plant mode (see Appendix A.2) [0.000, 0.006, 0.000, 0.000] [MW/◦ C]

## 公式/优化模型候选

### Page 5

```text
technology applied to district energy systems from a low level (TRL                        the plant could operate a single chiller, two serially connected chillers,
3: proof of concept) to a higher level (≥TRL 7: system prototype                           three chillers (two series chillers and one parallel chiller), and four
demonstration in an operational environment).                                              chillers (two parallel chiller groups of chillers where each group has
```
### Page 6

```text
powers, cooling tower fan powers, pump powers for the primary and
condenser water pumps, over the month of August were collected and                𝛿𝑂𝑁,𝑗 [𝑘] = 1 implies that the 𝑗th mode was OFF at least the previous
averaged. Note that the plant power is zero from 12:00 to 17:00 h. This           time step (𝑘 − 1) and is about to turn ON at 𝑘.
```
### Page 7

```text
𝑁𝑝 −1                                                                            measurements. Then, the continuous LTI was discretized in time.
             ∑(               )                                                              (𝐴, 𝐵) are the system matrices of the discrete LTI model. See
                       +
```
### Page 7

```text
+
𝑚𝑖𝑛            𝐸[𝑘] × 𝑃𝑛𝑒𝑡 [𝑘] + 𝜔𝑑 × 𝑑 + 𝜔𝑥 × 𝑣𝑥                            (1)
             𝑘=0                                                                             Appendix A.1 for more detailed descriptions.
```
### Page 7

```text
𝑚𝑖𝑛            𝐸[𝑘] × 𝑃𝑛𝑒𝑡 [𝑘] + 𝜔𝑑 × 𝑑 + 𝜔𝑥 × 𝑣𝑥                            (1)
             𝑘=0                                                                             Appendix A.1 for more detailed descriptions.
                                                                                           • Eq. (8) represents SOC constraint. This also defines the auxiliary
```
### Page 7

```text
• Eq. (8) represents SOC constraint. This also defines the auxiliary
            𝑠𝑗 [𝑘] − 𝑠𝑗 [𝑘 − 1] = 𝛿𝑂𝑁,𝑗 [𝑘] − 𝛿𝑂𝐹 𝐹 ,𝑗 [𝑘]                   (2)
                                                                                             variable of 𝑣𝑥 which is introduced to ensure a non-empty feasible
```
### Page 7

```text
variable of 𝑣𝑥 which is introduced to ensure a non-empty feasible
                    𝛿𝑂𝑁,𝑗 [𝑘] + 𝛿𝑂𝐹 𝐹 ,𝑗 [𝑘] ≤ 1                             (3)             set of the optimization problem.
                    𝑂𝑇𝑗 −1
```
### Page 7

```text
𝑂𝑇𝑗 −1
                     ∑                                                                     • Eq. (9) defines auxiliary variables, 𝜈𝑗 , to represent the total chiller
                             𝛿𝑂𝑁,𝑗 [𝑘 − 𝑙] ≤ 𝑠𝑗 [𝑘]                          (4)             load 𝑄𝐶𝐻 .
```
### Page 7

```text
∑                                                                     • Eq. (9) defines auxiliary variables, 𝜈𝑗 , to represent the total chiller
                             𝛿𝑂𝑁,𝑗 [𝑘 − 𝑙] ≤ 𝑠𝑗 [𝑘]                          (4)             load 𝑄𝐶𝐻 .
                    𝑙=0                                                                    • Eq. (10) is an algebraic expression of the following logic: IF the
```
### Page 7

```text
𝛿𝑂𝑁,𝑗 [𝑘 − 𝑙] ≤ 𝑠𝑗 [𝑘]                          (4)             load 𝑄𝐶𝐻 .
                    𝑙=0                                                                    • Eq. (10) is an algebraic expression of the following logic: IF the
                 𝑂𝑇𝑗 −1
```
### Page 8

```text
do not vary significantly: the relative 2-norm error between the optimal
trajectories for 𝜔𝑥 = 𝜔𝑑 = 200 and 𝜔𝑥 = 𝜔𝑑 = 500 was less than 0.01%                    3.5. MPC implementation and interface
for all decision variables.
```
### Page 8

```text
For choosing an appropriate time step, we considered (1) a better                       The flow diagram of implementing MPC at the campus cooling
response to unpredicted events (e.g., abrupt increase/decrease of cool-                 TES plant is shown in Fig. 5. At each sampling time (𝛥𝑡 = 1 h),
                                                                                        the MPC sever receives the read datapoints (listed in the Table 2),
```
### Page 8

```text
ing load) and (2) a time scale separation between the MPC loop (outer
                                                                                        and two-day (𝑁𝑝 = 48) ahead forecasts of ambient temperature us-
control loop that determines the plant mode and flow rate setpoint)
```
### Page 8

```text
forecast errors with several different stochastic difference equations and              as follows.
investigated the effect of the size on the MPC performance for TES                      𝑉𝑝,𝑆𝑃 = 𝑄𝐶𝐻 ∕(𝜌𝑤𝑎𝑡𝑒𝑟 × 𝐶𝑝,𝑤𝑎𝑡𝑒𝑟 × (𝑇𝐸𝐶𝐻𝑊 − 𝑇𝐶𝐻𝑊 𝑆,𝑆𝑃 ))                    (19)
systems. The results showed that the increasing prediction horizon low-
```
### Page 10

```text
variables, and (𝐽 + 2)𝑁𝑝 + 1, (4𝐽 + 3)𝑁𝑝 and 2𝑁𝑝 + 2 numbers of
equality, inequality, and bounding constraints respectively. With 𝑁𝑝 =
                                                                                             of the state of charge with the MPC for the same period. The MPC
```
### Page 10

```text
of the state of charge with the MPC for the same period. The MPC
48 and 𝐽 = 4, the optimization problem has around 1300 constraints
                                                                                             actually increased the state of the charge which implies that the chillers
```
### Page 12

```text
• It was not possible to rely on manufacturer specifications, and                         serious supply water temperature fluctuations. This could have
      performance was subject to change after maintenance and failures                        been avoided if it was tested with a detailed simulation model.
```
### Page 14

```text
installing new energy storage but only requires changing the operation.               𝑑                                   𝑇 − (𝑇𝑐 𝑧 + 𝑇ℎ (1 − 𝑧))
                                                                                 𝐶𝑤     (𝑇 𝑧 + 𝑇ℎ (1 − 𝑧)) = −𝑄𝑑𝑖𝑠𝑐ℎ𝑎𝑟𝑔𝑒 + 𝑂𝐴                     ,       (20)
We presented an MPC and its real site performance for a campus-                       𝑑𝑡 𝑐                                         𝑅
```
### Page 14

```text
level cooling TES plant that coordinates operation of multiple chillers,         where 𝐶𝑤 is the thermal capacitance of the chilled water tank [J/◦ C]
chilled water tank and behind-meter PVs. It aims at self-consuming               (ideally, 𝐶𝑤 = 𝜌𝑤 𝑐𝑝,𝑤 𝑉0 ), 𝑧 is the relative height of the thermocline in
on-site generation from a 4 MW solar farm, lowering carbon emission              the tank, and 𝑅 is the thermal resistance between the water and outdoor
```
### Page 14

```text
were conservative, since only a partial usage of the chilled water tank
was allowed during the MPC implementation period. The capability of              𝑄𝐵𝐿 = 𝑄𝐶𝐻 + 𝑄𝑑𝑖𝑠𝑐ℎ𝑎𝑟𝑔𝑖𝑛𝑔                                                 (21)
achieving utility peak demand in addition to lowering GHG emission is
```
### Page 14

```text
CRediT authorship contribution statement                                                 𝑢0ℎ − 𝑢
                                                                                 𝑥 ∶=               ,                                                     (22)
                                                                                        𝑢0ℎ − 𝑢0𝑐
```
### Page 14

```text
Support site demonstration. James Brugger: Validation, Site exper-               (𝑇𝑐0 ), respectively. Since the water in the tank are sub-cooled liquid, 𝑢
iment, Reviewing and editing. David Blum: Reviewing and editing.                 can be expressed as 𝑢 = 𝑐𝑝,𝑤 (𝑧𝑇𝑐 ) + 𝑐𝑝,𝑤 (1 − 𝑧)𝑇ℎ . Then, Eq. (22) becomes
Michael Wetter: Reviewing and editing. Tianzhen Hong: Funding
```
### Page 14

```text
𝑇ℎ0 − (𝑇𝑐 𝑧 + 𝑇ℎ (1 − 𝑧))
ing, Finding demonstration site. Mary Ann Piette: Funding acquisition,           𝑥=                                .                                      (23)
Supervision, Reviewing and editing, Finding demonstration site.                                𝑇ℎ0 − 𝑇𝑐0
```
### Page 14

```text
𝑑𝑥    𝑇 0 − 𝑇𝑐0                    𝑇𝑂𝐴 − 𝑇ℎ0
                                                                                 𝐶𝑠      = − ℎ        𝑥 + (𝑄𝐶𝐻 − 𝑄𝐵𝐿 ) −           ,                      (24)
                                                                                      𝑑𝑡        𝑅                           𝑅
```
### Page 14

```text
The authors declare that they have no known competing finan-
cial interests or personal relationships that could have appeared to                  𝐶𝑠 = 𝐶𝑤 (𝑇ℎ0 − 𝑇𝑐0 ).                                               (25)
influence the work reported in this paper.
```
### Page 15

```text
⎪𝑎1 𝑄𝐶𝐻 + 𝑏1 (𝑇𝑊 𝐵 ) for the plant mode 1                                                [11] Hajiah A, Krarti M. Optimal controls of building storage systems using both ice
𝑃𝑝𝑙𝑎𝑛𝑡 = ⎨                                                                          (27)               storage and thermal mass–Part II: Parametric analysis. Energy Convers Manage
         ⎪⋮                                                                                            2012;64:509–15.
```
### Page 15

```text
connected low energy buildings with thermal energy storages. Energy Build
model structure for 𝑏𝑗 but the linear affine form, i.e., 𝑏𝑗 = 𝑐𝑗,0 +𝑐𝑗,1 𝑇𝑊 𝐵 ,
                                                                                                       2015;86:415–26.
```

## 符号表/变量定义候选

### Page 3

```text
Acronyms
    ABC                      Active chilled beams
    ASHP                     Air source heat pump
    CAISO                    California independent system operator
    CHP                      Combined heat and power
    EMS                      Energy management system
    GDP                      Generalized disjunctive programming
    GHG                      Greenhouse gas
    GSHP                     Ground source heat pump
    HVAC                     Heating, ventilating, and air conditioning
    ISO                      Independent system operator
    LEED                     Leadership in energy and environmental
                             design
                                                                                            Fig. 2. Wind and solar curtailment totals by month in California ISO. The image is
    MILP                     Mixed integer linear programming
                                                                                            from CASIO (http://www.caiso.com/).
    MOER                     Marginal operating emission rate
    MPC                      Model predictive control
    NOAA                     National oceanic and atmospheric adminis-                      (MPC), for optimal operation of building and district energy systems
                             tration                                                        with the behind-meter renewable generation or/and active energy
    nZEB                     Net zero energy building                                       storage (TES or battery) for renewable energy integration. Reviewed
    PV                       Photovoltaic                                                   papers are summarized in Table 1, where ASHP stands for air source
    RTU                      Rooftop units                                                  heat pump, GSHP for ground source heat pump, PV for Photovoltaic,
    SOAP                     Simple object access protocol                                  TABS for thermally activated building structures, nZEB for net zero
    SOC                      State of charge                                                energy building, RTU for Roof Top Unit, ACB for Active Chilled Beams,
    TABS                     Thermally activated building structures                        CHP for combined heat and power, TES for thermal energy storage.
    TRL                      Technology readiness level                                     Advanced controls, especially MPC, can help to manage energy storage
                                                                                            and renewable generation. Kircher and Zhang [3] applied MPC to co-
    TES                      Thermal energy storage
                                                                                            optimize the operation of a chiller plant and ice storage in an office
                                                                                            building in New York, reducing the peak demand by 25%. Oldewurtel
                                                                                            et al. [4] developed a Sequential Linear Programming based MPC for
                                                                                            Residential and office buildings in Zurich, which reduced the peak de-
                                                                                            mand by 3.5% (without battery) and by 17.5% (with battery). Ceusters
                                                                                            et al. [5] developed a Mixed-integer Linear Programming based MPC
                                                                                            to optimize the operation of a campus-level multi-energy system,
                                                                                            including CHP, renewable generation (wind, PV), and battery. Zhang
                                                                                            et al. [6] proposed to use Mixed-integer Linear Programming based
                                                                                            MPC to operate a residential micro-grid, saving 40% costs compared
                                                                                            with conventional rule-based strategy. In addition to MPC, LeBreux
                                                                                            et al. [7] presented a fuzzy logic and feedforward controller to resolve
                                                                                            the supply and demand mismatch and to minimize the grid dependency
                                                                                            using thermal storage for a nZEB. Li et al. [8] proposed reinforcement
                                                                                            learning and MPC to mitigate the intermittency of behind-meter renew-
                                                                                            able generation by optimizing the charging/discharging of a battery
                                                                                            based on wind power generation prediction. It was found that MPC can
                                                                                            help to smooth wind power scheduling and lower wind curtailment. To
Fig. 1. The official duck chart first published by CAISO in 2013 (What the Duck Curve       cover the wind intermittency, MPC demands 25% less battery capacity
Tells us about Managing a Green Grid).                                                      compared with a heuristic control algorithm.
                                                                                                Despite many studies of optimal operation of TES with behind-
                                                                                            meter renewable and energy storage, a majority of them are using
power supply from, e.g., the nuclear power plants. It is essential to                       simulations as shown in the table, and therefore real performance of
curtail renewable energy to maintain the base load generators. Fig. 2                       MPC including self-consumption ratio are not clear. Although there
shows the monthly wind and solar curtailment for the CAISO from                             are some papers with experimental assessment of MPCs coordinat-
2019 to 2021 (different colors represent different years). A significant                    ing TES and HVAC systems, they are limited to small-scale systems,
portion of renewable energy generation is currently wasted, and the                         e.g., laboratory or small-sized building (e.g., residential) levels. For
renewable energy is expected to be curtailed more as more renewable                         large-scale systems, there are very few papers that demonstrate an MPC
resources are being installed in CAISO territory. The other issue occurs                    for renewable energy integration and present real site performance. In
on the neck of a duck: Because of the rapid drop of solar energy, the                       addition, there is a lack of knowledge about applying MPC to mitigate
net load increases quickly. To meet the high ramping rate of the load,                      CO2 emissions [17].
dispatchable generators with short response time (order of minutes)                             This paper fills the gaps by implementing an MPC for a campus-
such as gas turbine generators have to run and emit significant CO2                         level cooling TES plant and presenting on-site performance compared
(an order of thousands of metric ton CO2 equivalent per hour) during                        with carefully selected, historical rule-based operation data for the
the neck period.                                                                            plant. The MPC aims at promoting the self-consumption of the on-
   A large number of papers are available in the literature that present                    site renewable and minimizing CO2 in the grid. Because utility cost
advanced control approaches, including model predictive control                             reduction is one of the key motivations for the facility, the MPC
                                                                                        2
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
