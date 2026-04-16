%% E0 南京基线评估结果可视化
% 数据来源: 4 seed × (best + latest) checkpoint 的全年逐时评估
% 使用方法: 在 MATLAB 中直接运行此脚本，可交互缩放查看

clear; clc; close all;

%% ===== 数据加载 =====
dataDir = fileparts(mfilename('fullpath'));

% 加载推荐的两个模型
d_best = readtable(fullfile(dataDir, 'e0_hourly_seed02_best.csv'));
d_safe = readtable(fullfile(dataDir, 'e0_hourly_seed03_latest.csv'));

% 截断到 8760 行（EnergyPlus 有时多输出 1 步）
if height(d_best) > 8760, d_best = d_best(1:8760, :); end
if height(d_safe) > 8760, d_safe = d_safe(1:8760, :); end

% 加载所有 8 个模型用于对比
labels = {'seed01\_best','seed01\_latest','seed02\_best','seed02\_latest',...
          'seed03\_best','seed03\_latest','seed04\_best','seed04\_latest'};
files  = {'e0_hourly_seed01_best.csv','e0_hourly_seed01_latest.csv',...
          'e0_hourly_seed02_best.csv','e0_hourly_seed02_latest.csv',...
          'e0_hourly_seed03_best.csv','e0_hourly_seed03_latest.csv',...
          'e0_hourly_seed04_best.csv','e0_hourly_seed04_latest.csv'};

allData = cell(1, length(files));
for i = 1:length(files)
    t = readtable(fullfile(dataDir, files{i}));
    if height(t) > 8760, t = t(1:8760, :); end
    allData{i} = t;
end

N = 8760;
hours = (1:N)';
months_str = {'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'};

%% ===== Figure 1: 全年 PUE 逐时曲线 =====
figure('Name','PUE Annual Profile','Position',[100 100 1400 500]);

% 上: seed02-best (最优 PUE)
subplot(2,1,1);
plot(hours, d_best.pue, 'b-', 'LineWidth', 0.3);
hold on;
% 24h 滑动平均
pue_smooth = movmean(d_best.pue, 24);
plot(hours, pue_smooth, 'r-', 'LineWidth', 1.5);
yline(mean(d_best.pue), 'k--', sprintf('Mean PUE = %.3f', mean(d_best.pue)), 'LineWidth', 1);
ylabel('PUE'); title('seed02-best (PUE=1.282) - 全年逐时 PUE');
legend('逐时 PUE', '24h 滑动平均', 'Location', 'northeast');
xlim([1 8760]); ylim([1.0 1.8]); grid on;
% 添加月份标记
month_starts = [1, 745, 1417, 2161, 2881, 3625, 4345, 5089, 5833, 6553, 7297, 8017];
xticks(month_starts); xticklabels(months_str);

% 下: seed03-latest (最安全)
subplot(2,1,2);
plot(hours, d_safe.pue, 'Color', [0 0.6 0], 'LineWidth', 0.3);
hold on;
pue_smooth2 = movmean(d_safe.pue, 24);
plot(hours, pue_smooth2, 'r-', 'LineWidth', 1.5);
yline(mean(d_safe.pue), 'k--', sprintf('Mean PUE = %.3f', mean(d_safe.pue)), 'LineWidth', 1);
ylabel('PUE'); title('seed03-latest (PUE=1.293) - 全年逐时 PUE');
legend('逐时 PUE', '24h 滑动平均', 'Location', 'northeast');
xlim([1 8760]); ylim([1.0 1.8]); grid on;
xticks(month_starts); xticklabels(months_str);
xlabel('月份');

%% ===== Figure 2: 功率分解 =====
figure('Name','Power Breakdown','Position',[100 100 1400 700]);

subplot(3,1,1);
area(hours, [d_best.power_ite_kW, d_best.power_cooling_kW], ...
    'FaceColor', 'flat', 'EdgeColor', 'none');
colororder([0.2 0.6 1.0; 1.0 0.4 0.2]);
ylabel('功率 (kW)'); title('seed02-best - 功率分解 (IT + 冷却)');
legend('IT 负荷', '冷却系统', 'Location', 'northeast');
xlim([1 8760]); grid on;
xticks(month_starts); xticklabels(months_str);

subplot(3,1,2);
plot(hours, d_best.power_cooling_kW, 'Color', [1 0.4 0.2], 'LineWidth', 0.3);
hold on;
plot(hours, movmean(d_best.power_cooling_kW, 24), 'r-', 'LineWidth', 1.5);
ylabel('冷却功率 (kW)'); title('冷却系统功率 (24h 平均)');
xlim([1 8760]); grid on;
xticks(month_starts); xticklabels(months_str);

subplot(3,1,3);
plot(hours, d_best.outdoor_temp_C, 'Color', [0.8 0.4 0], 'LineWidth', 0.3);
hold on;
plot(hours, movmean(d_best.outdoor_temp_C, 24), 'k-', 'LineWidth', 1.5);
ylabel('温度 (°C)'); title('南京室外温度');
xlim([1 8760]); grid on;
xticks(month_starts); xticklabels(months_str);
xlabel('月份');

%% ===== Figure 3: 室内温度控制效果 =====
figure('Name','Temperature Control','Position',[100 100 1400 600]);

subplot(2,1,1);
plot(hours, d_best.indoor_temp_C, 'b-', 'LineWidth', 0.5);
hold on;
yline(18, 'r--', '下限 18°C', 'LineWidth', 1);
yline(27, 'r--', '上限 27°C', 'LineWidth', 1);
fill([1 8760 8760 1], [18 18 27 27], 'g', 'FaceAlpha', 0.1, 'EdgeColor', 'none');
ylabel('室内温度 (°C)'); title(sprintf('seed02-best - 室内温度 (越限 %.1f%%)', ...
    sum(d_best.indoor_temp_C < 18 | d_best.indoor_temp_C > 27)/8760*100));
xlim([1 8760]); ylim([15 38]); grid on;
xticks(month_starts); xticklabels(months_str);

subplot(2,1,2);
plot(hours, d_safe.indoor_temp_C, 'Color', [0 0.6 0], 'LineWidth', 0.5);
hold on;
yline(18, 'r--', '下限 18°C', 'LineWidth', 1);
yline(27, 'r--', '上限 27°C', 'LineWidth', 1);
fill([1 8760 8760 1], [18 18 27 27], 'g', 'FaceAlpha', 0.1, 'EdgeColor', 'none');
ylabel('室内温度 (°C)'); title(sprintf('seed03-latest - 室内温度 (越限 %.1f%%)', ...
    sum(d_safe.indoor_temp_C < 18 | d_safe.indoor_temp_C > 27)/8760*100));
xlim([1 8760]); ylim([15 38]); grid on;
xticks(month_starts); xticklabels(months_str);
xlabel('月份');

%% ===== Figure 4: HVAC 控制变量 =====
figure('Name','HVAC Controls','Position',[100 100 1400 800]);

subplot(4,1,1);
plot(hours, d_best.fan_flow_kgs, 'b-', 'LineWidth', 0.5);
ylabel('风量 (kg/s)'); title('CRAH 风机流量');
xlim([1 8760]); grid on;
xticks(month_starts); xticklabels(months_str);

subplot(4,1,2);
plot(hours, d_best.crah_supply_C, 'b-', 'LineWidth', 0.5);
hold on;
plot(hours, d_best.crah_return_C, 'r-', 'LineWidth', 0.5);
ylabel('温度 (°C)'); title('CRAH 送风/回风温度');
legend('送风', '回风'); xlim([1 8760]); grid on;
xticks(month_starts); xticklabels(months_str);

subplot(4,1,3);
plot(hours, d_best.chiller_t_C, 'b-', 'LineWidth', 0.5);
ylabel('温度 (°C)'); title('冷机出水温度设定');
xlim([1 8760]); grid on;
xticks(month_starts); xticklabels(months_str);

subplot(4,1,4);
plot(hours, d_best.ct_pump_kgs, 'b-', 'LineWidth', 0.5);
ylabel('流量 (kg/s)'); title('冷凝水泵流量');
xlim([1 8760]); grid on;
xticks(month_starts); xticklabels(months_str);
xlabel('月份');

%% ===== Figure 5: 月度 PUE 柱状图 (8 模型对比) =====
figure('Name','Monthly PUE Comparison','Position',[100 100 1200 500]);

monthly_pue = zeros(12, length(allData));
for i = 1:length(allData)
    d = allData{i};
    for m = 1:12
        mask = d.month == m;
        elec_sum = sum(d.power_facility_kW(mask));
        ite_sum = sum(d.power_ite_kW(mask));
        if ite_sum > 0
            monthly_pue(m, i) = elec_sum / ite_sum;
        end
    end
end

% 只画 best checkpoints (1,3,5,7) vs latest (2,4,6,8)
bar(1:12, monthly_pue(:, [3, 6]), 'grouped');  % seed02-best vs seed03-latest
legend('seed02-best (PUE=1.282)', 'seed03-latest (PUE=1.293)');
xlabel('月份'); ylabel('PUE');
title('月度 PUE 对比 - 推荐模型');
xticks(1:12); xticklabels(months_str);
ylim([1.1 1.45]); grid on;

%% ===== Figure 6: 4 seed 年度指标对比 =====
figure('Name','Seed Comparison','Position',[100 100 1000 600]);

seed_labels = categorical({'seed01','seed02','seed03','seed04'});
seed_labels = reordercats(seed_labels, {'seed01','seed02','seed03','seed04'});

% 年度 PUE
annual_pue_best = zeros(4,1);
annual_pue_latest = zeros(4,1);
comfort_viol_best = zeros(4,1);
comfort_viol_latest = zeros(4,1);
for i = 1:4
    d_b = allData{2*i-1};  % best
    d_l = allData{2*i};    % latest
    annual_pue_best(i) = sum(d_b.power_facility_kW) / sum(d_b.power_ite_kW);
    annual_pue_latest(i) = sum(d_l.power_facility_kW) / sum(d_l.power_ite_kW);
    comfort_viol_best(i) = sum(d_b.indoor_temp_C < 18 | d_b.indoor_temp_C > 27) / N * 100;
    comfort_viol_latest(i) = sum(d_l.indoor_temp_C < 18 | d_l.indoor_temp_C > 27) / N * 100;
end

subplot(2,1,1);
bar(seed_labels, [annual_pue_best, annual_pue_latest]);
ylabel('PUE'); title('年度 PUE (4 seed × best/latest)');
legend('Best Checkpoint', 'Latest Checkpoint');
ylim([1.2 1.4]); grid on;

subplot(2,1,2);
bar(seed_labels, [comfort_viol_best, comfort_viol_latest]);
ylabel('越限比例 (%)'); title('温度越限比例 (4 seed × best/latest)');
legend('Best Checkpoint', 'Latest Checkpoint');
grid on;

%% ===== Figure 7: 典型日 24h 调度曲线 (夏季 / 冬季) =====
figure('Name','Typical Day Profiles','Position',[100 100 1400 800]);

% 夏季典型日: 7月15日 (hour 4681-4704)
summer_start = 4681;
summer_end = 4704;
% 冬季典型日: 1月15日 (hour 337-360)
winter_start = 337;
winter_end = 360;

h24 = 1:24;

subplot(2,3,1);
plot(h24, d_best.outdoor_temp_C(summer_start:summer_end), 'r-o', 'LineWidth', 1.5);
hold on;
plot(h24, d_best.indoor_temp_C(summer_start:summer_end), 'b-s', 'LineWidth', 1.5);
yline(27, 'r--'); yline(18, 'r--');
xlabel('时刻 (h)'); ylabel('温度 (°C)'); title('夏季日 (7/15) - 温度');
legend('室外','室内','Location','best'); grid on;

subplot(2,3,2);
yyaxis left;
plot(h24, d_best.power_facility_kW(summer_start:summer_end), 'b-o', 'LineWidth', 1.5);
ylabel('总功率 (kW)');
yyaxis right;
plot(h24, d_best.pue(summer_start:summer_end), 'r-s', 'LineWidth', 1.5);
ylabel('PUE');
xlabel('时刻 (h)'); title('夏季日 - 功率与PUE'); grid on;

subplot(2,3,3);
plot(h24, d_best.fan_flow_kgs(summer_start:summer_end), 'b-o', 'LineWidth', 1.2);
hold on;
plot(h24, d_best.ct_pump_kgs(summer_start:summer_end), 'r-s', 'LineWidth', 1.2);
xlabel('时刻 (h)'); ylabel('流量 (kg/s)'); title('夏季日 - 风机与泵');
legend('CRAH风机','冷凝水泵'); grid on;

subplot(2,3,4);
plot(h24, d_best.outdoor_temp_C(winter_start:winter_end), 'r-o', 'LineWidth', 1.5);
hold on;
plot(h24, d_best.indoor_temp_C(winter_start:winter_end), 'b-s', 'LineWidth', 1.5);
yline(27, 'r--'); yline(18, 'r--');
xlabel('时刻 (h)'); ylabel('温度 (°C)'); title('冬季日 (1/15) - 温度');
legend('室外','室内','Location','best'); grid on;

subplot(2,3,5);
yyaxis left;
plot(h24, d_best.power_facility_kW(winter_start:winter_end), 'b-o', 'LineWidth', 1.5);
ylabel('总功率 (kW)');
yyaxis right;
plot(h24, d_best.pue(winter_start:winter_end), 'r-s', 'LineWidth', 1.5);
ylabel('PUE');
xlabel('时刻 (h)'); title('冬季日 - 功率与PUE'); grid on;

subplot(2,3,6);
plot(h24, d_best.fan_flow_kgs(winter_start:winter_end), 'b-o', 'LineWidth', 1.2);
hold on;
plot(h24, d_best.ct_pump_kgs(winter_start:winter_end), 'r-s', 'LineWidth', 1.2);
xlabel('时刻 (h)'); ylabel('流量 (kg/s)'); title('冬季日 - 风机与泵');
legend('CRAH风机','冷凝水泵'); grid on;

%% ===== Figure 8: Reward 分布 =====
figure('Name','Reward Distribution','Position',[100 100 800 400]);
rewards_all = zeros(N, length(allData));
for i = 1:length(allData)
    rewards_all(:, i) = allData{i}.reward(1:N);
end
boxplot(rewards_all, 'Labels', labels);
ylabel('Hourly Reward'); title('8 模型逐时 Reward 分布');
grid on;
xtickangle(30);

%% ===== 打印汇总信息 =====
fprintf('\n============================================================\n');
fprintf('  E0 南京基线评估结果汇总\n');
fprintf('============================================================\n');
fprintf('模型              年PUE   电力MWh   冷却MWh   越限%%  \n');
fprintf('------------------------------------------------------------\n');
for i = 1:length(allData)
    d = allData{i};
    elec = sum(d.power_facility_kW) / 1000;
    ite = sum(d.power_ite_kW) / 1000;
    cool = elec - ite;
    pue = elec / ite;
    viol = sum(d.indoor_temp_C < 18 | d.indoor_temp_C > 27) / N * 100;
    fprintf('%-17s %.3f  %8.0f  %8.0f  %5.1f%%\n', labels{i}, pue, elec, cool, viol);
end
fprintf('============================================================\n');

fprintf('\n所有图表已生成，可交互缩放查看。\n');
fprintf('推荐 E0 基线: seed02-best (PUE=1.282) 或 seed03-latest (PUE=1.293)\n');
