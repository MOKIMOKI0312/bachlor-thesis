# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2025_Xiang_Optimization_of_a_free_cooling_system_integrated_with_cold_thermal_energ.pdf`
- 标题：Optimization of a free cooling system integrated with cold thermal energy storage in data center based on model predictive control
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

Optimization of a free cooling system integrated with cold thermal energy storage in data center based on model predictive control Ke Xiang a,b , Zhiyong Tian a,b,* , Ling Ma c , Xinyu Chen d , Yongqiang Luo a,b , Yafeng Gao e, Jianhua Fan f, Qian Wang g a School of Environmental Science and Engineering, Huazhong University of Science and Technology, Wuhan, 430074, China b Hubei Key Laboratory of Multi-media Pollution Cooperative Control in Yangtze Basin, School of Environmental Science and Engineering, Huazhong University of Science and Technology, 1037 Luoyu Road, Wuhan, Hubei, 430074, China c School of Civil and Hydraulic Engineering, Huazhong University of Science and Technology, Wuhan, 430074, China d School of Electrical and Electronic Engineering, Huazhong University of Science and Technology, Wuhan, 430074, China e Joint International Research Laboratory of Green Building and Built Environment, Ministry of Education, Chongqing University, Chongqing, 400044, China f Department of Civil and Mechanical Engineering, Technical University of Denmark, Brovej 118, 2800, Kgs. Lyngby, Denmark g School of Architecture and the Built Environment, KTH Royal Institute of Technology, Uponor AB, Hackstavägen 1, 72132, Västerås, Sweden
### Page 1

Handling Editor: Dr X Zhao With the rapid development of information technology, energy consumption in data centers has become increasingly prominent. As a core component, cooling systems account for substantial energy use while offering Keywords: significant energy-saving potential, making them crucial for energy efficiency optimization. To address energy Data center conservation in cooling systems, a free cooling system integrated with cold thermal energy storage is investigated Water storage in this study. Using typical meteorological parameters of Wuhan as a case study, a genetic algorithm (GA)-based Free cooling model predictive control (MPC) strategy is employed to optimize system performance, and its adaptability across TRNSYS System optimization different climatic zones in China is evaluated. The results demonstrate that optimizing with power usage Energy saving effectiveness (PUE) minimization as the objective function reduces the PUE value by 0.018 compared to the baseline system. When applied nationwide, lower PUE values are observed in regions with more abundant free cooling resources. After MPC optimization, the most significant improvements are exhibited in the mild climate zone, where a maximum PUE reduction of 0.0185 is achieved compared to pre-optimized systems.
### Page 1

PUE Power usage effectiveness Taw ◦ C Wet-bulb temperature MPC Model predictive control Twb_low ◦ C Lower switchover temperature GA Genetic algorithm Twb_up ◦ C Upper switchover temperature HVAC Heating, ventilation, and air conditioning Tst ◦ C Inlet water temperature of the cold water storage tank PLR Part load ratio Tst_set ◦ C Set cold storage temperature COP Coefficient of performance Treo ◦ C Temperature for cold release CRAH Computer room air handler Treo_set ◦ C Set temperature for cold release MILP Mixed-integer linear programming WIT kJ Energy consumption of IT equipment ANN Artificial neural network WC kJ Energy consumption of cooling system TOU Time-of-use WE kJ Energy consumption of electrical systems CNY Chinese yuan PUEA – Actual PUE under different cases PUEB – Baseline PUE WA kJ Actual energy consumption under different cases WB kJ Baseline energy consumption CA CNY Actual electricity cost under different cases (continued on next page)
### Page 5

Cold storage mode When the inlet water temperature of the cold water storage tank (Tst) is lower than the set cold storage temperature (Tst_set), the backup unit utilizes free cooling sources for cold storage.
### Page 5

Cold release mode When the operating conditions for free cooling mode in the normal cooling mode cannot be met, the cold water storage tank prioritizes providing cooling to the data center. When the temperature for cold release exceeds the set temperature for cold release (Treo_set), the cold water storage tank stops supplying cooling, and the system continues to operate in partial free cooling or mechanical cooling mode.
### Page 5

Fig. 2. Simulation platform for the free cooling system integrated with cold thermal energy storage.
### Page 6

Table 3 Where Ptotal(t) is the total power (kW) of the cooling system at time t, Statistics of wet-bulb temperature distribution in typical Chinese cities. which includes the energy consumption of IT equipment, cooling sys­ Wet-bulb temperature Harbin Beijing Wuhan Kunming Guangzhou tems, and other auxiliary equipment. (◦ C) When optimizing the cooling process of a data center, it is crucial to ≤0 3918 2444 392 38 0 ensure that the equipment in the server room operates under favorable 0–10 1784 2190 2693 3222 966 conditions and that the cooling system functions in a stable state. 10–20 2455 2507 2854 5464 3028 20–30 604 1612 2801 37 4759 Therefore, the following constraints have been incorporated into the ≥30 0 7 21 0 8 optimization process.
### Page 7

Fig. 3. Model predictive control joint simulation model operation strategy diagram.
### Page 9

Fig. 5. Comparison of energy consumption, energy-saving ratio and ambient temperature across quarters before and after MPC optimization.
### Page 9

Fig. 7. The proportion of cooling provided by different cold sources in the cooling system across various quarters before and after MPC optimization.
### Page 10

Fig. 9. Comparison of total energy consumption, electricity cost, and PUE value before and after MPC optimization.
### Page 12

Fig. 14. Cooling source utilization distribution in representative cities before and after MPC optimization.

## 公式/优化模型候选

### Page 4

```text
cooling                           WIT + WC + WE
                                                           When the wet-            PUE =                                                                    (4)
                                                                                                  WIT
```
### Page 4

```text
Mechanical                        PUEB − PUEA
                                                                                    RPUE =               × 100%                                              (5)
                                                           cooling                              PUEB
```
### Page 4

```text
WB − WA
                                                           plate heat               RE =           × 100%                                                    (6)
                                                           exchanger and                     WB
```
### Page 4

```text
CB − CA
                                                                                    RC =           × 100%                                                    (7)
                                                                                              CB
```
### Page 4

```text
convergence threshold of the iteration error for each step is set to 0.001.         3.3.1. MPC strategy
The simulated temperature set-point temperatures are Twb_low = 9 ◦ C,                  Model predictive control is a modern control theory initially pro­
Twb_up = 13 ◦ C, and Treo_set = 14 ◦ C, and the design supply and return air        posed by Richalet et al. [38] in 1978 to address issues such as multi­
```
### Page 4

```text
The simulated temperature set-point temperatures are Twb_low = 9 ◦ C,                  Model predictive control is a modern control theory initially pro­
Twb_up = 13 ◦ C, and Treo_set = 14 ◦ C, and the design supply and return air        posed by Richalet et al. [38] in 1978 to address issues such as multi­
                                                                                    variable systems and frequent disturbances in the industrial sector. Due
```
### Page 6

```text
When optimizing the cooling process of a data center, it is crucial to
  ≤0                                  3918      2444          392        38              0                 ensure that the equipment in the server room operates under favorable
  0–10                                1784      2190         2693      3222            966                 conditions and that the cooling system functions in a stable state.
```
### Page 6

```text
Therefore, the following constraints have been incorporated into the
  ≥30                                    0         7           21         0              8                 optimization process.
```
### Page 6

```text
1) Constraint on data center return air temperature:
Table 4                                                                                                    Tr ≤ Tr,lim                                                                (2)
The fundamental parameters of system configuration.
```
### Page 6

```text
upper limit for the return air temperature. The normal operation of
  Water cooled chiller                         2+1            Q = 1870 kW;Pchiller = 267 kW
  Chilled water pump                           2+1            mchw = 325 m3/h;Pchwp = 55 kW                equipment within the data center requires strict control of the ambient
```
### Page 6

```text
Water cooled chiller                         2+1            Q = 1870 kW;Pchiller = 267 kW
  Chilled water pump                           2+1            mchw = 325 m3/h;Pchwp = 55 kW                equipment within the data center requires strict control of the ambient
  Cooling water pump                           2+1            mcw = 350 m3/h;Pcwp = 65 kW                  temperature. The return air temperature constraint ensures that the
```
### Page 6

```text
Chilled water pump                           2+1            mchw = 325 m3/h;Pchwp = 55 kW                equipment within the data center requires strict control of the ambient
  Cooling water pump                           2+1            mcw = 350 m3/h;Pcwp = 65 kW                  temperature. The return air temperature constraint ensures that the
  Water-water heat exchanger                   2+1            UA = 2000 kW/K                               indoor temperature remains within the range recommended by equip­
```
### Page 6

```text
Cooling water pump                           2+1            mcw = 350 m3/h;Pcwp = 65 kW                  temperature. The return air temperature constraint ensures that the
  Water-water heat exchanger                   2+1            UA = 2000 kW/K                               indoor temperature remains within the range recommended by equip­
  Cooling tower                                2+1            mct,a = 380000 m3/h;Pct = 18 kW              ment manufacturers, thereby preventing excessively high temperatures
```
### Page 6

```text
Water-water heat exchanger                   2+1            UA = 2000 kW/K                               indoor temperature remains within the range recommended by equip­
  Cooling tower                                2+1            mct,a = 380000 m3/h;Pct = 18 kW              ment manufacturers, thereby preventing excessively high temperatures
  Cold storage pump                            1              mre = 400 m3/h;Pre = 80 kW
```
### Page 8

```text
Pc is set to 0.6, the mutation probability Pm is set to 0.001, and the           significant energy-saving potential of this control strategy under low-
maximum number of iterations is defined as T = 30.                               temperature conditions. In the second quarter, as temperatures rose,
                                                                                 the energy-saving ratio was 2.4 %, and the PUE value decreased by
```
### Page 14

```text
fully considering practical engineering challenges like cooling tower
performance degradation in low-temperature environments. In addi­                      The crossover probability (Pc = 0.6) was selected as the intermediate
tion, regarding the MPC strategy based on the genetic algorithm, efforts           value between the typical ranges recommended by the genetic algo­
```

## 符号表/变量定义候选

### Page 1

```text
Abbreviations                                                                                      Nomenclature
    PUE                                        Power usage effectiveness                             Taw              ◦
                                                                                                                        C            Wet-bulb temperature
    MPC                                        Model predictive control                              Twb_low          ◦
                                                                                                                        C            Lower switchover temperature
    GA                                         Genetic algorithm                                     Twb_up           ◦
                                                                                                                        C            Upper switchover temperature
    HVAC                                       Heating, ventilation, and air conditioning            Tst              ◦
                                                                                                                        C            Inlet water temperature of the cold water storage tank
    PLR                                        Part load ratio                                       Tst_set          ◦
                                                                                                                        C            Set cold storage temperature
    COP                                        Coefficient of performance                            Treo             ◦
                                                                                                                        C            Temperature for cold release
    CRAH                                       Computer room air handler                             Treo_set         ◦
                                                                                                                        C            Set temperature for cold release
    MILP                                       Mixed-integer linear programming                      WIT              kJ             Energy consumption of IT equipment
    ANN                                        Artificial neural network                             WC               kJ             Energy consumption of cooling system
    TOU                                        Time-of-use                                           WE               kJ             Energy consumption of electrical systems
    CNY                                        Chinese yuan                                          PUEA             –              Actual PUE under different cases
                                                                                                     PUEB             –              Baseline PUE
                                                                                                     WA               kJ             Actual energy consumption under different cases
                                                                                                     WB               kJ             Baseline energy consumption
                                                                                                     CA               CNY            Actual electricity cost under different cases
                                                                                                                                                                        (continued on next page)
    * Corresponding author. School of Environmental Science and Engineering, Huazhong University of Science and Technology, Wuhan, 430074, China.
      E-mail addresses: tianzy0913@163.com, zhiyongtian@hust.edu.cn (Z. Tian).
https://doi.org/10.1016/j.energy.2025.138389
Received 11 April 2025; Received in revised form 9 August 2025; Accepted 6 September 2025
Available online 8 September 2025
0360-5442/© 2025 Elsevier Ltd. All rights are reserved, including those for text and data mining, AI training, and similar technologies.
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
