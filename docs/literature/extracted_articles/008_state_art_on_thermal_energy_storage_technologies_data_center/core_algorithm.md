# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2020_Liu_State_of_the_art_on_thermal_energy_storage_technologies_in_data_center.pdf`
- 标题：State-of-the-art on thermal energy storage technologies in data center
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

p3-p5 TES principles; p10-p15 active TES; p17 operation strategies based on TES to reduce operation cost.

核心支撑数据中心 TES 背景、蓄冷技术分类和运行策略，不是当前模型已实现事实。

## 算法/控制流程候选

### Page 1

State-of-the-art on thermal energy storage technologies in data center Lijun Liu a, Quan Zhang a,⇑, Zhiqiang (John) Zhai b,⇑, Chang Yue a, Xiaowei Ma a a College of Civil Engineering, Hunan University, Changsha, Hunan 410082, China b Department of Civil, Environmental and Architectural Engineering, University of Colorado at Boulder, USA
### Page 1

Article history: Data center consumes a great amount of energy and accounts for an increasing proportion of global Received 4 December 2019 energy demand. Low efficiency of cooling systems leads to a cooling cost at about 40% of the total energy Revised 23 May 2020 consumption of a data center. Due to specific operation conditions, high security and high cooling load is Accepted 24 July 2020 required in data center. To achieve energy saving, cost saving and high security, novel cooling systems Available online 29 July 2020 integrated with thermal energy storage (TES) technologies have been proposed. This paper presents an extensive overview of the research advances and the applications of TES technologies in data centers. Keywords: Operating conditions, energy mismatch and requirement of high security in data center were overviewed. Thermal energy storage Data center Principles and characteristics of TES technologies were discussed. Applications of passive TES coupled air Energy saving flow and applications of active TES integrated cooling system are summarizes, and the design and perfor- Emergency cooling mance of these TES integrated thermal systems are analyzed, with a focus on energy saving, cost savings Cooling system design and high security. Ó 2020 Elsevier B.V. All rights reserved.
### Page 2

TES Thermal energy storage AHU Air handle unit LTES Latent thermal energy storage ACU Air conditioner unit STES Sensible thermal energy storage PCB Phase change board DP Dew Point UFAD Under-floor air distribution system RH Relative humidity EDL Enthalpy difference laboratory CPU Central processing unit COP Coefficient of performance CRAC Computer room air conditioner PUE Power usage effectiveness UPS Uninterrupted power supply HP Heat pipe EES Electricity energy storage TPCT Two-phase closed thermosyphon PCM Phase change material TCO Total cost of ownership ATES Aquifer thermal energy storage HX Heat exchanger TBS Telecommunications base station
### Page 3

Energy supply–demand mismatches exist in energy consump- tion process. Thermal energy storage technology adapts to the vari- ations in outdoor temperature and user cooling requirement (i.e., supply–demand mismatches). During the operation of data cen- ters, five supply–demand mismatches commonly occur, including:
### Page 12

actual temperature profile of underground should be verified. In addition, legal aspects are suggested to be deeply researched, since benefits and requirements for operation of ATES are ambiguous. Studies mentioned above mainly focus on utilizing of diurnal/ seasonal/ cold energy and low electricity price to achieve energy saving and cost saving. You et al. [91] designed a kind of air- cooled system to provide cold energy for emergency cooling to data centers by the application of TES. Zhang et al. [92] realized emergency through control strategies and TES technology.

## 公式/优化模型候选

未在可抽取文本中发现明确公式候选；可能需要渲染 PDF 页面人工读取。

## 符号表/变量定义候选

### Page 2

```text
Nomenclature/Abbreviations
     TES           Thermal energy storage                                                                                AHU             Air handle unit
     LTES          Latent thermal energy storage                                                                         ACU             Air conditioner unit
     STES          Sensible thermal energy storage                                                                       PCB             Phase change board
     DP            Dew Point                                                                                             UFAD            Under-floor air distribution system
     RH            Relative humidity                                                                                     EDL             Enthalpy difference laboratory
     CPU           Central processing unit                                                                               COP             Coefficient of performance
     CRAC          Computer room air conditioner                                                                         PUE             Power usage effectiveness
     UPS           Uninterrupted power supply                                                                            HP              Heat pipe
     EES           Electricity energy storage                                                                            TPCT            Two-phase closed thermosyphon
     PCM           Phase change material                                                                                 TCO             Total cost of ownership
     ATES          Aquifer thermal energy storage
     HX            Heat exchanger
     TBS           Telecommunications base station
         5.3.  TES integrated free cooling system . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 14
               5.3.1.    TES combined heat pipe system . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 15
               5.3.2.    TES coupling evaporative cooling system . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 15
    6.   Operation strategies based on TES to reduce operation cost. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 17
    7.   Conclusions and future work. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 18
         Declaration of Competing Interest . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 18
         Acknowledgements . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 18
         References . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 18
1. Introduction                                                                                                              In the current, TES technologies of data center have been paid
                                                                                                                         more and more attention and are evolving rapidly. The purpose
    Data centers, which house computing servers, network equip-                                                          of this paper is to provide the fundamental knowledge and a
ment, cooling devices, power supplying sets, and other related                                                           review of existing literatures of TES in data center. Section 1 briefly
equipment, experience fast growth as an integral part of informa-                                                        introduced energy consumption in data center and TES technolo-
tion and communication technology. Due to the massive computa-                                                           gies. In section 2, operating conditions, energy mismatches, and
tion and data interactions, data centers consume explosive amount                                                        security requirement in data center are overviewed. Section 3 dis-
of energy. The energy consumption of data centers is approxi-                                                            cusses principles and the characteristics of TES technologies in data
mately 1.1%-1.5% of the total global electricity consumption in                                                          center with a focus on TES materials and TES configurations. Appli-
2011 and it will continue to increase with the rate that is doubling                                                     cations of passive TES coupled air flow, and applications of active
every two years until 2020 [1–3]. Among this huge energy con-                                                            TES integrated cooling systems, are analyzed in section 4 and sec-
sumption, cooling devices, as one of the main infrastructures pro-                                                       tion 5, respectively. Operation strategies are analyzed in section 6.
viding proper operating conditions for servers, account for about                                                        The last section summarizes the main findings and development
30–40% of total consumption, taking up the second largest propor-                                                        directions. The outlook of the components is shown in Fig. 1. This
tion, while IT equipment of servers, I/O devices and storages utilize                                                    article is expected to be helpful to understand the state-of-the-art
most of the energy [4–5]. Energy saving and energy efficiency                                                            of TES in data center, and to improve the reliability and energy effi-
enhancement in cooling system of data center is urgent, and kinds                                                        ciency of data center through the TES integration.
of technologies have been applied to achieve it, including free cool-
ing, air distribution optimization, variable frequency technology                                                        2. Overview of data center
and energy storage technology [6–9]. Among them, thermal energy
storage is one of the most promising technologies to enhance the                                                         2.1. Operating conditions
efficiency of energy sources (and increase the energy efficiency of
cooling system), which overcomes many mismatch between                                                                      Cooling devices are applied to control temperature, humidity
energy supply and demand in terms of time, temperature or site.                                                          and particle concentration to create suitable environments for IT
    Advantages of TES integrated energy systems include enhance-                                                         servers, which is determinant for the reliability and efficiency of
ment of overall efficiency and reliability, better economic feasibil-                                                    data center operations. In order to ensure a reliable and efficient
ity, less operating costs and less environmental pollution [9]. TES                                                      operation of computing servers, America Society of Heating, Refrig-
technologies have been utilized in many occasions for years, and                                                         erating and Air-conditioning Engineers (ASHRAE) developed ther-
various TES units and systems have been proposed and studied                                                             mal guidelines for data processing environment. Classes A1-A4
extensively [10–12]. Many researchers studied performance of dif-                                                        were proposed to define suitable temperatures and humidity set-
ferent thermal energy storage materials and different thermal                                                            ting ranges for data centers at different cooling levels (as shown
energy storage configures, which are the important impacts of                                                            in Fig. 2), and an indoor environment with temperature ranging
thermal energy storage technologies [13–14]. Besides thermal                                                             from 18 to 27 °C and moisture ranging from 9°C-15 °C DP (Dew
energy storage materials and configures, applications of TES inte-                                                       Point) and 60% RH(relative humidity) was suggested to be optimal
grated thermal management system (including cooling system                                                               [15]. Cooling systems should provide proper temperature and
and air flow) in data center, shown its own characteristics as well                                                      humidity for the computer room to maintain the safe and reliable
as inherent challenges, which are the focus of this review.                                                              operation of the systems.
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
