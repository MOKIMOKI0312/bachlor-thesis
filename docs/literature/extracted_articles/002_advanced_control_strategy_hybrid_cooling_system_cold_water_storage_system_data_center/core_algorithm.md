# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2024_Zhu_An_advanced_control_strategy_of_hybrid_cooling_system_with_cold_water_st.pdf`
- 标题：An advanced control strategy of hybrid cooling system with cold water storage system in data center
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

p3 MPC strategy; p6 objective function/MILP; p7 constraint conditions; p10-p14 case and results.

核心直连数据中心冷水蓄冷、MPC、MILP 和冷却模式调度；Zhu 2024 在本地有多份副本，已按 DOI 合并。

## 算法/控制流程候选

### Page 1

An advanced control strategy of hybrid cooling system with cold water storage system in data center Yiqun Zhu a, Quan Zhang a, *, Liping Zeng b, Jiaqiang Wang c, Sikai Zou d a College of Civil Engineering, Hunan University, Changsha, 410082, China b School of Architectural Engineering, Hunan Institute of Engineering, Xiangtan, 411104, China c School of Energy Science and Engineering, Central South University, Changsha, 410083, China d School of Civil Engineering and Architecture, East China JiaoTong University, Nanchang, 330013, China
### Page 1

Handling Editor: X Zhao The inefficient operation of cooling equipment is a significant impact factor to the high energy consumption of cooling system in data center. This study proposes an advanced model predictive control (MPC) strategy for a Keywords: hybrid cooling with water storage system to improve energy efficiency and reduce the accumulation of cold Data center storage losses. Mixed integer linear programming (MILP) in MPC strategy is used to optimize the operating Free cooling parameters under free cooling, hybrid cooling, and mechanical cooling modes, further solving the problem of Cold storage tank volume precise optimization for different modes. Taking Guangzhou city as an example, the equipment scheduling and Model predictive control (MPC) Mixed integer linear programming (MILP) the appropriate volume of cold water storage tank for MPC strategy are analyzed. The results indicate that, the emergency cold water storage tank 500 m3 only supports the efficient operation of cooling system under the maximum 60 % IT load rate, meanwhile, the optimal tank volume 1400 m3 could meet the 60–100 % IT load rate. Compared to Baseline strategy, the biggest reduction of annual energy consumption using MPC strategy would be attained by 12.19 % under free cooling mode, by 4.04 % under hybrid cooling mode, and by 22.15 % under mechanical cooling conditions at the 55 % IT load rate. Therefore, the MPC strategy proposed in this paper has important guiding significance for energy conservation and carbon reduction in global data centers.
### Page 3

range of IT load rate can be well cooled with the normal emergency cold water storage tank. Additionally, we need to determine the appropriate volume of the water tank that can meet the rated IT load. The rest of the study is organized as follows. Section 2 introduces the advanced MPC strategy for regulating the operating parameters with cold storage technology. Section 3 describes the cooling system’s framework of the data center. Subsequently, the simulation results are discussed in Section 4, and the conclusions are given in Section 5.
### Page 5

Cold storage mode OFF ON ON ON ON ON Variable frequency Cooling capacity: 3868.7 kWh; 4+1 Fig. 3 (e) centrifugal chiller Input power:523 kW Cold release mode ON ON OFF ON ON ON Water-water heat Heat transfer capacity: 3900 kW 4+1 Fig. 3 (f) exchanger Normal cooling mode OFF ON OFF OFF OFF OFF Chilled water pump Water flow rate: 600 m3/h; Pump head: 42 4+1 Fig. 3 (g) m; Input power: 90 kW Cooling water pump Water flow rate: 700 m3/h; Pump head: 35 4+1 m; Input power: 90 kW take only integer values (i.e., they must be whole numbers), while others Cold release pump Water flow rate: 450 m3/h; Pump head: 27 4+1 can take any real value. The objective is to find values for the variables m; Input power: 45 kW Cooling tower Water flow rate: 700 m3/h; Input power: 37 4+1 that minimize or maximize a linear objective function, subject to a set of kW; Air flow rate: 651132 m3/h linear equality and inequality constraints. The cold storage/release mode is executed according to the optimi­ zation results. By using MILP method for equipment scheduling opti­ storage and release flow rate, cold storage tank volume, 15min emer­ mization, the cooling unit is operated at an efficient point. The objective gency cold storage capacity, and the continuous operating time of the function is the lowest energy consumption during the optimization chiller. Before entering the optimization process, perform pre- period. Optimization is carried out under constraints such as cold calculations first. When in mechanical cooling mode, calculate the cooling system energy consumption of all combinations of PLR and
### Page 6

Table 4 Table 5 Time-segment of peak-valley electricity price. Thresholds in objective function and constraints. Peak section Flat section Valley Super-High section PLRmax PLRmin Gmax Gmin Gtank,sto, Gtank,sto, Rs α section min max Gtank,rel, Gtank,rel, 10:00–12:00 8:00–10:00 0:00–8:00 11:00–12:00 min max 14:00–19:00 12:00–14:00 Total 8 h 15:00–17:00 Total 7 h 19:00–24:00 High temperature days with daily (%) (%) m3/ m3/ m3/h m3/h Total 9 h maximum temperature ≥35 ◦ C in h h July, August and September 100 30 600 200 40 2000 7.744 5 1.1008 0.6475 0.2461 1.3759 %/24 RMB/kWh RMB/kWh RMB/kWh RMB/kWh
### Page 7

− dt ≥ QStorageMin (2) 2. The constraint conditions for the volume of the cold storage device are as follows: ( ) ∑PLRmax ∑Nrated ∑Gmax ∑Nrated Nk,i ∗ Qk,i + Uk,j ∗ Qk,j − H ∗ (1 − Y) QV,L ≤ S ∗ α i=PLRmin k=0 j=Gmin k=0 ( ) ) t (∑t ∑PLRmax ∑Nrated ∑Gmax ∑Nrated − dt ≤ − QReleaseMin + n=1 i=PLRmin k=0 Nk,i ∗ Qk,i + j=Gmin k=0 Uk,j ∗ Qk,j − dt (3) t ∗α ≤ QV,S (5)
### Page 7

where QV,L represents the lower limit of the capacity of the cold water storage tank, which is the cooling capacity of the 15 min emergency. The
### Page 8

Fig. 10. The cold storage and release time with MPC strategy of typical Fig. 9. Wet-bulb temperature of typical 3 days in Guangzhou. three days.
### Page 8

emergency cooling capacity is one-fourth of the terminal cooling ca­ 3. The constraints for the continuous running time of chillers are as pacity demand. QV,S refers to the upper limit of the capacity of the cold follows: water storage tank, which is the cooling capacity corresponding to the volume of the cold storage device. α represents the cooling capacity loss Pt / NRated ≤ Zt ≤ Pt (6) of the cold water storage tank for 1 h.
### Page 12

Fig. 17. The impact of MPC and Baseline strategies on annual PUE, cooling system energy consumption, and cooling system electricity charge in Guangzhou.
### Page 13

4.1. The influence of cold water storage tank volume on PUE 4.2. Analysis of cooling system operating parameters
### Page 14

to be turned on, with a PLR of 98.4 % and basically operating at full load, optimization of the temperature difference between supply and return with an average COP of 8.31. The average cooling water supply tem­ water on the performance of cooling system in the future. perature is 31 ◦ C, the PLR of the chiller is about 55 % with the highest COP. From Fig. 15, it can be seen that for MPC strategy, the average PLR CRediT authorship contribution statement of the chiller is 53 % by adjusting the storage and release capacity. The chiller is operating efficiently during both the storage and release pe­ Yiqun Zhu: Data curation, Formal analysis, Investigation, Method­ riods, with an average COP of 9.63, which is 15.88 % higher than the ology. Quan Zhang: Conceptualization, Methodology, Project admin­ Baseline strategy. On August 25th, the cooling system energy con­ istration, Supervision, Writing - review & editing, Funding acquisition. sumption of MPC strategy is 23884.16 kWh, and the Baseline strategy is Liping Zeng: Investigation, Software, Supervision, Writing - review & 29116.25 kWh. MPC strategy reduces the energy consumption by 17.97 editing. Jiaqiang Wang: Investigation, Methodology, Software, Fund­ %. ing acquisition. Sikai Zou: Funding acquisition, Methodology, Software, Writing - review & editing. 4.3. Annual energy performance analysis using MPC strategy in Guangzhou Declaration of competing interest

## 公式/优化模型候选

### Page 2

```text
Gmax         Maximum water flow rate allowed for chilled water pump                       (kWh)
                 (m3/h)                                                            α          Cooling capacity loss of the cold water storage tank for 1 h
    Gmin         Minimum water flow rate allowed for chilled water pump            Zt         Decision variable with a value of 0 or 1
```
### Page 2

```text
Pk,j         System energy consumption when the number of water-               PUEMPC PUE of MPC strategy
                 water heat exchanger is k and the cold water flow rate is j       ΔPUE       The value of PUEBaseline - PUEMPC
    Nk,i         Decision variable with a value of 0 or 1                          ΔPUEv      ΔPUE with a volume of v
```
### Page 2

```text
water heat exchanger is k and the cold water flow rate is j       ΔPUE       The value of PUEBaseline - PUEMPC
    Nk,i         Decision variable with a value of 0 or 1                          ΔPUEv      ΔPUE with a volume of v
    Uk,j         Decision variable with a value of 0 or 1                          ΔPUEr      The value of ΔPUEv+100 - ΔPUEv
```
### Page 2

```text
Nk,i         Decision variable with a value of 0 or 1                          ΔPUEv      ΔPUE with a volume of v
    Uk,j         Decision variable with a value of 0 or 1                          ΔPUEr      The value of ΔPUEv+100 - ΔPUEv
    QStorageMin Minimum cooling capacity calculated by the minimum                 Ppump      Pump power (kW)
```
### Page 2

```text
Gtank,sto,min Minimum cold storage water flow rate of the cold water           mw         Mass flow rate (kg/s)
                 storage tank (m3/h)                                               ηpump      Pump efficiency
    QStorageMax Maximum cooling capacity calculated by the minimum                 ηm         Motor efficiency
```
### Page 2

```text
storage tank (m3/h)                                               ηpump      Pump efficiency
    QStorageMax Maximum cooling capacity calculated by the minimum                 ηm         Motor efficiency
                 cold storage flow rate (kW)                                       ηv         Converter efficiency
```
### Page 2

```text
QStorageMax Maximum cooling capacity calculated by the minimum                 ηm         Motor efficiency
                 cold storage flow rate (kW)                                       ηv         Converter efficiency
    Gtank,sto,max Maximum cold storage water flow rate of the cold water           kpump      Pump speed ratio
```
### Page 5

```text
Mechanical cooling               ON         OFF          OFF          ON             OFF            ON         ON             OFF            ON            OFF
    Twet ≥ 20 ◦ C
    Fig. 3 (b)
```
### Page 5

```text
Free cooling                     OFF        ON           ON           OFF            ON             OFF        OFF            ON             OFF           ON
    Twet ≤ 14 ◦ C
    Fig. 3 (d)
```
### Page 5

```text
Cooling tower           Water flow rate: 700 m3/h; Input power: 37   4+1
that minimize or maximize a linear objective function, subject to a set of                                  kW; Air flow rate: 651132 m3/h
linear equality and inequality constraints.
```
### Page 6

```text
Time-segment of peak-valley electricity price.                                              Thresholds in objective function and constraints.
  Peak section    Flat section   Valley          Super-High section                          PLRmax    PLRmin    Gmax    Gmin    Gtank,sto,     Gtank,sto,    Rs       α
                                 section                                                                                         min            max
```
### Page 6

```text
Total 7 h     19:00–24:00                    High temperature days with daily            (%)       (%)       m3/     m3/     m3/h           m3/h
                  Total 9 h                      maximum temperature ≥35 ◦ C in                                  h       h
                                                 July, August and September                  100       30        600     200     40             2000          7.744    5
```
### Page 6

```text
((                          ) (                         ))                      Fig. 5. The impact of IT load rate and continuous operation time of the chiller
     ∑T       ∑PLRmax ∑Nrated              ∑Gmax ∑Nrated                                    on PUE under the emergency water tank volume. (Note: ΔPUE = PUEBaseline
min     t=t       i=PLR    k=0
```
### Page 6

```text
∑T       ∑PLRmax ∑Nrated              ∑Gmax ∑Nrated                                    on PUE under the emergency water tank volume. (Note: ΔPUE = PUEBaseline
min     t=t       i=PLR    k=0
                               Nk,i Pk,i +     j=G    k=0
```
### Page 6

```text
min     t=t       i=PLR    k=0
                               Nk,i Pk,i +     j=G    k=0
                                                          Uk,i Pk,i                         - PUEMPC).
```
### Page 6

```text
time domain; t is the time; Pk,i is the system energy consumption when                      have the condition that only one of them can be 1 at time t, which can be
                                                                                                          ∑∑            ∑∑
                                                                                            expressed as        Nt +          Ut = 1.
```
### Page 6

```text
∑∑            ∑∑
                                                                                            expressed as        Nt +          Ut = 1.
```
### Page 7

```text
(                                                                       )
                                                                                                                  ∑PLRmax ∑Nrated                       ∑Gmax ∑Nrated
                                                                                               − QReleaseMax ≤         i=PLRmin   k=0
```
### Page 7

```text
∑PLRmax ∑Nrated                       ∑Gmax ∑Nrated
                                                                                               − QReleaseMax ≤         i=PLRmin   k=0
                                                                                                                                        Nk,i ∗ Qk,i +       j=Gmin   k=0
```
### Page 7

```text
− QReleaseMax ≤         i=PLRmin   k=0
                                                                                                                                        Nk,i ∗ Qk,i +       j=Gmin   k=0
                                                                                                                                                                           Uk,j ∗ Qk,j
```
### Page 7

```text
t
                                                                                               − dt ≤ QStorageMax
                                                                                                                                                                                         (4)
```
### Page 7

```text
Fig. 7. The impact of the cold water storage tank on the PUE reduction of MPC
strategy at 70 %, 80 %, and 90 % IT load rates. (Note: ΔPUE = PUEBaseline -
                                                                                               rate, which is the cooling capacity calculated as the smaller value be­
```
### Page 7

```text
rate, which is the cooling capacity calculated as the smaller value be­
PUEMPC; ΔPUEr = ΔPUEv+100 - ΔPUEv. The v represents the volume of the                          tween the maximum flow rate of the cold release pipeline and the
water tank corresponding to the horizontal coordinate of this position).                       maximum cold release water flow rate of the cold water storage tank
```
### Page 7

```text
(
 ∑PLRmax ∑Nrated                 ∑Gmax ∑Nrated
                                                                   )                           of water-water heat exchanger is k and the chilled water flow rate is j; dt
```
### Page 7

```text
N k,i ∗ Q k,i +               Uk,j ∗ Qk,j + H ∗ Y                             is the cooling demand of the computer room at time t.
     i=PLR   k=0
            min                   j=G   k=0  min
```
### Page 8

```text
water storage tank, which is the cooling capacity corresponding to the
volume of the cold storage device. α represents the cooling capacity loss                       Pt / NRated ≤ Zt ≤ Pt                                                (6)
of the cold water storage tank for 1 h.
```
### Page 8

```text
(                                                      )         (                                                 )
           ∑PLRmax ∑Nrated              ∑Gmax ∑Nrated                       ∑PLRmax ∑Nrated            ∑Gmax ∑Nrated
                i=PLRmin   k=0
```
### Page 8

```text
∑PLRmax ∑Nrated              ∑Gmax ∑Nrated                       ∑PLRmax ∑Nrated            ∑Gmax ∑Nrated
                i=PLRmin   k=0
                               Nk,i +      j=Gmin     k=0
```
### Page 8

```text
i=PLRmin   k=0
                               Nk,i +      j=Gmin     k=0
                                                          Uk,j         −       i=PLRmin   k=0
```
### Page 8

```text
Nk,i +      j=Gmin     k=0
                                                          Uk,j         −       i=PLRmin   k=0
                                                                                              Nk,i +     j=Gmin   k=0
```
### Page 8

```text
Uk,j         −       i=PLRmin   k=0
                                                                                              Nk,i +     j=Gmin   k=0
                                                                                                                      Uk,j
```
### Page 8

```text
(                                                      ) t+1 (                                         )t                                                   (7)
          ∑PLRmax ∑Nrated               ∑Gmax      ∑Nrated             ∑PLRmax ∑Nrated        ∑Gmax ∑Nrated
≤ Pt ≤          i=PLRmin   k=0
```
### Page 8

```text
∑PLRmax ∑Nrated               ∑Gmax      ∑Nrated             ∑PLRmax ∑Nrated        ∑Gmax ∑Nrated
≤ Pt ≤          i=PLRmin   k=0
                               Nk,i +     j=Gmin    k=0
```
### Page 9

```text
(                                                             )       (                                                            )              (                                                     )
 ∑PLRmax ∑Nrated                  ∑Gmax ∑Nrated                        ∑PLRmax ∑Nrated                  ∑Gmax ∑Nrated                              ∑PLRmax ∑Nrated              ∑Gmax ∑Nrated
       i=PLRmin    k=0
```
### Page 9

```text
∑PLRmax ∑Nrated                  ∑Gmax ∑Nrated                        ∑PLRmax ∑Nrated                  ∑Gmax ∑Nrated                              ∑PLRmax ∑Nrated              ∑Gmax ∑Nrated
       i=PLRmin    k=0
                         Nk,i +     j=Gmin       k=0
```
### Page 9

```text
Uk,j       −           i=PLRmin   k=0
                                                                                               Nk,i +        j=Gmin   k=0
                                                                                                                            Uk,j         ≤ Pt ≤       i=PLRmin   k=0
```
### Page 9

```text
Nk,i +        j=Gmin   k=0
                                                                                                                            Uk,j         ≤ Pt ≤       i=PLRmin   k=0
                                                                                                                                                                       Nk,i +     j=Gmin   k=0
```
### Page 9

```text
Uk,j         ≤ Pt ≤       i=PLRmin   k=0
                                                                                                                                                                       Nk,i +     j=Gmin   k=0
                                                                                                                                                                                                 Uk,j
```
### Page 9

```text
(                                                              )
        ∑PLRmax ∑Nrated                 ∑Gmax ∑Nrated
   −         i=PLRmin    k=0
```
### Page 9

```text
∑PLRmax ∑Nrated                 ∑Gmax ∑Nrated
   −         i=PLRmin    k=0
                               Nk,i +        j=Gmin     k=0
```
### Page 9

```text
−         i=PLRmin    k=0
                               Nk,i +        j=Gmin     k=0
                                                              Uk,j           + H ∗ (1 − δt )
```
### Page 10

```text
3. Application in a hybrid cooling system case
∑R− 1
    k=1
```
### Page 10

```text
k=1
          Zt+k ≤ H ∗ (1 − Zt )                                              (9)        3.1. System description
```
### Page 10

```text
where Zt, Pt and δt are the decision variable; Zt is 0 or 1, which indicates              The study case is a real typical data center located in China. The data
whether the number of cooling units starts changes from t to t+1. If Zt is             center’s computer room layout consists of a total of 4 floors. The first
```
### Page 10

```text
0, it indicates that the number of cooling units has not changed. If Zt is 1,          layer has 190 IT racks, with 156 having a power of 6 kW and 34 having a
it indicates that the number of cooling units has changed. δt is 0 or 1,               power of 4 kW. The second, third, and fourth layers each have 700 IT
which means that the number of cooling units starts increases or de­                   racks, each with a power of 6 kW. The demand coefficient for IT
```
### Page 10

```text
which means that the number of cooling units starts increases or de­                   racks, each with a power of 6 kW. The demand coefficient for IT
creases from t to t + 1. If δt is 0, it indicates an increase in the number of         equipment capacity is 0.9. The rated IT load is 12304.8 kW. When
cooling units. If δt is 1, it indicates a decrease in the number of cooling            calculating, the heat load is 1.13 times the IT load. The partial PUE
```
### Page 10

```text
creases from t to t + 1. If δt is 0, it indicates an increase in the number of         equipment capacity is 0.9. The rated IT load is 12304.8 kW. When
cooling units. If δt is 1, it indicates a decrease in the number of cooling            calculating, the heat load is 1.13 times the IT load. The partial PUE
units. Pt represents the absolute value of the change quantity of the                  (pPUE) is the ratio of energy consumption of local areas or devices in a
```
### Page 12

```text
gmw Hw
                                                                                  Ppump =                                                                                   (11)
                                                                                            1000ηpump ηm ηv
```
### Page 12

```text
Ppump =                                                                                   (11)
                                                                                            1000ηpump ηm ηv
                                                                                                  (                 )
```
### Page 12

```text
(                 )
                                                                                  ηm = 0.94187 1 − e− 9.04kpump                                                             (12)
```
### Page 12

```text
ηv = 0.5087 + 1.283kpump − 1.42kpump 2 + 0.5834kpump 3                                    (13)
```
### Page 12

```text
where Ppump is pump power (kW); Hw is pump head (m); mw is mass flow
                                                                                  rate (kg/s); ηpump is pump efficiency; ηm is motor efficiency; ηv is con­
                                                                                  verter efficiency; kpump is pump speed ratio, that is, the ratio between the
```
### Page 12

```text
Eq. (10) shown below:
                                                                                        Pfan = a0 + a1 Gcw,nor + a2 Twet,nor + a3 Gcw,nor 2 + a4 Gcw,nor Twet,nor
COP = a0 + a1 PLR + a2 PLR2 + a3 (Tcwi − Tchws )
```
### Page 12

```text
Pfan = a0 + a1 Gcw,nor + a2 Twet,nor + a3 Gcw,nor 2 + a4 Gcw,nor Twet,nor
COP = a0 + a1 PLR + a2 PLR2 + a3 (Tcwi − Tchws )
                                                                      (10)        +a5 Twet,nor 2 + a6 Gcw,nor 3 + a7 Gcw,nor 2 Twet,nor + a8 Gcw,nor Twet,nor 2 + a9 Twet,nor 3
```
### Page 12

```text
(◦ C). The coefficients obtained according to the performance curve of
                                                                                  cooling water flow rate (m3/h). In mechanical cooling mode, a0 =
the chiller provided by the manufacturer are as follows: a0 = 4.4721, a1
```
### Page 13

```text
a7 = − 7.6165, a8 = 2.0545, a9 = 0.5333, and the R2 is 0.999. In the free            when the water tank volume ranges from 600 m3 to 1500 m3. At this
cooling mode with wet-bulb temperature above 5 ◦ C, a0 = − 0.4767, a1                situation, cooling load is high, the least of chillers can be used for MPC
```
### Page 13

```text
cooling mode with wet-bulb temperature above 5 ◦ C, a0 = − 0.4767, a1                situation, cooling load is high, the least of chillers can be used for MPC
= 4.6092, a2 = 16.9622, a3 = 1.1112, a4 = − 26.1715, a5 = − 42.1616.                 regulation. Therefore, the optimal volume of the water tank for 90 % IT
a6 = − 0.6698, a7 = 13.3499, a8 = 34.3616, a9 = 30.4930, and the R2 is               load rate is less than 70 % and 80 % IT load rates. Regarding the 80 % IT
```
### Page 13

```text
= 4.6092, a2 = 16.9622, a3 = 1.1112, a4 = − 26.1715, a5 = − 42.1616.                 regulation. Therefore, the optimal volume of the water tank for 90 % IT
a6 = − 0.6698, a7 = 13.3499, a8 = 34.3616, a9 = 30.4930, and the R2 is               load rate is less than 70 % and 80 % IT load rates. Regarding the 80 % IT
0.992. In the free cooling mode with wet-bulb temperature below 5 ◦ C,               load rate, the PUE significantly decrease when the water tank volume
```
### Page 13

```text
0.992. In the free cooling mode with wet-bulb temperature below 5 ◦ C,               load rate, the PUE significantly decrease when the water tank volume
a0 = 0.1399, a1 = 1.1003, a2 = − 1.0452, a3 = 0.1725, a4 = − 2.7741, a5              increases from 500 to 700 m3. This is because there is no cold storage
= 3.3106. a6 = − 0.2999, a7 = 2.4414, a8 = 2.8494, a9 = − 1.9106, and                and release regulation at 500 m3, however, the water tank 600 m3 and
```
### Page 13

```text
a0 = 0.1399, a1 = 1.1003, a2 = − 1.0452, a3 = 0.1725, a4 = − 2.7741, a5              increases from 500 to 700 m3. This is because there is no cold storage
= 3.3106. a6 = − 0.2999, a7 = 2.4414, a8 = 2.8494, a9 = − 1.9106, and                and release regulation at 500 m3, however, the water tank 600 m3 and
the R2 is 0.986.                                                                     700 m3 have 75 % and 100 % time to cooperate cooling with chiller in
```
### Page 13

```text
Table 5 shows the thresholds for the objective function and                      can meet the constraint of a continuous operating time of 3 h, resulting
constraint conditions in the case. PLRmax is 100 %; PLRmin is 30 %; Gmax             in a decrease in ΔPUE. When it increases to 1400 m3, ΔPUEr becomes
is 600 m3/h; Gmin is 200 m3/h; Gtank,sto,min and Gtank,rel,min are 40 m3/h;          less than 0.0005. Hence, the optimal water tank volume for 80 % IT load
```
### Page 13

```text
Gtank,sto,max and Gtank,rel,max are 2000 m3/h; Rs is 7.744. The loss of cold         rate is 1400 m3. Similarly, for the 70 % IT load rate, when the water tank
storage capacity over 24 h is less than 5 %. Therefore, α is set as 5 %/24           volume is 700 m3, it meets the constraint of a continuous operating time
in this paper.                                                                       of 3 h, so the ΔPUE is the smallest. Its optimal water tank volume is
```
### Page 13

```text
storage capacity over 24 h is less than 5 %. Therefore, α is set as 5 %/24           volume is 700 m3, it meets the constraint of a continuous operating time
in this paper.                                                                       of 3 h, so the ΔPUE is the smallest. Its optimal water tank volume is
                                                                                     1000 m3. Consequently, the optimal water tank volume is 1400 m3 to
```

## 符号表/变量定义候选

### Page 2

```text
Nomenclature                                                                              exchanger is k and the chilled water flow rate is j (kW)
                                                                                   dt         Cooling demand of the computer room at time t (kW)
    Twet         Wet-bulb temperature (◦ C)                                        QV,L       Lower limit of the capacity of the cold water storage tank
    PLRmax       Maximum PLR allowed for chiller                                              (kWh)
    PLRmin       Minimum PLR allowed for chiller                                   QV,S       Upper limit of the capacity of the cold water storage tank
    Gmax         Maximum water flow rate allowed for chilled water pump                       (kWh)
                 (m3/h)                                                            α          Cooling capacity loss of the cold water storage tank for 1 h
    Gmin         Minimum water flow rate allowed for chilled water pump            Zt         Decision variable with a value of 0 or 1
                 (m3/h)                                                            Pt         Absolute value of the change quantity of the cooling units
    Nrated       Rated number of the chiller                                                  at time t+1 and time t
    Pk,i         System energy consumption when the number of chiller is           R          Continuous operation restriction of the chiller
                 k and the PLR is i                                                PUEBaseline PUE of Baseline strategy
    Pk,j         System energy consumption when the number of water-               PUEMPC PUE of MPC strategy
                 water heat exchanger is k and the cold water flow rate is j       ΔPUE       The value of PUEBaseline - PUEMPC
    Nk,i         Decision variable with a value of 0 or 1                          ΔPUEv      ΔPUE with a volume of v
    Uk,j         Decision variable with a value of 0 or 1                          ΔPUEr      The value of ΔPUEv+100 - ΔPUEv
    QStorageMin Minimum cooling capacity calculated by the minimum                 Ppump      Pump power (kW)
                 cold storage flow rate (kW)                                       Hw         Pump head (m)
    Gtank,sto,min Minimum cold storage water flow rate of the cold water           mw         Mass flow rate (kg/s)
                 storage tank (m3/h)                                               ηpump      Pump efficiency
    QStorageMax Maximum cooling capacity calculated by the minimum                 ηm         Motor efficiency
                 cold storage flow rate (kW)                                       ηv         Converter efficiency
    Gtank,sto,max Maximum cold storage water flow rate of the cold water           kpump      Pump speed ratio
                 storage tank (m3/h)                                               Pfan       Energy consumption of the cooling tower fan (kW)
    QReleaseMin Minimum cooling capacity calculated by the minimum                 Gcw,nor    Normalized value of the cooling water flow rate
                 cold release flow rate (kW)                                       Twet,nor   Normalized value of the wet-bulb temperature
    Rs           Adjustable ratio of the valve                                     Gcw        Cooling water flow rate (m3/h)
    Gtank,rel,min Minimum cold release water flow rate of the cold water
                 storage tank (m3/h)                                               Acronyms
    QReleaseMax Maximum cooling capacity calculated by the minimum                 MPC      Model predictive control
                 cold release flow rate (kW)                                       MILP     Mixed integer linear programming
    Gtank,rel,max Maximum cold release water flow rate of the cold water           PUE      Power usage effectiveness
                 storage tank (m3/h)                                               COP      Coefficient of performance
    H            A sufficiently large positive constant                            PLR      Partial load rate
    Y            Decision variable with a value of 0 or 1                          OCL      Optimal chiller loading
    Qk,i         Cooling capacity when the number of chiller is k and the          IT       Information technology
                 PLR is i (kW)                                                     pPUE     Partial PUE
    Qk,j         Cooling capacity when the number of water-water heat
weather conditions and building loads, resulting in a 19.1 % increase in           air-cooled water chillers. When the economy control method was used
COP of chillers. This is a problem involving dynamic effects, where the            instead of the energy consumption control method, the energy con­
state of a moment can affect the subsequent device actions, making it              sumption increased by about 2.15 %, but the cost decreased by 2.94 %.
difficult for OCL to meet this scenario. Model predictive control (MPC)            Most of the above studies have focused on reducing electricity charges
strategy can solve this kind of cold storage scheduling problem.                   [18–22], with only a small number focusing on reducing energy con­
    Various factors affecting MPC strategy have been studied [18,19].              sumption [23,24].
Candanedo et al. [20] simplified the chiller and cold storage device                   The aforementioned research focuses on commercial buildings and
models, and the MPC algorithm saved 5%–20 % of electricity charge                  school buildings. However, the security requirements and cooling time
compared with the storage-priority strategy, and 20%–30 % compared                 of data centers are different from these buildings [25,26]. There is
with the chiller-priority strategy. Lee et al. [21] established an MPC             almost no research on MPC strategy for water storage systems in data
strategy that responds to changes in commercial building occupancy                 centers. To ensure the stability and security of IT equipment, data center
rates and time-varying electricity prices. The objective function is to            equips with the emergency cold water storage tank to provide 15 min of
minimize operational costs. Artificial neural network is used as the               cooling in the case of power failure [27]. The average IT load rate in
prediction model, and metaheuristics algorithm is used as the optimi­              China is around 50 % [28], while the IT load rate in newly built data
zation solver. Compared to rule-based control, MPC strategy reduced the            centers is even below 30 %. Therefore, after meeting the emergency cold
total operating costs by 3.4 %. D’Ettorre et al. [22] optimized the                storage capacity, the cold water storage tank still can collaborate with
operating cost of a hybrid heat pump system composed of an                         the chiller to improve the efficiency of whole cooling system.
electrically-driven air source heat pump and a gas boiler using MPC,                   In addition, free cooling can be widely utilized in data centers to
saving 8 % of the cost compared to traditional rule based storage free             reduce energy consumption [29,30]. Ranran et al. [4] extended the
control strategies. Chiam et al. [23] combined genetic algorithm with              available time for free cooling by optimizing the wind speed of the
mixed integer linear programming (MILP) in MPC strategy to reduce the              cooling tower, resulting in a maximum reduction of 21.05 % in energy
search space of the genetic algorithm, thus improving the possibility of           consumption of the chiller. Dong et al. [31] studied the energy-saving
global optimization. Satué et al. [24] carried out MPC strategy of                effect of using free cooling in data centers and found that the free
economy and energy consumption for the cooling system using                        cooling utilization rate in most areas exceeds 50 %, with an
                                                                               2
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
