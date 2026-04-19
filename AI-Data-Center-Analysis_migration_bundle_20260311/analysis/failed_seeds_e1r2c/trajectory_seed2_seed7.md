# E1-R2c Failed Seed Trajectory Record
# Generated: 2026-04-18T11:26:54.571919
# Reason: seed2 and seed7 diverged (ent_coef persistently > 1.0, actor_loss ~-1000 to -1600)
# Both were killed manually to free CPU for the 6 healthy seeds.

## seed2
- final ep (at kill): 138
- final elapsed: 9.73h (since resume from ep 50)
- total log entries: ent_coef=88, reward=88, actor=88

### ent_coef trajectory (all 88 logs)
  log#  1: 0.0773
  log#  2: 0.0769
  log#  3: 0.0761
  log#  4: 0.0749
  log#  5: 0.0737
  log#  6: 0.0767
  log#  7: 0.1020
  log#  8: 0.1690
  log#  9: 0.2680
  log# 10: 0.4060
  log# 11: 0.5610 <-- crossed 0.5
  log# 12: 0.5990
  log# 13: 0.5970
  log# 14: 0.6180
  log# 15: 0.6440
  log# 16: 0.6420
  log# 17: 0.4950
  log# 18: 0.4860
  log# 19: 0.5660 <-- crossed 0.5
  log# 20: 0.6080
  log# 21: 0.6090
  log# 22: 0.6450
  log# 23: 0.5930
  log# 24: 0.6230
  log# 25: 0.7190
  log# 26: 0.7290
  log# 27: 0.7060
  log# 28: 0.6790
  log# 29: 0.7820
  log# 30: 0.8880
  log# 31: 0.9480
  log# 32: 1.0000
  log# 33: 1.2600 <-- crossed 1.0
  log# 34: 1.1900
  log# 35: 1.0300
  log# 36: 0.9750
  log# 37: 0.9060
  log# 38: 0.8930
  log# 39: 0.9050
  log# 40: 0.9380
  log# 41: 1.0100 <-- crossed 1.0
  log# 42: 1.0500
  log# 43: 1.0700
  log# 44: 1.1000
  log# 45: 1.0600
  log# 46: 1.1000
  log# 47: 1.0500
  log# 48: 1.0200
  log# 49: 1.0400
  log# 50: 0.9370
  log# 51: 0.9390
  log# 52: 0.9280
  log# 53: 0.9540
  log# 54: 0.9390
  log# 55: 1.0000
  log# 56: 0.9920
  log# 57: 0.9750
  log# 58: 0.9350
  log# 59: 0.9830
  log# 60: 0.9280
  log# 61: 0.9410
  log# 62: 1.0200 <-- crossed 1.0
  log# 63: 1.0200
  log# 64: 1.0000
  log# 65: 1.0600 <-- crossed 1.0
  log# 66: 1.0600
  log# 67: 1.0300
  log# 68: 1.1800
  log# 69: 0.9720
  log# 70: 1.0500 <-- crossed 1.0
  log# 71: 1.0800
  log# 72: 1.0200
  log# 73: 1.0000
  log# 74: 1.0600 <-- crossed 1.0
  log# 75: 1.0900
  log# 76: 1.1100
  log# 77: 1.0900
  log# 78: 1.0200
  log# 79: 0.9860
  log# 80: 1.0500 <-- crossed 1.0
  log# 81: 0.9740
  log# 82: 0.9650
  log# 83: 0.9270
  log# 84: 0.8790
  log# 85: 0.7920
  log# 86: 0.6970
  log# 87: 0.6340
  log# 88: 0.5560

### actor_loss trajectory (every 2nd log)
  log#  1: +239.00
  log#  3: +247.00
  log#  5: +243.00
  log#  7: +206.00
  log#  9: +19.90
  log# 11: -217.00
  log# 13: -445.00
  log# 15: -683.00
  log# 17: -823.00
  log# 19: -790.00
  log# 21: -727.00
  log# 23: -756.00
  log# 25: -846.00
  log# 27: -954.00
  log# 29: -1040.00
  log# 31: -1120.00
  log# 33: -1170.00
  log# 35: -1230.00
  log# 37: -1220.00
  log# 39: -1180.00
  log# 41: -1190.00
  log# 43: -1200.00
  log# 45: -1220.00
  log# 47: -1220.00
  log# 49: -1210.00
  log# 51: -1200.00
  log# 53: -1190.00
  log# 55: -1160.00
  log# 57: -1180.00
  log# 59: -1170.00
  log# 61: -1130.00
  log# 63: -1110.00
  log# 65: -1110.00
  log# 67: -1090.00
  log# 69: -1080.00
  log# 71: -1070.00
  log# 73: -1060.00
  log# 75: -1000.00
  log# 77: -989.00
  log# 79: -954.00
  log# 81: -901.00
  log# 83: -849.00
  log# 85: -755.00
  log# 87: -622.00

### ep_rew_mean trajectory (every 3rd log)
  log#  1: -3.990e+04
  log#  4: -4.040e+04
  log#  7: -4.080e+04
  log# 10: -4.140e+04
  log# 13: -4.170e+04
  log# 16: -4.280e+04
  log# 19: -4.370e+04
  log# 22: -4.440e+04
  log# 25: -4.480e+04
  log# 28: -4.440e+04
  log# 31: -4.410e+04
  log# 34: -4.420e+04
  log# 37: -4.420e+04
  log# 40: -4.420e+04
  log# 43: -4.410e+04
  log# 46: -4.410e+04
  log# 49: -4.400e+04
  log# 52: -4.390e+04
  log# 55: -4.400e+04
  log# 58: -4.380e+04
  log# 61: -4.380e+04
  log# 64: -4.380e+04
  log# 67: -4.360e+04
  log# 70: -4.300e+04
  log# 73: -4.280e+04
  log# 76: -4.290e+04
  log# 79: -4.300e+04
  log# 82: -4.310e+04
  log# 85: -4.330e+04
  log# 88: -4.360e+04

## seed7
- final ep (at kill): 118
- final elapsed: 9.71h (since resume from ep 50)
- total log entries: ent_coef=67, reward=67, actor=67

### ent_coef trajectory (all 67 logs)
  log#  1: 0.0487
  log#  2: 0.0452
  log#  3: 0.0404
  log#  4: 0.0416
  log#  5: 0.0404
  log#  6: 0.0407
  log#  7: 0.0405
  log#  8: 0.0400
  log#  9: 0.0406
  log# 10: 0.0386
  log# 11: 0.0391
  log# 12: 0.0411
  log# 13: 0.0426
  log# 14: 0.0391
  log# 15: 0.0425
  log# 16: 0.0454
  log# 17: 0.0506
  log# 18: 0.0453
  log# 19: 0.0472
  log# 20: 0.0484
  log# 21: 0.0557
  log# 22: 0.0525
  log# 23: 0.0561
  log# 24: 0.0576
  log# 25: 0.0828
  log# 26: 0.1370
  log# 27: 0.2030
  log# 28: 0.2610
  log# 29: 0.2710
  log# 30: 0.3220
  log# 31: 0.4310
  log# 32: 0.4830
  log# 33: 0.5080 <-- crossed 0.5
  log# 34: 0.5510
  log# 35: 0.6210
  log# 36: 0.7720
  log# 37: 0.9830
  log# 38: 1.2600 <-- crossed 1.0
  log# 39: 1.4400
  log# 40: 1.5200
  log# 41: 1.5700
  log# 42: 1.7600
  log# 43: 1.6400
  log# 44: 1.4200
  log# 45: 1.3000
  log# 46: 1.2400
  log# 47: 1.2700
  log# 48: 1.2700
  log# 49: 1.4100
  log# 50: 1.4800
  log# 51: 1.5400
  log# 52: 1.5000
  log# 53: 1.6200
  log# 54: 1.6000
  log# 55: 1.4600
  log# 56: 1.3600
  log# 57: 1.3700
  log# 58: 1.4700
  log# 59: 1.3600
  log# 60: 1.2800
  log# 61: 1.2200
  log# 62: 1.2500
  log# 63: 1.3100
  log# 64: 1.1000
  log# 65: 1.2800
  log# 66: 1.3000
  log# 67: 1.2400

### actor_loss trajectory (every 2nd log)
  log#  1: +193.00
  log#  3: +195.00
  log#  5: +192.00
  log#  7: +202.00
  log#  9: +210.00
  log# 11: +216.00
  log# 13: +230.00
  log# 15: +228.00
  log# 17: +233.00
  log# 19: +239.00
  log# 21: +230.00
  log# 23: +233.00
  log# 25: +207.00
  log# 27: +115.00
  log# 29: +15.90
  log# 31: -105.00
  log# 33: -214.00
  log# 35: -334.00
  log# 37: -554.00
  log# 39: -860.00
  log# 41: -1130.00
  log# 43: -1340.00
  log# 45: -1430.00
  log# 47: -1430.00
  log# 49: -1440.00
  log# 51: -1520.00
  log# 53: -1580.00
  log# 55: -1630.00
  log# 57: -1630.00
  log# 59: -1630.00
  log# 61: -1610.00
  log# 63: -1590.00
  log# 65: -1520.00
  log# 67: -1490.00

### ep_rew_mean trajectory (every 3rd log)
  log#  1: -3.390e+04
  log#  4: -3.420e+04
  log#  7: -3.440e+04
  log# 10: -3.500e+04
  log# 13: -3.510e+04
  log# 16: -3.500e+04
  log# 19: -3.540e+04
  log# 22: -3.580e+04
  log# 25: -3.610e+04
  log# 28: -3.620e+04
  log# 31: -3.670e+04
  log# 34: -3.660e+04
  log# 37: -3.690e+04
  log# 40: -3.690e+04
  log# 43: -3.690e+04
  log# 46: -3.690e+04
  log# 49: -3.720e+04
  log# 52: -3.720e+04
  log# 55: -3.740e+04
  log# 58: -3.700e+04
  log# 61: -3.670e+04
  log# 64: -3.660e+04
  log# 67: -3.650e+04
