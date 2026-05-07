# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2024_Zhao_A_model_predictive_control_for_a_multi_chiller_system_in_data_center_con.pdf`
- 标题：A model predictive control for a multi-chiller system in data center considering whole system energy conservation
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

p2-p4 method route; p4-p7 LSTM prediction; p14-p17 control effect; keywords: MPC, PSO, constraint, TRNSYS.

支撑数据中心多冷机 MPC、温度约束和系统节能；不直接覆盖 PV/TOU/TES。

## 算法/控制流程候选

### Page 1

A model predictive control for a multi-chiller system in data center considering whole system energy conservation Jing Zhao * , Ziyi Chen , Haonan Li , Dehan Liu Tianjin Key Laboratory of Built Environment and Energy Application, School of Environmental Science and Engineering, Tianjin University, Tianjin 300072, China
### Page 4

2.2.1. Selection of input parameters Table 1 The selection of input parameters for prediction models will directly Constraint ranges for each parameter to be optimized. affect the complexity of calculations and the accuracy of predictions, Vscrew* (m3/ Vmaglev* (m3/ Tsupply* (◦ C) Treturn* (◦ C) and should be chosen according to the data relationship of the prediction h) h) target. In this study, grey relation analysis (GRA) [33] was used to Upper bound 150 45 11.5 15.5 evaluate the degree of influence between different factors in order to Lower 120 30 10.0 14.5 select and get the key factors affecting the target parameters. Compared bound with the classical correlation analysis methods such as correlation
### Page 9

where Ppump is the pump power, kW; Me is the chilled water flow rate, where a1~a10 are the parameters to be recognized; Tei is the chilled m3/h. water return temperature, ◦ C; Tci is the cooling water return tempera- Fig. 9 shows the comparison between the fitted and measured COP ture, ◦ C; Ta is the ambient temperature, ◦ C; Qcooling is the cooling ca- values for the four air-cooled chillers. As shown in the figure, the error pacity, kW. rates between the fitted and measured values of the four models are Although the four chillers in this study involve two models, their basically within 5%. By employing Eq. (7) and Eq. (11) for error cal- actual performance varies due to the wear and tear in the actual oper- culations in the mathematical models, the results are shown in Table 7. ation. In order to ensure the accuracy of the MPC, this study established The accuracy and validity of the established unit performance-energy mathematical models based on the actual operation data of four chillers consumption mathematical models were successfully demonstrated. respectively. A multiple linear regression method based on the least squares was used for parameter identification. A total of 900 sets of 3.2.2. Verification of simulation platform operational data were acquired for each chiller, of which 700 sets were In this study, TRNSYS 16 was used to build the simulation model of used for model training and 200 sets for model validation. The regressed the data center cooling system. The constructed TRNSYS is shown in Fig. 10.
### Page 12

water flow rate are selected as input parameters and simulation calcu- the MAPE for each equipment is within 2%, and these results demon- lations are carried out in 72 h to obtain the indoor temperature change strate the accuracy of the equipment module selection and parameter curve of the IDC room and the total system power consumption value. input in the developed TRNSYS model. The results are shown in Fig. 17. The average absolute error of the temperature of the computer room 3.2.3. Comparative conditions is 0.05◦ C. Table 8 demonstrates the MAPE values of the day-by-day In this study, PID control, fuzzy control [45], and MPC control power consumption of each equipment. As can be seen from the table, strategies were selected for comparative analysis.
### Page 15

evaluated. Over a 3-day period, the total system energy consumption indicating the effectiveness of the “prediction” component in MPC. was 36,096.9 kW⋅h for the PID control, 34,443.5 kW⋅h for the fuzzy Further combining with temperature data analysis, the outdoor control, and 31,833.3 kW⋅h for the MPC control. Among them, the MPC temperature gradually begins to rise at 7 a.m., followed by an increase in strategy is the most energy-efficient, saving 11.81% compared to the PID the server room temperature under PID and fuzzy control at 8 a.m., in control and 7.58% compared to the fuzzy control. line with the outdoor temperature increase. Similarly, at 6p.m., as the Fig. 21 shows the daily power consumption comparison of the three outdoor temperature starts to decrease, the server room temperature control strategies. From the graph, it is evident that the daily power under the two control methods also starts to decrease. In the process of consumption over the three days shows a gradual decrease trend. Within each day, the MPC strategy consistently exhibits the lowest energy consumption. Compared to PID control, daily energy savings are around Table 11 12%, and compared to fuzzy control, they are around 8%. These savings Comparison of evaluation indicators of prediction models. align with the overall 3-day energy efficiency, indicating that MPC Cooling load prediction Server room temperature prediction strategy also possesses excellent and stable capability to reduce system model model
### Page 19

Table 14 Table 15 Comparison of cooling capacity and ICOP of the chillers under different control Daily PUE values under different control strategies. strategies. PID control Fuzzy control MPC control Cooling (kW⋅h) ICOP Day 1 1.63 1.61 1.58 PID control 1127.60 2.44 Day 2 1.62 1.60 1.56 Fuzzy control 1121.19 2.50 Day 3 1.60 1.58 1.54 MPC control 1133.90 2.81 Full year (extrapolated) 1.47 1.45 1.42
### Page 19

equal to the predicted value of the cooling load to achieve energy-saving water flow rate and temperature configurations of multiple chillers to operation of the cooling system. Based on the prediction models and the meet the control objectives, reducing the cooling system operating en- performance-energy consumption mathematical models of the cooling ergy consumption, and then reducing the PUE of the data center. system, the PSO algorithm is used to solve the combination of chilled This study proposes an intelligent control strategy for the joint

## 公式/优化模型候选

### Page 3

```text
(2) Based on the temperature prediction model, the server room
temperature Tin(t+1)* at the moment t+1 is predicted by inputting                  Pchiller (t + 1)* =Pscrew,1 (t + 1)* + Pscrew,2 (t + 1)* + Pmaglev,1 (t + 1)*
                                                                                                                                                                     (2)
```
### Page 3

```text
*                *
⎨ Lcooling (t + 1) = 4.19/3.6⋅Vchw (t + 1) ⋅ΔTchw (t + 1)                          {                                          [                                  ]2
                  *                   *
```
### Page 3

```text
*                   *
     Vchw (t + 1) = 2⋅[Vscrew (t + 1) + Vmaglev (t + 1) ] *
                                                                       (1)           J(t) = α⋅[Tin (t +1)* − Tset (t +1)]2 +β⋅ Pchiller (t +1)* +3⋅Ppump (t +1)*
```
### Page 3

```text
Vchw (t + 1) = 2⋅[Vscrew (t + 1) + Vmaglev (t + 1) ] *
                                                                       (1)           J(t) = α⋅[Tin (t +1)* − Tset (t +1)]2 +β⋅ Pchiller (t +1)* +3⋅Ppump (t +1)*
⎩
```
### Page 3

```text
⎩
      ΔTchw (t + 1)* = Treturn (t + 1)* − Tsupply (t + 1)*                                                              α +β = 1
                                                                                                                                                                    (3)
```
### Page 3

```text
water flow rate, the chilled water flow rate borne by a single screw unit          diction value, and Tset is the temperature setting value, ◦ C; Pchiller* and
and a single magnetic levitation unit, respectively, m3/h; ΔTchw*, Tsupply*        Ppump* denote the total power consumption of the chillers and the power
and Treturn* are the temperature difference between the supply and re-             consumption of a single pump, respectively, kW⋅h; α and β are dimen-
```
### Page 3

```text
and a single magnetic levitation unit, respectively, m3/h; ΔTchw*, Tsupply*        Ppump* denote the total power consumption of the chillers and the power
and Treturn* are the temperature difference between the supply and re-             consumption of a single pump, respectively, kW⋅h; α and β are dimen-
turn water, the supply water temperature and the return water tem-                 sionless weight coefficients, and the temperature control of the server
```
### Page 3

```text
cooled chillers, the chilled water flow rate Vscrew(t+1)* and Vmaglev(t+1)         should be close in the cost function. Considering that the absolute value
*, the return water temperature Treturn(t+1)*, and the predicted cooling           of the temperature control term in the cost function is around 3.6×10-
load Lcooling(t+1) at the time of t+1 mentioned above are brought in               1 ◦ 2
```
### Page 4

```text
term is around 1.95×105 (kW⋅h)2, α=1–1.8×10-6 and β=1.8×10-6 are                        while minimizing energy consumption as much as possible. The
set to ensure that the two controlled targets are in the same order of                  controlled parameters include chilled water supply temperature Tsupply,
```
### Page 5

```text
moment of t+1 can be obtained through the meteorological forecast,                 the collected data, which are not on the same scale, for example, the
and thus is also analyzed as the input parameter to be selected.                   temperature of the server room is in the order of 2 × 101 ◦ C, while the
```
### Page 6

```text
prediction models are shown in Table 2.
cooling load is concentrated in the order of 1 × 103 kW, so it is necessary
to normalize and dimensionless all data. This is to facilitate the neural
```
### Page 6

```text
Xi − Xmin                                                                         This study uses the relative temperature fluctuation rate to measure
Xi =                                                                        (4)
       Xmax − Xmin                                                                    the overall fluctuation amplitude of temperature in the selected time
```
### Page 6

```text
in this paper, with 80% of the data used for model training and 20% for                                Tmax − Tmin
model validation.                                                                     RTemperature =               × 100%                                        (5)
                                                                                                          Tave
```
### Page 7

```text
Table 2
                                                                                                   1 ∑n (          )2
Parameters of LSTM prediction models.                                                         MSE = ⋅ i=1 yi − yʹi                                                     (10)
```
### Page 7

```text
1 ∑n (          )2
Parameters of LSTM prediction models.                                                         MSE = ⋅ i=1 yi − yʹi                                                     (10)
                                                                                                   n
```
### Page 7

```text
⃒        ⃒
                                                                                                     1 ∑n ⃒yi − yʹi ⃒
                                                                                              MAPE = ⋅ i=1            × 100%                                           (11)
```
### Page 7

```text
1 ∑n ⃒yi − yʹi ⃒
                                                                                              MAPE = ⋅ i=1            × 100%                                           (11)
  Feature vector                       5                  7                                          n        yi
```
### Page 7

```text
follows:                                                                                      and maintenance duty center; the second floor is the service monitoring
ICOP = (A × COPscrew ) + (B × COPmaglev )                                           (6)       room and office area; the third to fifth floors are two IDC rooms with the
                                                                                              same specifications and three computer room air conditioning (CRAC)
```
### Page 7

```text
the average COP of screw chiller; COPmaglev is the average COP of                             is a diesel-powered generation room. The ambient temperature of the
magnetic levitation chiller.                                                                  server room area is set at 22±2◦ C, and the relative humidity is allowed
   The accuracy of the prediction model and the equipment model was                           to range from 30% to 60%. The server room is in the form of room-level
```
### Page 7

```text
are as follows [42]:                                                                              The cooling system of this data center adopts air-cooled chillers +
            ∑n                                                                                CRAC end system. The cooling system mainly includes two sets of high-
                  (yi − yʹi )                                                                 power screw air-cooled chiller units, two sets of low-power magnetic
```
### Page 7

```text
(yi − yʹi )                                                                 power screw air-cooled chiller units, two sets of low-power magnetic
R2 = 1 − ∑n i=1               × 100%                                  (7)
            i=1 (yi − ymean )                                                                 levitation air-cooled chiller units, four sets of circulating water pumps,
```
### Page 8

```text
18.5 kW
                                       Rated speed:                                                 COP =a1 + a2 ⋅Qcooling + a3 ⋅Tei + a4 ⋅Tci + a5 ⋅Q2cooling + a6 ⋅Tei2 + a7 ⋅Tci2
                                       1480 r/min
```
### Page 8

```text
conditioning          Number of EC                        operation
                                       fans: 2                                                      COP =a1 + a2 ⋅Qcooling + a3 ⋅Tei + a4 ⋅Ta + a5 ⋅Q2cooling + a6 ⋅Tei2 + a7 ⋅Ta2
                                       EC fan air                                                                                                                                            (13)
```
### Page 9

```text
a9          − 0.0004       − 0.0001         − 0.0008        − 0.0006
  a10         − 0.0085       − 0.0093           0.0184        − 0.0056               Ppump = 0.0238⋅Me 2 − 5.270⋅Me + 306.7                                  (14)
```
### Page 13

```text
analyzed values of GRA between the cooling load and each factor to be             fect, both prediction models show good fitting performance on the
screened at the moment of t+1. With GRA≥0.8 as the correlation                    training and test sets, with their goodness-of-fit R2 exceeding 90%; the
judgment criterion, the time series of five factors, namely, the cooling          MRE and RMSE of the test set meet the ASHRAE standard [46]. There-
```

## 符号表/变量定义候选

未发现明确 Nomenclature/Acronyms 段。

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
