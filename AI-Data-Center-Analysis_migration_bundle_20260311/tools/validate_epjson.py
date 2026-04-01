import json
import sys

for f in ['Data/buildings/DRL_DC_training.epJSON', 'Data/buildings/DRL_DC_evaluation.epJSON']:
    with open(f) as fh:
        data = json.load(fh)
    for cat in ['ElectricLoadCenter:Distribution','ElectricLoadCenter:Generators',
                'ElectricLoadCenter:Inverter:PVWatts','ElectricLoadCenter:Storage:LiIonNMCBattery',
                'Generator:PVWatts','Generator:WindTurbine']:
        assert cat not in data, f'{cat} still in {f}'
    assert 'P_3' not in data.get('EnergyManagementSystem:Program',{})
    assert 'P_4' not in data.get('EnergyManagementSystem:Program',{})
    assert 'Charge_rate' not in data.get('EnergyManagementSystem:Actuator',{})
    assert 'SoC' not in data.get('EnergyManagementSystem:Sensor',{})
    assert 'P_1' in data['EnergyManagementSystem:Program']
    assert 'P_2' in data['EnergyManagementSystem:Program']
    n_act = len(data.get('EnergyManagementSystem:Actuator',{}))
    n_sen = len(data.get('EnergyManagementSystem:Sensor',{}))
    n_prog = len(data.get('EnergyManagementSystem:Program',{}))
    print(f'{f}: PASS (actuators={n_act}, sensors={n_sen}, programs={n_prog})')
print('All validations passed')
