# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2025_Campoy_Nieves_Sinergym_A_virtual_testbed_for_building_energy_optimization_with_Reinfor.pdf`
- 标题：Sinergym – A virtual testbed for building energy optimization with Reinforcement Learning
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

Sinergym – A virtual testbed for building energy optimization with Reinforcement Learning Alejandro Campoy-Nieves ∗ , Antonio Manjavacas, Javier Jiménez-Raboso, Miguel Molina-Solana, Juan Gómez-Romero Department of Computer Science and Artiﬁcial Intelligence, Universidad de Granada, Granada, 18071, Spain
### Page 1

Dataset link: https:// Simulation has become a crucial tool for Building Energy Optimization (BEO) as it enables the evaluation of github.com/ugr-sail/sinergym diﬀerent design and control strategies at a low cost. Machine Learning (ML) algorithms can leverage large- scale simulations to learn optimal control from vast amounts of data without supervision, particularly under Keywords: Building Energy Optimization the Reinforcement Learning (RL) paradigm. Unfortunately, the lack of open and standardized tools has hindered Simulation the widespread application of ML and RL to BEO. To address this issue, this paper presents Sinergym, an open- HVAC source Python-based virtual testbed for large-scale building simulation, data collection, continuous control, and EnergyPlus experiment monitoring. Sinergym provides a consistent interface for training and running controllers, predeﬁned Machine Learning benchmarks, experiment visualization and replication support, and comprehensive documentation in a ready-to- Reinforcement Learning use software library. This paper 1) highlights the main features of Sinergym in comparison to other existing frameworks, 2) describes its basic usage, and 3) demonstrates its applicability for RL-based BEO through several representative examples. By integrating simulation, data, and control, Sinergym supports the development of intelligent, data-driven applications for more eﬃcient and responsive building operations, aligning with the objectives of digital twin technology.
### Page 1

* Corresponding author. E-mail addresses: alejandroac79@correo.ugr.es (A. Campoy-Nieves), manjavacas@ugr.es (A. Manjavacas), jajimer@correo.ugr.es (J. Jiménez-Raboso), miguelmolina@ugr.es (M. Molina-Solana), jgomez@decsai.ugr.es (J. Gómez-Romero). 1 https://www.iea.org/reports/buildings. 2 https://www.unep.org/resources/report/2021-global-status-report-buildings-and-construction. 3 https://www.doe2.com/equest/. 4 https://www.carrier.com/commercial/en/us/software/hvac-system-design/building-system-optimizer. 5 https://energyplus.net. 6 https://modelica.org.
### Page 3

RL TestBed EnergyPlus v9.5.0 Custom patch Gym 1 3 in simulator v0.15.7 Energym EnergyPlus v9.5.0 Functional Mock-up No 7 14 and Modelica v2.14 Interface (FMI) BOPTEST-Gym Modelica v4.0.0 HTTP REST API Gymnasium 7 7 (based on FMI) v0.28.1 Sinergym EnergyPlus v24.1.0 EnergyPlus Gymnasium 4 87 Python API v0.2 v0.29.1
### Page 3

Simulator: Building simulation engine (EnergyPlus, Modelica or both). Middleware: Com- munication interface between Gym/Gymnasium and the simulator. API: Is the tool compliant with the Gym/Gymnasium interface? Buildings: Number of diﬀerent buildings included. Envs: Number of predeﬁned environments (buildings & conﬁguration parameters).
### Page 3

WeatherSet: Can each building be used with diﬀerent weather conﬁgurations? Weath- erVar: Does the temperature dataset vary between episodes? Actions: Which action spaces are supported? (discrete, continuous or both). DynamicSp: Dynamic spaces; can an environment be conﬁgured with diﬀerent action and observation spaces than the predeﬁned? CustomRw: Can custom rewards be deﬁned?
### Page 5

sends actions to and receives observations from the simulated building rides the default building control by overwriting the default EnergyPlus through the Gymnasium interface (communication layer). The Gymna- schedulers. When actions are sent to the simulation by calling step, sium interface communicates with the simulation engine through the Sinergym transparently interrupts the simulation, sets the control sig- EnergyPlus Python API (middleware layer). The EnergyPlus engine runs nal, and resumes the process. the simulation (simulator layer) and updates the building state. The agent may use the information received from the environment to de- 4. Functionalities termine the subsequent control action and to modify its behaviour to maximize future rewards. This section provides an overview of the key functionalities of Sin- Every Sinergym simulation requires two data ﬁles to conﬁgure and ergym 3.6.2. For updated information and examples, please refer to its launch the control process: oﬃcial documentation website.12
### Page 8

The installation and conﬁguration of the software are eﬀortless by This section showcases the practical application of Sinergym 3.6.2 using PyPi15 or the Docker distribution.16 Consequently, Sinergym can through four BEO use cases: 1) testing the default control of a EnergyPlus run on a local machine or a cloud computing infrastructure. building model, 2) using a custom rule-based controller, 3) training DRL controllers from scratch, and 4) hyperparameter optimization of the DRL 15 https://pypi.org/project/sinergym/. algorithm. The environment is the predeﬁned Eplus-datacenter- 16 https://hub.docker.com/r/sailugr/sinergym. mixed-continuous-stochastic-v1, featuring the 2ZoneData-
### Page 13

Heating Setpoint RL Heating Setpoints 15.0 22.0 RL algorithm conﬁguration and hyperparameters The hyperparameters Cooling Setpoint RL Cooling Setpoints 22.0 30.0 and neural network architecture used to train the DRL agents in subsection 5.5 follow the default conﬁgurations of StableBaselines3. Speciﬁcally, the neural network consists of two fully connected lay- Acknowledgements ers with 64 units per layer for PPO, 256 units per layer for SAC, and 400 and 300 units respectively for each layer in TD3. This work was funded by ERDF/Junta de Andalucía (D3S project, Table A.10 presents the grid search in the hyperparameter optimiza- P21.00247), MICIU/AEI/10.13039/501100011033 (SPEEDY project, tion developed with PPO algorithm in subsection 5.4. Each experiment TED2021.130454B.I00) and the NextGenerationEU funds (IA4TES was executed during 20 episodes, with intermediate evaluations every project, MIA.2021.M04.0008). A. Manjavacas is funded by ERDF/Junta 3 episodes. de Andalucía under SE21_UGR_IFMIF-DONES project.
### Page 14

Table A.10 Hyperparameter space used for PPO grid search optimization (108 total combinations).

## 公式/优化模型候选

### Page 6

```text
which maps variables to the building actuators. In particular, the ob-
𝑇𝑡+1 = (1 − 𝜇)𝑇𝑡 − 𝜏 + 𝜎(𝑊𝑡+1 − 𝑊𝑡 )                                                   (1)
                                                                                                 servation space incorporates meters, dates and other output variables
```
### Page 7

```text
4.6. Controllers
𝑟𝑡 = −𝜔 𝜆𝑃 𝑃𝑡 − (1 − 𝜔) 𝜆𝑇 (|𝑇𝑡 − 𝑇𝑢𝑝 | + |𝑇𝑡 − 𝑇𝑙𝑜𝑤 |)                      (2)
where 𝑃𝑡 represents power consumption (W); 𝑇𝑡 is the current indoor                       Every controller in Sinergym is a process that sends actions to the
```

## 符号表/变量定义候选

未发现明确 Nomenclature/Acronyms 段。

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
