# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2021_Tarragona_Systematic_review_on_model_predictive_control_strategies_applied_to_acti.pdf`
- 标题：Systematic review on model predictive control strategies applied to active thermal energy storage systems
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

Systematic review on model predictive control strategies applied to active thermal energy storage systems Joan Tarragona a, b, Anna Laura Pisello b, c, Cèsar Fernández a, Alvaro de Gracia a, Luisa F. Cabeza a, * a GREiA Research Group, Universitat de Lleida, Pere de Cabrera s/n, 25001-Lleida, Spain b CIRIAF – Interuniversity Research Centre on Pollution and Environment Mauro Felli, Via G. Duranti 63, 06125, Perugia, Italy c Department of Engineering, University of Perugia, Via G. Duranti 93, Perugia, 06125, Italy
### Page 2

Table 1 Query string to search scientific documents related to TES and MPC. QUERY string
### Page 2

(“thermal energy storage” OR “cold energy storage” OR “latent near/3 storage” OR TITLE-ABS-KEY ((“thermal energy storage” OR “cold energy storage” OR “latent W/3 “sensible near/3 storage” OR “thermochemical near/3 storage” OR "*sorption near/3 storage” OR “sensible W/3 storage” OR “thermochemical W/3 storage” OR "*sorption W/ storage”) AND (“model predictive control”) 3 storage”) AND (“model predictive control”))
### Page 4

Table 2 Summary of MPC strategies applied to heating equipment with active TES. Ref. Year TES material Occupancy schedule Type of study ToU tariff Renewable energy MPC settings
### Page 4

Water PCM N/A Residential Office Service N/A Simulation Experimental Yes No PV panels Solar collectors Wind No Prediction turbines horizon
### Page 7

Maintenance cost the authors designed an MPC strategy using a stochastic formulation to move the model towards a more realistic framework. The behaviour of this random approach was successfully managed by the designed MPC
### Page 7

reduction control tool, encouraging the authors to consider it in future studies. MPC objective function
### Page 7

Regarding the review of the literature related to cooling systems, the • • • • • • • • • only studies found among all the publications reviewed applied MPC strategies to cooling systems based on HVAC equipment with active TES •
### Page 7

A summary of all MPC studies that contain cooling systems with active TES was done. Table 4 provides all the information extracted from these studies, detailing the same characteristics as in the heating systems •
### Page 7

Candanedo et al. [66] analysed the behaviour of a cooling system based on a chiller controlled by an MPC strategy to optimize the charging and discharging processes of an ice bank. The results highlighted the ability MPC approach
### Page 7

of MPC to optimize the operation of the ice bank. This was confirmed by Dehkordi and Candanedo [67] in a comparison of the same system operating under MPC and a rule-based control (RBC) strategy. Similarly, Beghi et al. [68,69] compared the ability of an MPC strategy to manage a • • • • • • • • •
### Page 7

effective in terms of energy efficiency and demand satisfaction than the other strategies analysed. Aiming to take advantage of the operational MPC settings
### Page 7

flexibility of the active TES, Pertzborn [70] and Cao et al. [71] also Biomass No Prediction horizon
### Page 7

systems, both located in service buildings. A step further was taken by Touretzky et al. [72], who also applied MPC in a service building, but in • •
### Page 7

this case, the authors used a commercial PCM instead of ice. The ca­ Summary of MPC strategies applied to district heating networks with active TES.
### Page 7

study, Touretzky and Baldea [73] proposed a hierarchical MPC strategy with a continuous reformulation of this scheduling problem. This panels
### Page 7

approach showed that the strategy solved the problem in a short period Residential Office Service N/ PV
### Page 7

tained good control system behaviour that coordinated the relatively slow phase change dynamics of the TES and the relatively fast temper­ •
### Page 7

ature dynamics elsewhere. Focusing on the occupancy schedule, almost all the cooling systems studied in the literature were in service and office buildings. Only • • • • • • • •
### Page 7

cyclical demand profiles, as is the case of both office and service buildings. From a computational perspective, simple MPC configura­ Table 3
### Page 8

Table 4 Summary of MPC strategies applied to cooling equipment with active TES. Ref. Year TES material Occupancy schedule Type of study ToU tariff Renewable energy
### Page 8

Water Ice Another PCM N/A Residential Office Service Test room N/A Simulation Experimental Yes No PV panels Solar collectors
### Page 9

Free cooling No Prediction horizon Time step Centralized Distributed Deterministic Stochastic Hierarchical Hybrid Cost reduction Other
### Page 10

Table 5 Summary of MPC strategies applied to CSP plants with active TES. Ref. Year TES material MPC settings MPC approach MPC objective function

## 公式/优化模型候选

未在可抽取文本中发现明确公式候选；可能需要渲染 PDF 页面人工读取。

## 符号表/变量定义候选

未发现明确 Nomenclature/Acronyms 段。

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
