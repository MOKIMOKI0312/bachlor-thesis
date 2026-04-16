%% seed02-best 最优模型全年详细可视化
% PUE = 1.282, Comfort violation = 1.2%
% 用于检查各项数据是否物理合理

clear; clc; close all;

%% 加载数据
dataDir = fileparts(mfilename('fullpath'));
d = readtable(fullfile(dataDir, 'e0_hourly_seed02_best.csv'));
if height(d) > 8760, d = d(1:8760, :); end

N = 8760;
hours = (1:N)';

% 时间轴：构造 datetime 用于更直观的 x 轴
t = datetime(2025,1,1,0,0,0) + calendarDuration(0,0,0,hours-1,0,0);

% 月份分隔线位置
month_starts = datetime(2025, 1:12, 1);
months_cn = {'1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'};

%% ===== 图1: 温度总览（室外 + 室内 + 舒适区）=====
figure('Name','温度总览','Position',[50 50 1500 600],'Color','w');

yyaxis left
plot(t, d.outdoor_temp_C, 'Color', [0.9 0.5 0.1 0.4], 'LineWidth', 0.3);
hold on;
plot(t, movmean(d.outdoor_temp_C, 24), 'Color', [0.9 0.5 0.1], 'LineWidth', 2);
ylabel('室外温度 (°C)');

yyaxis right
plot(t, d.indoor_temp_C, 'Color', [0.1 0.4 0.9 0.4], 'LineWidth', 0.3);
hold on;
plot(t, movmean(d.indoor_temp_C, 24), 'Color', [0.1 0.4 0.9], 'LineWidth', 2);
% 舒适区
yline(18, 'r--', 'LineWidth', 1.2);
yline(27, 'r--', 'LineWidth', 1.2);
ylabel('室内温度 (°C)');

title(sprintf('全年温度 | 室外: %.1f ~ %.1f°C | 室内: %.1f ~ %.1f°C | 越限: %.1f%%', ...
    min(d.outdoor_temp_C), max(d.outdoor_temp_C), ...
    min(d.indoor_temp_C), max(d.indoor_temp_C), ...
    sum(d.indoor_temp_C<18 | d.indoor_temp_C>27)/N*100));
legend('室外(逐时)','室外(日均)','室内(逐时)','室内(日均)','舒适区边界', 'Location','north','Orientation','horizontal');
grid on; xlim([t(1) t(end)]);

%% ===== 图2: PUE 全年 =====
figure('Name','PUE 全年','Position',[50 50 1500 500],'Color','w');

% 逐时 + 日均 + 月均
pue_daily = movmean(d.pue, 24);

fill([t(1); t(end); t(end); t(1)], [1 1 1.1 1.1], [0.7 1 0.7], ...
    'FaceAlpha', 0.3, 'EdgeColor', 'none'); hold on;
fill([t(1); t(end); t(end); t(1)], [1.1 1.1 1.3 1.3], [1 1 0.7], ...
    'FaceAlpha', 0.3, 'EdgeColor', 'none');
fill([t(1); t(end); t(end); t(1)], [1.3 1.3 1.6 1.6], [1 0.8 0.7], ...
    'FaceAlpha', 0.3, 'EdgeColor', 'none');

plot(t, d.pue, 'Color', [0.5 0.5 0.5 0.3], 'LineWidth', 0.3);
plot(t, pue_daily, 'b-', 'LineWidth', 1.5);
yline(mean(d.pue), 'r-', sprintf('年均 PUE = %.3f', mean(d.pue)), 'LineWidth', 2, 'FontSize', 12);

ylabel('PUE'); ylim([1.0 1.7]);
title(sprintf('PUE 全年曲线 | 年均 = %.3f | 最低 = %.3f | 最高 = %.3f', ...
    mean(d.pue), min(d.pue), max(d.pue)));
legend('优秀(<1.1)', '良好(1.1~1.3)', '一般(1.3~1.6)', '逐时', '日均', 'Location', 'northwest');
grid on; xlim([t(1) t(end)]);

%% ===== 图3: 功率分解 =====
figure('Name','功率分解','Position',[50 50 1500 700],'Color','w');

subplot(3,1,1);
a = area(t, [d.power_ite_kW, d.power_cooling_kW]);
a(1).FaceColor = [0.2 0.6 1.0]; a(1).FaceAlpha = 0.7; a(1).EdgeColor = 'none';
a(2).FaceColor = [1.0 0.4 0.2]; a(2).FaceAlpha = 0.7; a(2).EdgeColor = 'none';
ylabel('功率 (kW)');
title(sprintf('功率分解 | IT: %.0f MWh/年 | 冷却: %.0f MWh/年 | 总: %.0f MWh/年', ...
    sum(d.power_ite_kW)/1e3, sum(d.power_cooling_kW)/1e3, sum(d.power_facility_kW)/1e3));
legend('IT 负荷', '冷却系统', 'Location', 'northeast');
grid on; xlim([t(1) t(end)]);

subplot(3,1,2);
plot(t, d.power_cooling_kW, 'Color', [1 0.4 0.2 0.3], 'LineWidth', 0.3); hold on;
plot(t, movmean(d.power_cooling_kW, 24), 'Color', [0.8 0.2 0], 'LineWidth', 1.5);
ylabel('冷却功率 (kW)');
title(sprintf('冷却功率 | 均值: %.0f kW | 峰值: %.0f kW | 谷值: %.0f kW', ...
    mean(d.power_cooling_kW), max(d.power_cooling_kW), min(d.power_cooling_kW)));
grid on; xlim([t(1) t(end)]);

subplot(3,1,3);
plot(t, d.power_ite_kW, 'Color', [0.2 0.6 1.0 0.3], 'LineWidth', 0.3); hold on;
plot(t, movmean(d.power_ite_kW, 24), 'Color', [0 0.3 0.8], 'LineWidth', 1.5);
ylabel('IT 功率 (kW)');
title(sprintf('IT 负荷 | 均值: %.0f kW | 峰值: %.0f kW | 利用率均值: %.1f%%', ...
    mean(d.power_ite_kW), max(d.power_ite_kW), mean(d.ite_utilization)*100));
grid on; xlim([t(1) t(end)]);

%% ===== 图4: HVAC 四个控制变量 =====
figure('Name','HVAC 控制变量','Position',[50 50 1500 800],'Color','w');

subplot(4,1,1);
plot(t, d.fan_flow_kgs, 'Color', [0.2 0.5 0.8], 'LineWidth', 0.5);
hold on; plot(t, movmean(d.fan_flow_kgs, 24), 'r-', 'LineWidth', 1.5);
ylabel('流量 (kg/s)');
title(sprintf('CRAH 风机流量 | 范围: %.0f ~ %.0f kg/s | 均值: %.0f', ...
    min(d.fan_flow_kgs), max(d.fan_flow_kgs), mean(d.fan_flow_kgs)));
% 标注 EMS 控制范围
yline(500, 'k--', 'EMS下限 500'); yline(2000, 'k--', 'EMS上限 2000');
grid on; xlim([t(1) t(end)]);

subplot(4,1,2);
plot(t, d.crah_supply_C, 'b-', 'LineWidth', 0.5); hold on;
plot(t, d.crah_return_C, 'r-', 'LineWidth', 0.5);
plot(t, movmean(d.crah_supply_C, 24), 'b-', 'LineWidth', 2);
plot(t, movmean(d.crah_return_C, 24), 'r-', 'LineWidth', 2);
ylabel('温度 (°C)');
title(sprintf('CRAH 送风/回风温度 | 送风: %.1f ~ %.1f°C | 回风: %.1f ~ %.1f°C | ΔT均值: %.1f°C', ...
    min(d.crah_supply_C), max(d.crah_supply_C), ...
    min(d.crah_return_C), max(d.crah_return_C), ...
    mean(d.crah_return_C - d.crah_supply_C)));
legend('送风(逐时)','回风(逐时)','送风(日均)','回风(日均)', 'Location','best');
% 标注 EMS 控制范围
yline(11, 'k--', 'CRAH_T下限 11'); yline(22, 'k--', 'CRAH_T上限 22');
grid on; xlim([t(1) t(end)]);

subplot(4,1,3);
plot(t, d.chiller_t_C, 'Color', [0 0.5 0.5], 'LineWidth', 0.5);
hold on; plot(t, movmean(d.chiller_t_C, 24), 'r-', 'LineWidth', 1.5);
ylabel('温度 (°C)');
title(sprintf('冷机出水温度设定 | 范围: %.1f ~ %.1f°C | 均值: %.2f°C', ...
    min(d.chiller_t_C), max(d.chiller_t_C), mean(d.chiller_t_C)));
yline(5.6, 'k--', 'EMS下限 5.6'); yline(10, 'k--', 'EMS上限 10');
grid on; xlim([t(1) t(end)]);

subplot(4,1,4);
plot(t, d.ct_pump_kgs, 'Color', [0.6 0.3 0.8], 'LineWidth', 0.5);
hold on; plot(t, movmean(d.ct_pump_kgs, 24), 'r-', 'LineWidth', 1.5);
ylabel('流量 (kg/s)');
title(sprintf('冷凝水泵流量 | 范围: %.0f ~ %.0f kg/s | 均值: %.0f', ...
    min(d.ct_pump_kgs), max(d.ct_pump_kgs), mean(d.ct_pump_kgs)));
yline(300, 'k--', 'EMS下限 300'); yline(5000, 'k--', 'EMS上限 5000');
grid on; xlim([t(1) t(end)]);

%% ===== 图5: 温度-冷却耦合关系 =====
figure('Name','温度与冷却耦合','Position',[50 50 1200 500],'Color','w');

subplot(1,2,1);
scatter(d.outdoor_temp_C, d.power_cooling_kW, 3, d.pue, 'filled', 'MarkerFaceAlpha', 0.3);
colorbar; colormap(jet);
xlabel('室外温度 (°C)'); ylabel('冷却功率 (kW)');
title('室外温度 vs 冷却功率 (颜色=PUE)');
grid on;

subplot(1,2,2);
scatter(d.outdoor_temp_C, d.pue, 3, d.month, 'filled', 'MarkerFaceAlpha', 0.3);
colorbar; colormap(hsv);
xlabel('室外温度 (°C)'); ylabel('PUE');
title('室外温度 vs PUE (颜色=月份)');
grid on;

%% ===== 图6: 月度统计箱线图 =====
figure('Name','月度统计','Position',[50 50 1400 700],'Color','w');

subplot(2,2,1);
boxplot(d.pue, d.month, 'Labels', months_cn);
ylabel('PUE'); title('月度 PUE 分布'); grid on;

subplot(2,2,2);
boxplot(d.indoor_temp_C, d.month, 'Labels', months_cn);
hold on; yline(18,'r--'); yline(27,'r--');
ylabel('室内温度 (°C)'); title('月度室内温度分布'); grid on;

subplot(2,2,3);
boxplot(d.power_cooling_kW, d.month, 'Labels', months_cn);
ylabel('冷却功率 (kW)'); title('月度冷却功率分布'); grid on;

subplot(2,2,4);
boxplot(d.fan_flow_kgs, d.month, 'Labels', months_cn);
ylabel('风机流量 (kg/s)'); title('月度 CRAH 风机流量分布'); grid on;

%% ===== 图7: 典型周放大（夏季 + 冬季）=====
figure('Name','典型周放大','Position',[50 50 1500 800],'Color','w');

% 夏季典型周: 7月14-20日
summer_idx = (hours >= 4633) & (hours <= 4800);  % ~7月14-20日
t_summer = t(summer_idx);
% 冬季典型周: 1月13-19日
winter_idx = (hours >= 289) & (hours <= 456);   % ~1月13-19日
t_winter = t(winter_idx);

% 夏季
subplot(2,4,1);
plot(t_summer, d.outdoor_temp_C(summer_idx), 'r-', 'LineWidth', 1); hold on;
plot(t_summer, d.indoor_temp_C(summer_idx), 'b-', 'LineWidth', 1);
yline(27,'r--'); yline(18,'r--');
ylabel('°C'); title('夏季 温度'); legend('室外','室内','Location','best'); grid on;

subplot(2,4,2);
plot(t_summer, d.pue(summer_idx), 'b-', 'LineWidth', 1);
ylabel('PUE'); title('夏季 PUE'); grid on;

subplot(2,4,3);
plot(t_summer, d.fan_flow_kgs(summer_idx), 'b-', 'LineWidth', 1); hold on;
plot(t_summer, d.ct_pump_kgs(summer_idx), 'r-', 'LineWidth', 1);
ylabel('kg/s'); title('夏季 风机/泵'); legend('风机','冷凝泵'); grid on;

subplot(2,4,4);
plot(t_summer, d.crah_supply_C(summer_idx), 'b-', 'LineWidth', 1); hold on;
plot(t_summer, d.chiller_t_C(summer_idx), 'r-', 'LineWidth', 1);
ylabel('°C'); title('夏季 送风/冷机温度'); legend('CRAH送风','冷机出水'); grid on;

% 冬季
subplot(2,4,5);
plot(t_winter, d.outdoor_temp_C(winter_idx), 'r-', 'LineWidth', 1); hold on;
plot(t_winter, d.indoor_temp_C(winter_idx), 'b-', 'LineWidth', 1);
yline(27,'r--'); yline(18,'r--');
ylabel('°C'); title('冬季 温度'); legend('室外','室内','Location','best'); grid on;

subplot(2,4,6);
plot(t_winter, d.pue(winter_idx), 'b-', 'LineWidth', 1);
ylabel('PUE'); title('冬季 PUE'); grid on;

subplot(2,4,7);
plot(t_winter, d.fan_flow_kgs(winter_idx), 'b-', 'LineWidth', 1); hold on;
plot(t_winter, d.ct_pump_kgs(winter_idx), 'r-', 'LineWidth', 1);
ylabel('kg/s'); title('冬季 风机/泵'); legend('风机','冷凝泵'); grid on;

subplot(2,4,8);
plot(t_winter, d.crah_supply_C(winter_idx), 'b-', 'LineWidth', 1); hold on;
plot(t_winter, d.chiller_t_C(winter_idx), 'r-', 'LineWidth', 1);
ylabel('°C'); title('冬季 送风/冷机温度'); legend('CRAH送风','冷机出水'); grid on;

%% ===== 图8: IT 负荷利用率 =====
figure('Name','IT 负荷','Position',[50 50 1400 400],'Color','w');

yyaxis left;
plot(t, d.ite_utilization, 'Color', [0 0.5 0 0.3], 'LineWidth', 0.3); hold on;
plot(t, movmean(d.ite_utilization, 24), 'Color', [0 0.5 0], 'LineWidth', 1.5);
ylabel('IT 利用率');

yyaxis right;
plot(t, d.power_ite_kW, 'Color', [0.2 0.4 0.8 0.3], 'LineWidth', 0.3); hold on;
plot(t, movmean(d.power_ite_kW, 24), 'Color', [0.2 0.4 0.8], 'LineWidth', 1.5);
ylabel('IT 功率 (kW)');

title(sprintf('IT 负荷利用率 | 均值: %.1f%% | 范围: %.1f%% ~ %.1f%%', ...
    mean(d.ite_utilization)*100, min(d.ite_utilization)*100, max(d.ite_utilization)*100));
legend('利用率(逐时)','利用率(日均)','功率(逐时)','功率(日均)', 'Location','northeast');
grid on; xlim([t(1) t(end)]);

%% ===== 图9: 湿度 =====
figure('Name','湿度','Position',[50 50 1400 350],'Color','w');

plot(t, d.humidity_pct, 'Color', [0.3 0.6 0.9 0.3], 'LineWidth', 0.3); hold on;
plot(t, movmean(d.humidity_pct, 24), 'Color', [0.1 0.3 0.7], 'LineWidth', 1.5);
ylabel('相对湿度 (%)');
title(sprintf('室内相对湿度 | 均值: %.1f%% | 范围: %.1f%% ~ %.1f%%', ...
    mean(d.humidity_pct), min(d.humidity_pct), max(d.humidity_pct)));
grid on; xlim([t(1) t(end)]);

%% ===== 图10: Reward 分解 =====
figure('Name','Reward 分解','Position',[50 50 1400 500],'Color','w');

subplot(2,1,1);
plot(t, d.reward, 'Color', [0.3 0.3 0.3 0.3], 'LineWidth', 0.3); hold on;
plot(t, movmean(d.reward, 24), 'k-', 'LineWidth', 1.5);
yline(mean(d.reward), 'r--', sprintf('均值 = %.4f', mean(d.reward)), 'LineWidth', 1);
ylabel('Reward'); title(sprintf('逐时 Reward | 总计: %.1f | 均值: %.4f', sum(d.reward), mean(d.reward)));
grid on; xlim([t(1) t(end)]);

subplot(2,1,2);
cum_reward = cumsum(d.reward);
plot(t, cum_reward, 'b-', 'LineWidth', 1.5);
ylabel('累积 Reward');
title(sprintf('累积 Reward 曲线 | 终值: %.1f', cum_reward(end)));
grid on; xlim([t(1) t(end)]);

%% ===== 打印汇总 =====
fprintf('\n');
fprintf('================================================================\n');
fprintf('  seed02-best 全年评估汇总\n');
fprintf('================================================================\n');
fprintf('  PUE:          年均 = %.3f, 范围 [%.3f, %.3f]\n', mean(d.pue), min(d.pue), max(d.pue));
fprintf('  总电力:       %.0f MWh/年 (均值 %.0f kW)\n', sum(d.power_facility_kW)/1e3, mean(d.power_facility_kW));
fprintf('  IT 电力:      %.0f MWh/年 (均值 %.0f kW)\n', sum(d.power_ite_kW)/1e3, mean(d.power_ite_kW));
fprintf('  冷却电力:     %.0f MWh/年 (均值 %.0f kW, 峰值 %.0f kW)\n', sum(d.power_cooling_kW)/1e3, mean(d.power_cooling_kW), max(d.power_cooling_kW));
fprintf('  室内温度:     均值 %.1f°C, 范围 [%.1f, %.1f]°C\n', mean(d.indoor_temp_C), min(d.indoor_temp_C), max(d.indoor_temp_C));
fprintf('  温度越限:     %.1f%% (%.0f 小时)\n', sum(d.indoor_temp_C<18|d.indoor_temp_C>27)/N*100, sum(d.indoor_temp_C<18|d.indoor_temp_C>27));
fprintf('  室外温度:     均值 %.1f°C, 范围 [%.1f, %.1f]°C\n', mean(d.outdoor_temp_C), min(d.outdoor_temp_C), max(d.outdoor_temp_C));
fprintf('  CRAH 风机:    均值 %.0f kg/s, 范围 [%.0f, %.0f]\n', mean(d.fan_flow_kgs), min(d.fan_flow_kgs), max(d.fan_flow_kgs));
fprintf('  冷机出水:     均值 %.1f°C, 范围 [%.1f, %.1f]°C\n', mean(d.chiller_t_C), min(d.chiller_t_C), max(d.chiller_t_C));
fprintf('  冷凝水泵:     均值 %.0f kg/s, 范围 [%.0f, %.0f]\n', mean(d.ct_pump_kgs), min(d.ct_pump_kgs), max(d.ct_pump_kgs));
fprintf('  CRAH ΔT:      均值 %.1f°C\n', mean(d.crah_return_C - d.crah_supply_C));
fprintf('  IT 利用率:    均值 %.1f%%, 范围 [%.1f%%, %.1f%%]\n', mean(d.ite_utilization)*100, min(d.ite_utilization)*100, max(d.ite_utilization)*100);
fprintf('  室内湿度:     均值 %.1f%%\n', mean(d.humidity_pct));
fprintf('  总 Reward:    %.1f\n', sum(d.reward));
fprintf('================================================================\n');
fprintf('\n已生成 10 个图窗，可交互缩放查看。\n');
