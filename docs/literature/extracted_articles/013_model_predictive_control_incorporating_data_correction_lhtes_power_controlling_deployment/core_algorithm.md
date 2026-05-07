# 核心公式、伪代码和算法

## 抽取边界

- 来源 PDF：`2025_Gao_Model_predictive_control_incorporating_data_correction_for_LHTES_power_c.pdf`
- 标题：Model predictive control incorporating data correction for LHTES power controlling: Deployment and case study in data center
- 抽取重点：公式、优化目标、约束、MPC/MILP/控制流程、输入输出变量。
- 注意：PDF 公式转文本可能丢失上下标、希腊字母、分式结构和跨栏顺序；这里是低 token 检索索引，不是最终论文公式稿。

## 人工核对页线索

自动抽取；未做人工页码核对。

无人工补充说明。

## 算法/控制流程候选

### Page 1

Model predictive control incorporating data correction for LHTES power controlling: Deployment and case study in data center Jiacheng Gao a,b,c , Yanlong Lv a,b,c , Lejun Feng a,c,* , Jun Sui a,c, Hongguang Jin a,c a Institute of Engineering Thermophysics, Chinese Academy of Sciences, Beijing 100190, China b University of Chinese Academy of Sciences, Beijing 100190, China c Institute of New Energy, Dongguan 523808, China
### Page 1

• Built a high-performance LHTES model via theoretical modeling and experi­ mental calibration. • Developed MPC with coupled data correction to control LHTES power output. • The control strategy’s effectiveness was validated in a cooling system of data center.
### Page 1

Keywords: Latent Heat Thermal Energy Storage (LHTES) can effectively reduce cooling energy consumption in data centers LHTES through renewable energy utilization and peak load management. However, the lack of practical discharging MPC power control methods for real-world engineering applications has hindered their widespread adoption. To Data center address this challenge, this study used the model predictive control (MPC) strategy incorporating data correction Cooling system to solve the power control challenges of LHTES, and validated in a data center cooling system retrofit project. Power control Specifically, an efficient LHTES unit was first designed, with a series of charging/discharging experiments conducted to characterize its thermal storage properties. Based on the unit’s structure, a temperature field model was established, which achieved a prediction error below 5 % within the flow rate range of 0.5–1.5 m3/h through composite parameter identification using experimental data on heat transfer fluid and phase change material (PCM) temperatures. To mitigate model divergence caused by abrupt operating condition changes and accu­ mulated errors, an assimilation method based on extended Kalman filtering was employed for real-time model
### Page 2

correction. Building on this model, MPC-based LHTES power control was implemented, achieving a control error as low as 3 %. To verify the feasibility of the proposed model in practical engineering applications, validation was conducted in a small-scale data center in China. Results showed that integrating the LHTES system with optimized operation strategies reduced the relative error in global power control to 1.52 %, while achieving 21.5 % energy savings and 60.3 % operational cost reduction. This strategy addresses the control challenge in LHTES applications, providing reliable technical support for the implementation of LHTES technology in data centers.
### Page 2

yexp (k) the experimentally observed values at the k-th time step out Outflowing sim Simulated results Abbreviations exp Experimental results PCM Phase Change Material liq Liquid state PCM plates HDPE plates filled with PCM sol Solid state TES Thermal Energy Storage k|k − 1 The value at time step k derived from the state at time step LHTES Latent Heat Thermal Energy Storage k-1 HTF Heat Transfer Fluid k|k The value at time step k based on the state at time step k PID Proportional-Integral-Derivative Control MPC Model Predictive Control Superscripts SOC The current state of charge m, n The node at the m-th row and n-th column
### Page 2

Fig. 1. Cooling system for data centers integrated with Thermal Energy Storage Unit.
### Page 4

Fig. 2. Schematic structure of LHTES. (a) Three-dimensional view of the cold storage tank of the LHTES unit, (b) photograph of a single phase change cold plate, (c) Heat transfer fluid channels between adjacent cold plates, (d) design drawing of the perforated baffle plate in the cold storage tank.
### Page 4

and recessed circular grooves on its surface, as shown in Fig. 2(b). The recessed grooves are designed to increase the heat transfer area. The protruding rings serve two main functions: (1) Mechanical support and positioning: The protrusions act as me­ chanical supports between adjacent PCM plates, interlocking with cor­ responding structures on adjacent plates to form a stable interlayer support system. (2) Fluid channel formation and enhancing heat transfer efficiency: These protrusions create regular fluid channels between adjacent plates, facilitating heat exchange of HTF within the plate assembly, as illus­ trated in Fig. 2(c). To further optimize fluid flow, perforated baffle plates were installed at the inlet and outlet of the device, with the design dimensions shown in Fig. 2(d). These plates ensure that the HTF flows uniformly into each heat transfer channel, thereby maintaining stable heat transfer within the LHTES cold storage tank.
### Page 7

(3) Update Phase. employs a MPC strategy to regulate the flow rate parameters. As a Calculate the Kalman gain: model-based receding horizon optimization control method, the core ( )− 1 control mechanism of MPC encompasses three key elements: Kk = Pk|k− 1 HTk Hk Pk|k− 1 HTk + Rk (10)
### Page 9

Fig. 5. Schematic of the Experimental facilities: (a) 3D design drawing of the LHTES device: 1. Fan coil unit; 2. Control panel; 3. Cold storage tank; 4. Temperature/ pressure sensor; 5. Circulation pump; 6. Cold energy meter; 7. Electric valve; (b) Actual photograph of the LHTES device, water tank, and chiller (the three constitute the complete LHTES cold release and storage operation modes); (c) Actual photograph of the internal cold storage tank of the LHTES device; (d) Schematic diagram of the sensor installation position inside the PCM plate (indicated by the red line). (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)
### Page 10

Fig. 7. Three views and dimensional drawings of LHTES storage tanks (a) Main view (b) Left view (c) Top view (d) Three-dimensional drawings.
### Page 13

Fig. 11. Effect diagram of equivalent parameter identification: (a) Results of 10 optimization iterations; (b) Comparison chart of model prediction and actual temperature under the operating condition with a flow rate of 1.0 m3/h after parameter identification; (c) Model prediction results after identification using only HTF outlet temperature without PCM internal temperature.
### Page 16

particle swarm optimization algorithm, as the optimization algorithm for MPC power control, can efficiently search in the solution space and quickly converge to the global optimal solution. At this time, the system is approximately in an unconstrained optimization state (the flow rate will not reach the limit value), ensuring the control accuracy. When the outlet temperature is high (insufficient cooling capacity), the power control is prone to fluctuations. The reason is that a larger flow rate is required to achieve the predetermined power, leading to frequent contact of the flow rate with the constraint boundaries, which significantly reduces the control effect. For operating conditions with insufficient cooling capacity, if the cold storage release is temporarily stopped to allow the HTF sufficient heat exchange time to reduce the outlet temperature, the power control accuracy can be effectively improved. Therefore, in the subsequent design of the power control strategy, it is necessary to fully consider the heat conduction delay effect and further enhance the stability of system operation by optimizing the handling of constraint conditions in the control logic.
### Page 22

Data availability [4] Güğül GN, Gökçül F, Eicker U. Sustainability analysis of zero energy consumption data centers with free cooling, waste heat reuse and renewable energy systems: a feasibility study. Energy 2023;262:125495. https://doi.org/10.1016/j. Data will be made available on request. energy.2022.125495. [5] Rong H, Zhang H, Xiao S, Li C, Hu C. Optimizing energy consumption for data centers. Renew Sustain Energy Rev 2016;58:674–91. https://doi.org/10.1016/j. References rser.2015.12.283. [6] Chakraborty S, Kramer B, Kroposki B. A review of power electronics interfaces for [1] TC9.9 A. Thermal Guidelines for Data Processing Environments – Expanded Data distributed energy systems towards achieving low-cost modular design. Renew Center Classes and Usage Guidance n.d. 2011. Sustain Energy Rev 2009;13:2323–35. https://doi.org/10.1016/j. [2] Lykou G, Mentzelioti D, Gritzalis D. A new methodology toward effectively rser.2009.05.005. assessing data center sustainability. Comput Secur 2018;76:327–40. https://doi. [7] Zhu Y, Zhang Q, Zeng L, Wang J, Zou S. An advanced control strategy of hybrid org/10.1016/j.cose.2017.12.008. cooling system with cold water storage system in data center. Energy 2024;291: [3] China Institute of Electronics. Cloud Computing White Paper 2023, https://www. 130304. https://doi.org/10.1016/j.energy.2024.130304. caict.ac.cn/english/research/whitepapers/202311/P020231103312619845700. pdf (accessed October 22, 2024).

## 公式/优化模型候选

### Page 2

```text
A           the coefficient matrix of the state vector X in state-space         Symbols
                equations                                                           φ          Material physical property dataset
    B           the coefficient matrix of the input vector u in state-space         ζ          Specific enthalpy
```
### Page 2

```text
B           the coefficient matrix of the input vector u in state-space         ζ          Specific enthalpy
                equations                                                           ρ          Density
    Cf          equivalent thermal capacitance                                      c          Specific heat capacity
```
### Page 2

```text
Cf          equivalent thermal capacitance                                      c          Specific heat capacity
                                                                                    λ          Thermal conductivity
    Rda         the thermal resistance of diffusion and advection of the
```
### Page 4

```text
composes the LHTES into three coupled subsystems: the HTF, heat ex­                  node distributions, and found that for the plate-type LHTES device they
change wall, and PCM, explicitly quantifying the interactive heat                    used, the configuration of m = 5 (nodes parallel to the flow direction)
transfer mechanisms among fluid convection, wall conduction, and PCM                 and n = 3 (nodes perpendicular to the flow direction) could achieve the
```
### Page 4

```text
change wall, and PCM, explicitly quantifying the interactive heat                    used, the configuration of m = 5 (nodes parallel to the flow direction)
transfer mechanisms among fluid convection, wall conduction, and PCM                 and n = 3 (nodes perpendicular to the flow direction) could achieve the
phase change. This decomposition approach not only retains clear                     optimal trade-off between computational accuracy and efficiency. Since
```
### Page 4

```text
physical significance but also ensures computational efficiency,                     the structure of our LHTES device is similar to theirs, we also adopted
rendering it suitable for the real-time optimization requirements of                 the node configuration of m = 5 and n = 3 for model division during our
MPC.                                                                                 research. The final computational results showed that this division
```
### Page 5

```text
⎪
⎪ Cf f =                     + f out f +                                                           the influences of detailed factors such as heat loss, contact thermal
⎪
```
### Page 5

```text
⎪
⎪ Cf f =                       + f out f + f in f , (m = 2, 3, 4)                                  efficiency of the model, but at the same time, it may lead to significant
⎪
```
### Page 5

```text
⎪
⎪ Cf f =                     + f in f                                                                  To compensate for the model errors caused by model simplification,
⎪
```
### Page 5

```text
⎪
⎪ Cw w =                     +               , (m = 1, 2, ⋯, 5)
⎪
```
### Page 5

```text
⎪
⎪ Cm,2        =                   +                 , (m = 1, 2, ⋯, 5)                                 It is worth noting that these equivalent parameters, in essence, are
⎪
```
### Page 5

```text
⎪
⎪ Cm,1        =                  +                , (m = 1, 2, ⋯, 5)
⎪
```
### Page 5

```text
⎪
⎪ Cm,3        =                       , (m = 1, 2, ⋯, 5)                                           simplified model closer to the real system through equivalent compen­
⎪
```
### Page 5

```text
dX                                                                                                     (2) To ensure the rationality of equivalent parameter adjustment, we
   = f(X, u)                                                                            (2)
dt                                                                                                 set clear boundary ranges, with parameter changes not exceeding ±50
```
### Page 6

```text
thereby enabling more efficient approximation of the global optimal                 {
                                                                                      X(k) = Δt⋅(A(k − 1)X(k − 1) + B(k)u(k)) + X(k − 1) + wk
solution in the nonlinear parameter space.                                                                                                            (6)
```
### Page 6

```text
solution in the nonlinear parameter space.                                                                                                            (6)
                                                                                      Z(k) = h(X(k), u(k) ) + vk
2.1.4. Real-time model calibration based on extended Kalman filter                     Where X(k) is the state matrix of the system at moment k;u(k) is the
```
### Page 6

```text
In practical engineering applications, models are often simplified to            control input vector at moment k, Z(k)is the measurement vector at
improve computational efficiency (e.g., neglecting heat losses and                  moment k，In this research，Z(k) = Tout (k) = Tf5 (k), wk , vk represent
contact thermal resistance between the PCM and heat exchange walls).                the process and observation noises, which are initially assumed to follow
```
### Page 6

```text
̂ k− 1|k− 1 , u(k-1) )
                                                                                      Xk|k− 1 = f( X
                                                                                                                                                           (7)
```
### Page 6

```text
(7)
   (1) The identification is based on temperature data at a selected flow             Pk|k− 1 = Fk− 1 Pk− 1|k− 1 FTk− 1 + Qk− 1
       rate, showing good fitting at this flow rate, but errors still persist
```
### Page 6

```text
̂ k− 1|k− 1 + Bk|k− 1 uk|k− 1 + X
                                                                                        Xk|k− 1 = Δt⋅ Ak− 1|k− 1 X                               ̂ k− 1|k− 1
                                                                                                                                                                          (8)
```
### Page 6

```text
(8)
       modes, model predictions tend to deviate from actual operating                   Z(k) = h(X(k) u(k) ) + vk
       conditions.
```
### Page 6

```text
dictions and actual measurements gradually increases due to the              estimates at time k − 1, respectively. With its initial state determined by
       cumulative effect of errors.                                                 the state equation. The dimension of the state vector is 25 × 1,
                                                                                    encompassing nodes for the heat exchange channel, the heat exchange
```
### Page 7

```text
(                    )− 1                                           control mechanism of MPC encompasses three key elements:
Kk = Pk|k− 1 HTk Hk Pk|k− 1 HTk + Rk                                    (10)
```
### Page 7

```text
X
  ̂ k|k = Xk|k− 1 + Kk (Zk − f(Xk|k− 1 , uk ) )                                           control algorithm.
                                                                    (11)
```
### Page 7

```text
(11)
  Pk|k = (I − Kk Hk )Pk|k− 1                                                          (2) Receding Horizon Optimization: In each control cycle, constructs
                                                                                          an objective function based on control objectives over a finite
```
### Page 7

```text
follows:                                                                              (3) Feedback Correction: Utilizes real-time system output data
       ∂h ⃒⃒        h(X(k) ) ⃒⃒                                                           collected by sensors to compute the deviation between actual and
Hk =       ⃒      =            Xk|k− 1 = H                              (12)              predicted values. Adjusts subsequent prediction trajectories
```
### Page 7

```text
∂h ⃒⃒        h(X(k) ) ⃒⃒                                                           collected by sensors to compute the deviation between actual and
Hk =       ⃒      =            Xk|k− 1 = H                              (12)              predicted values. Adjusts subsequent prediction trajectories
       ∂x Xk|k− 1     ∂x
```
### Page 7

```text
Hk =       ⃒      =            Xk|k− 1 = H                              (12)              predicted values. Adjusts subsequent prediction trajectories
       ∂x Xk|k− 1     ∂x
                                                                                          through a deviation compensation model, forming a closed-loop
```
### Page 7

```text
through a deviation compensation model, forming a closed-loop
   Where I is the identity matrix with dimensions 25 × 25; Δt is the time
                                                                                          feedback mechanism.
```
### Page 7

```text
feedback mechanism.
step, taken as 1 s; H = [01×4 , 1, 01×20 ]denotes the observation matrix.
The observation equation can be written asZ(k) = h(X(k) , uk ) + vk =
```
### Page 8

```text
N ⃦                             N− 1
                                                                                     function, and by adjusting the weighting coefficient λ, a balance can be
            ∑                      ⃦        ∑
```
### Page 8

```text
function, and by adjusting the weighting coefficient λ, a balance can be
            ∑                      ⃦        ∑
min J =           ⃦P(i) − Pref (i) ⃦2 + λ                             2
```
### Page 8

```text
∑                      ⃦        ∑
min J =           ⃦P(i) − Pref (i) ⃦2 + λ                             2
                                                   ‖ṁ(i + 1) − ṁ(i) ‖              achieved between control accuracy and flow rate variation, thereby
```
### Page 8

```text
‖ṁ(i + 1) − ṁ(i) ‖              achieved between control accuracy and flow rate variation, thereby
            i=1                             i=1                                      suppressing unnecessary fluctuations in the flow rate to some extent.
                          ⎧                                                             (3) Receding Horizon Optimization.
```
### Page 8

```text
⎧                                                             (3) Receding Horizon Optimization.
                          ⎪ 0 ≤ SOC ≤ 100                                 (13)
                          ⎪
```
### Page 8

```text
⎨                                                             At each sampling time t, three tasks are performed:
                      s.t. ṁmin ≤ ṁ ≤ ṁmax
                          ⎪
```
### Page 8

```text
⎪
                          ⎩ T (i) = T (1)                                            a) Input the current state: Use the current system state X(t) as the initial
                              in       in
```
### Page 8

```text
model          to      calculate   the predicted   output      sequence
P(i) = cf ṁf (i)[Tout (i) − Tin (i) ]                                    (14)          {                               }
                                                                                          P t+1|t , P t+2|t , …, P t+M|t .
```
### Page 9

```text
Flow Range: − 20-    Flow Accuracy:              leakage, as shown in Fig. 5(d), and the position of the sensor is indicated
                                      60 (m3/h)            ±0.01m3/h                   by the red line.
  Control Valve      AC-220 V         − 25-60 ◦ C
```
### Page 9

```text
Pt1000           − 200-200 ◦ C                                    release, as shown in Fig. 6.
    Resistance                                             Accuracy: ±0.1 ◦ C
                                      Refrigeration                                        Fig. 6 (a) illustrates the energy storage process in cool storage mode.
```
### Page 9

```text
Chiller Unit       AH11DCE-AC       Range:
                                                           Stability: ±0.1 ◦ C         The flow direction of the HTF is: Chiller Unit → V1 → V2 → LHTES Unit
                                      4–60 ◦ C
```
### Page 10

```text
identification.                                                                    (Tliq ), and phase equilibrium temperature (Tpc ); latent heat (ζ); solid
    The experiment begins with measuring the physical parameters of                density (ρsol ) and liquid density (ρliq ); solid thermal conductivity (λp,sol )
the LHTES device, including dimensions and weight. To illustrate the               and liquid thermal conductivity (λp,liq ); as well as solid specific heat
```
### Page 10

```text
The experiment begins with measuring the physical parameters of                density (ρsol ) and liquid density (ρliq ); solid thermal conductivity (λp,sol )
the LHTES device, including dimensions and weight. To illustrate the               and liquid thermal conductivity (λp,liq ); as well as solid specific heat
structure of the LHTES cold storage tank employed, we present the                  capacity (cp,sol ) and liquid specific heat capacity (cp,liq ).
```
### Page 12

```text
Initial Thermophysical Properties of the LHTES unit.
  Material                    Tsol (◦ C)   Tpc (◦ C)   Tliq (◦ C)   ζ(kJ/kg)   ρsol           ρliq (kg/m3)   λp,sol (W/m⋅   λp,liq (W/m⋅   cp,sol (J/(kg⋅K))   cp,liq (J/(kg⋅K))
                                                                               (kg/m3)                       K)             K)
```
### Page 12

```text
Temperature measurement: A PT1000 thermal resistance is used,                          peratures under different flow rates all exhibit regions with a slow
with an accuracy of ±0.1 ◦ C. The standard uncertainty is calculated                       temperature rise. After the phase change plateau of the phase change
according to the uniform distribution (0.1/√3 ≈ 0.058 ◦ C), and a                          material ends, the temperature rise rate of the outlet temperature ac­
```
### Page 12

```text
with an accuracy of ±0.1 ◦ C. The standard uncertainty is calculated                       temperature rise. After the phase change plateau of the phase change
according to the uniform distribution (0.1/√3 ≈ 0.058 ◦ C), and a                          material ends, the temperature rise rate of the outlet temperature ac­
coverage factor k = 2 (95 % confidence level) is adopted, resulting in an                  celerates significantly, which proves that the energy storage of phase
```
### Page 12

```text
according to the uniform distribution (0.1/√3 ≈ 0.058 ◦ C), and a                          material ends, the temperature rise rate of the outlet temperature ac­
coverage factor k = 2 (95 % confidence level) is adopted, resulting in an                  celerates significantly, which proves that the energy storage of phase
expanded uncertainty of ±0.12 ◦ C.                                                         change materials plays a certain role in maintaining the stability of the
```
### Page 12

```text
coverage factor k = 2 (95 % confidence level) is adopted, resulting in an                  celerates significantly, which proves that the energy storage of phase
expanded uncertainty of ±0.12 ◦ C.                                                         change materials plays a certain role in maintaining the stability of the
    Flow rate measurement: An electromagnetic flowmeter is used (pa­                       operating temperature.
```
### Page 12

```text
Flow rate measurement: An electromagnetic flowmeter is used (pa­                       operating temperature.
rameters can be found in Table 1), with a full-scale error of ±0.01 m3/h.                      Meanwhile, a comparison of these three figures shows that the
Similarly, the calculated standard uncertainty is approximately 0.0058                     temperature difference between the outlet temperature and the internal
```
### Page 12

```text
Similarly, the calculated standard uncertainty is approximately 0.0058                     temperature difference between the outlet temperature and the internal
m3/h, and the expanded uncertainty is ±0.012 m3/h.                                         temperature of the PCM narrows as the flow rate increases. This is
    Overall, the interference of the above uncertainties on the temper­                    because when the flow rate increases, the flow velocity of the HTF rises
```
### Page 12

```text
control strategies for the cold release process, both the experiments and                  within the target flow rate range (0.5–1.5 m3/h) were analyzed: this
parameter identification work are centered on the cold release process.                    range corresponds to a flow rate of 2.778 × 10− 5 m3/s in a single HTF
For the cold storage process, its goal is to achieve rapid storage of cold
```
### Page 13

```text
Thermophysical Properties of the LHTES unit After Parameter Identification.
  Material                     Tsol (◦ C)   Tpc (◦ C)   Tliq (◦ C)   ζ(kJ/kg)   ρsol           ρliq (kg/m3)   λp,sol (W/m⋅   λp,liq (W/m⋅   cp,sol (J/(kg⋅K))   cp,liq (J/(kg⋅K))
                                                                                (kg/m3)                       K)             K)
```
### Page 13

```text
(         )                                                                     concentrated between 240 and 270, demonstrating the stability of the
     4A 4 Hf × Wf                                                                           parameter identification.
dh =     ≈              = 0.016 m                                 (19)
```
### Page 13

```text
4A 4 Hf × Wf                                                                           parameter identification.
dh =     ≈              = 0.016 m                                 (19)
      P       2Wf                                                                               The parameter set with the smallest fitness value was selected as the
```
### Page 13

```text
P       2Wf                                                                               The parameter set with the smallest fitness value was selected as the
    Combined with the kinematic viscosity of the HTF (taken as 1.0 ×                        optimization result, and its optimized equivalent parameter values are
10− 6 m2/s), the calculated Reynolds number range is 178–535, indi­                         shown in Table 4.
```
### Page 13

```text
patterns and boundary layer development laws within this range are                          significant changes compared with the original values are observed in
consistent; therefore, Re = 356 (corresponding to 1.0 m3/h) was selected                    four parameters: Tsol, Tpc, Tliq, and the latent heat of phase change. The
as the midpoint of the range. Theoretically, this helps mitigate de­                        reason for this may be that with the increase in the number of cycles, the
```
### Page 15

```text
viations in SOC prediction.                                                             min power release test was designed. The power fluctuated within the
                  ∫t              ∫t                                                    range of 0–30 kW according to a certain strategy, with the inlet tem­
                     P(t)dt          cm(t)(Tin (t) − Tout (t) )dt
```
### Page 15

```text
P(t)dt          cm(t)(Tin (t) − Tout (t) )dt
SOCreal (t) = 1 − 0         =1− 0                                     (20)              perature maintained at Tin = 24∘C. The MPC strategy was implemented
                     Qmax                    Qmax                                       to control and validate the method’s accuracy. The control horizon of
```
### Page 17

```text
“charging-discharging” control mechanism, the system can achieve load
                                                                                       COP = a0 + a1 PLR + a2 PLR2 + a3 (Tcwi − Tchws )
balancing, efficient utilization of natural cold sources at night, and load                                                                                         (21)
```
### Page 17

```text
This proportion not only meets the adjustment requirements under                                 gmw Hw
typical operating conditions but also highlights the dynamic control                   Ppump =
                                                                                              1000ηpump ηm ηv
```
### Page 17

```text
typical operating conditions but also highlights the dynamic control                   Ppump =
                                                                                              1000ηpump ηm ηv
capability of MPC through capacity constraints.                                                    (                 )                                              (22)
```
### Page 17

```text
capability of MPC through capacity constraints.                                                    (                 )                                              (22)
    In Section 3.4 above, we determined that the cool storage capacity of              ηm = 0.94187 1 − e− 9.04kpump
a single cold storage module is approximately 45,200 kJ (equivalent to                 ηv = 0.5087 + 1.283kpump − 1.42k2pump + 0.5834k3pump
```
### Page 17

```text
In Section 3.4 above, we determined that the cool storage capacity of              ηm = 0.94187 1 − e− 9.04kpump
a single cold storage module is approximately 45,200 kJ (equivalent to                 ηv = 0.5087 + 1.283kpump − 1.42k2pump + 0.5834k3pump
12.56 kWh). Therefore, 219 cold storage modules need to be operated in
```
### Page 17

```text
parallel to meet the above-mentioned capacity requirement. Combined                       Where Ppump is pump power (kW); Hw is pump head (m); mw is mass
with the dimensional parameters of a single module in Table 2, the total               flow rate (kg/s); ηpump is pump efficiency; ηm is motor efficiency; ηv is
volume is calculated to be 134.69 m3. To compare the advantages of                     converter efficiency; kpump is pump speed ratio, that is the ratio between
```
### Page 17

```text
236.28 m3. In summary, the total volume of LHTES modules is reduced
                                                                                       Pfan =    f0 + f1 Gcw,nor + a2 Twet,nor
by approximately 43 % compared with water-based cold storage,
```
### Page 17

```text
Table 5
                                                                                       rate；Twet,nor is the normalized value of the wet-bulb temperature. a0 =
Fitting Results of COP for the Chiller.                                                0.1399, a1 = 1.1003, a2 = 1.0452, a3 = 0.1725, a4 = 2.7741, a5 = 3.3106.
```
### Page 19

```text
tive error between the model-predicted temperature and the                  gation, Data curation, Conceptualization. Yanlong Lv: Writing – review
       measured value is ≤5 %, which can reflect the internal temper­              & editing, Visualization, Supervision, Conceptualization. Lejun Feng:
       ature dynamics of LHTES within this flow range.                             Supervision, Resources, Project administration, Funding acquisition,
```
### Page 20

```text
⎪ Rin
    da =
⎪
```
### Page 20

```text
⎪
⎪        5Af λf + ṁf cf Lf
⎪
```
### Page 20

```text
⎪               2Lf
⎨ Rda = 5Af λf − ṁf cf Lf
⎪  out
```
### Page 20

```text
⎪
⎪  C f = c f ρf
⎪
```
### Page 20

```text
⎪
⎪  Rf =
⎪
```
### Page 20

```text
Where, Af = Hf Wf is the cross-sectional area of the HTF channel perpendicular to the flow direction; Ac = Hf Lf is the heat transfer area between the
HTF and the wall; Lf , Wf , Hf are the length, width, and height of the HTF channel, respectively; ρf , cf , λf , ṁ are the density, specific heat capacity,
```
### Page 20

```text
⎪
⎪ Cw = cw ρw Aw
⎪
```
### Page 20

```text
⎪
⎪ Rw =
⎪
```
### Page 21

```text
be obtained as:
            ∫ Tp
 hp,e =          cp,e dTp
```
### Page 21

```text
∫ Tp
 hp,e =          cp,e dTp
                               ∫ TP (                                                             ) )
```
### Page 21

```text
hp,e =          cp,e dTp
                               ∫ TP (                                                             ) )
                                                   (              )  12            (
```
### Page 21

```text
(              )  12            (
                           =         cp,sol + θj,i
                                               liq cp,liq − cp,sol +          θj,i   1 −   θ j,i
```
### Page 21

```text
=         cp,sol + θj,i
                                               liq cp,liq − cp,sol +          θj,i   1 −   θ j,i
                                                                                             liq ζ dTp
```
### Page 21

```text
(                               )(      (                   ) ( ( )            (  )))
                                                  12ζ               Tp,liq − Tp,sol ln σ Tp + σ Tpe
            = cp,sol Tp + cp,liq − cp,sol +                  Tp +                                                +
```
### Page 21

```text
12ζ               Tp,liq − Tp,sol ln σ Tp + σ Tpe
            = cp,sol Tp + cp,liq − cp,sol +                  Tp +                                                +
                                              Tliq − Tsol                                12
```
### Page 21

```text
(       (                ) ( ( )        (    )) (                          ) ( ))                                             (A8)
              12ζ               Tp,liq − Tp,sol ln σ Tp + σ Tpe              Tp,liq − Tp,sol σ Tp
                        Tp −                                          −       ( ( )              (   ))
```
### Page 22

```text
1        − 1 − 1                        1
        ⎢ 1,1            + 1,1 , 0, 0, 0, 0, 1,1 , 0, 0, 0, 0, 01×5 ⎥
        ⎢ Cp
```
### Page 22

```text
⎢ 1            − 1 − 1                        1                     ⎥
        ⎢ 1,2 0,            + 1,2 , 0, 0, 0, 0, 1,2 , 0, 0, 0, 01×5 ⎥
        ⎢ Cp
```
### Page 22

```text
⎢ 1               −  1     −  1                  1                  ⎥
A33,1 = ⎢ 1,3 0, 0,
        ⎢                       + 1,3 , 0, 0, 0, 0, 1,3 , 0, 0, 01×5 ⎥
```
### Page 22

```text
A33,1 = ⎢ 1,3 0, 0,
        ⎢                       + 1,3 , 0, 0, 0, 0, 1,3 , 0, 0, 01×5 ⎥
          C
```
### Page 22

```text
⎢ 1                   − 1 − 1                       1               ⎥
        ⎢         0, 0, 0,         +         , 0, 0, 0, 0,      , 0, 01×5
                                                                            ⎥
```
### Page 22

```text
⎢ 1                      −  1     − 1                   1           ⎥
        ⎣         0, 0, 0, 0,          + 1,5 , 0, 0, 0, 0, 1,5 , 01×5 ⎦
          Cp1,5
```
### Page 22

```text
⎢ 1             1                   −  1      −  1               1         ⎥
A33,2 = ⎢
        ⎢ C2,3 0, 0, R1,3 , 0, 0, 0, 0, R1,3 + R2,3 , 0, 0, 0, 0, R2,3 , 0, 0 ⎥
```

## 符号表/变量定义候选

### Page 2

```text
Nomenclature                                                                    EKF        Extended Kalman Filter
    A           the coefficient matrix of the state vector X in state-space         Symbols
                equations                                                           φ          Material physical property dataset
    B           the coefficient matrix of the input vector u in state-space         ζ          Specific enthalpy
                equations                                                           ρ          Density
    Cf          equivalent thermal capacitance                                      c          Specific heat capacity
                                                                                    λ          Thermal conductivity
    Rda         the thermal resistance of diffusion and advection of the
                                                                                    ζ          Convective heat transfer coefficient
                HTF
    Rc          the thermal resistance                                              Subscripts
    T           temperatures                                                        f          HTF
    u           The input vector of the state-space model                           w          the heat exchange wall
    X           The output matrix of the state-space model                          p          the PCM
    ysim        the model-predicted values at the k-th time step                    in         Inflowing
     (k)
    yexp
     (k)
                the experimentally observed values at the k-th time step            out        Outflowing
                                                                                    sim        Simulated results
    Abbreviations                                                                   exp        Experimental results
    PCM       Phase Change Material                                                 liq        Liquid state
    PCM plates HDPE plates filled with PCM                                          sol        Solid state
    TES       Thermal Energy Storage                                                k|k − 1 The value at time step k derived from the state at time step
    LHTES     Latent Heat Thermal Energy Storage                                               k-1
    HTF       Heat Transfer Fluid                                                   k|k        The value at time step k based on the state at time step k
    PID       Proportional-Integral-Derivative Control
    MPC       Model Predictive Control                                              Superscripts
    SOC       The current state of charge                                           m, n       The node at the m-th row and n-th column
                                                                                    data centers play a crucial role in data storage [1] and computational
                                                                                    processing [2]. With the deployment of large models such as ChatGPT,
1. Introduction                                                                     data center construction has witnessed exponential growth [3]. It is
                                                                                    projected that by 2030, their energy consumption will account for 13 %
    As the core infrastructure of the information technology industry,
                                      Fig. 1. Cooling system for data centers integrated with Thermal Energy Storage Unit.
                                                                                2
```

## 面向本项目的复现接口

- 输入侧优先映射：天气/湿球温度、IT cooling load、TOU 电价、PV 预测、TES/SOC 初始状态、设备容量和效率曲线。
- 状态侧优先映射：TES/SOC、室温或供回水温度、设备启停状态、储冷/释冷功率。
- 决策侧优先映射：chiller/heat-exchanger/pump/fan 负荷率、储冷/释冷动作、MPC 滚动时域控制量。
- 目标侧优先映射：能耗、电费、PUE、约束违背惩罚、启停或动作平滑惩罚。
- 验证边界：任何文献节能率或控制效果都不能直接迁移为本项目结果，必须通过本地模型或 `mpc_v2` 验证矩阵复核。
