# 数据来源说明

## 气象数据 (EPW Weather Files)

**数据来源**: climate.onebuilding.org (TMYx Typical Meteorological Year data, 2009-2023)
**下载日期**: 2026-04-01

### 1. 南京 (Nanjing)

- **WMO站号**: 582380
- **坐标**: 31.9316°N, 118.8996°E, 海拔 14.9m
- **时区**: UTC+8
- **下载URL**: https://climate.onebuilding.org/WMO_Region_2_Asia/CHN_China/JS_Jiangsu/CHN_JS_Nanjing.582380_TMYx.2009-2023.zip

| 文件 | 大小 | 说明 |
|------|------|------|
| CHN_JS_Nanjing.582380_TMYx.2009-2023.epw | 1.53 MB | EnergyPlus气象数据文件 |
| CHN_JS_Nanjing.582380_TMYx.2009-2023.ddy | 176 KB | 设计日数据 (Sinergym必需) |
| CHN_JS_Nanjing.582380_TMYx.2009-2023.stat | 62 KB | 气候统计数据 (Sinergym必需) |
| CHN_JS_Nanjing.582380_TMYx.2009-2023.clm | 186 KB | DesignBuilder气候文件 |
| CHN_JS_Nanjing.582380_TMYx.2009-2023.pvsyst | 346 KB | PVsyst太阳能仿真文件 |
| CHN_JS_Nanjing.582380_TMYx.2009-2023.rain | 145 KB | 降雨数据 |
| CHN_JS_Nanjing.582380_TMYx.2009-2023.wea | 138 KB | Radiance/Daysim气象文件 |

### 2. 徐州 (Xuzhou)

- **WMO站号**: 580270
- **坐标**: 34.2871°N, 117.1587°E, 海拔 42.0m
- **时区**: UTC+8
- **下载URL**: https://climate.onebuilding.org/WMO_Region_2_Asia/CHN_China/JS_Jiangsu/CHN_JS_Xuzhou.580270_TMYx.2009-2023.zip

| 文件 | 大小 | 说明 |
|------|------|------|
| CHN_JS_Xuzhou.580270_TMYx.2009-2023.epw | 1.53 MB | EnergyPlus气象数据文件 |
| CHN_JS_Xuzhou.580270_TMYx.2009-2023.ddy | 175 KB | 设计日数据 (Sinergym必需) |
| CHN_JS_Xuzhou.580270_TMYx.2009-2023.stat | 62 KB | 气候统计数据 (Sinergym必需) |
| CHN_JS_Xuzhou.580270_TMYx.2009-2023.clm | 186 KB | DesignBuilder气候文件 |
| CHN_JS_Xuzhou.580270_TMYx.2009-2023.pvsyst | 347 KB | PVsyst太阳能仿真文件 |
| CHN_JS_Xuzhou.580270_TMYx.2009-2023.rain | 145 KB | 降雨数据 |
| CHN_JS_Xuzhou.580270_TMYx.2009-2023.wea | 138 KB | Radiance/Daysim气象文件 |

### 3. 银川 (Yinchuan)

- **WMO站号**: 536140
- **坐标**: 38.4714°N, 106.2078°E, 海拔 1112.0m
- **时区**: UTC+8
- **下载URL**: https://climate.onebuilding.org/WMO_Region_2_Asia/CHN_China/NX_Ningxia_Hui/CHN_NX_Yinchuan.536140_TMYx.2009-2023.zip

| 文件 | 大小 | 说明 |
|------|------|------|
| CHN_NX_Yinchuan.536140_TMYx.2009-2023.epw | 1.53 MB | EnergyPlus气象数据文件 |
| CHN_NX_Yinchuan.536140_TMYx.2009-2023.ddy | 176 KB | 设计日数据 (Sinergym必需) |
| CHN_NX_Yinchuan.536140_TMYx.2009-2023.stat | 62 KB | 气候统计数据 (Sinergym必需) |
| CHN_NX_Yinchuan.536140_TMYx.2009-2023.clm | 187 KB | DesignBuilder气候文件 |
| CHN_NX_Yinchuan.536140_TMYx.2009-2023.pvsyst | 349 KB | PVsyst太阳能仿真文件 |
| CHN_NX_Yinchuan.536140_TMYx.2009-2023.rain | 145 KB | 降雨数据 |
| CHN_NX_Yinchuan.536140_TMYx.2009-2023.wea | 139 KB | Radiance/Daysim气象文件 |

## 气候特征对比

| 城市 | 纬度 | 海拔(m) | 冬季设计温度(°C) | 夏季设计温度(°C) | 气候类型 |
|------|------|---------|------------------|------------------|----------|
| 南京 | 31.93°N | 14.9 | -4.9 | 36.4 | 亚热带季风 |
| 徐州 | 34.29°N | 42.0 | -6.3 | 35.3 | 温带季风 |
| 银川 | 38.47°N | 1112.0 | -16.0 | 33.2 | 温带大陆性 |

## 注意事项

- TMYx数据基于2009-2023年实测气象站数据生成的典型气象年
- Sinergym运行时需要 `.epw`、`.ddy`、`.stat` 三个文件
- 数据使用ASHRAE 2025 Handbook设计条件
