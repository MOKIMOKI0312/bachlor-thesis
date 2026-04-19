import json
import os

import gymnasium as gym
from gymnasium.envs.registration import WrapperSpec, register, registry

from sinergym.utils.common import convert_conf_to_env_parameters
from sinergym.utils.constants import *
from sinergym.utils.rewards import *

# ------------------------- Set __version__ in module ------------------------ #
version_file = os.path.join(os.path.dirname(__file__), 'version.txt')
with open(version_file, 'r') as file_handler:
    __version__ = file_handler.read().strip()


def _register_if_missing(env_id: str, **kwargs) -> None:
    if env_id in registry:
        return
    register(id=env_id, **kwargs)

# ---------------------------- Data Center environment --------------------------- #
_register_if_missing(
    'Eplus-DC-Cooling',
    entry_point='sinergym.envs:EplusEnv',
    kwargs={
        'building_file': 'DRL_DC_evaluation.epJSON',
        'weather_files': 'AUS_NSW_Sydney.Intl.AP.947670_TMYx.2009-2023.epw',
        'action_space': gym.spaces.Box(
            low=np.array([0,0,0,0,0], dtype=np.float32),
            high=np.array([1,1,1,1,1], dtype=np.float32),
            shape=(5,),
            dtype=np.float32),
        'time_variables': ['month', 'day_of_month', 'hour'],
        'variables': {
            'outdoor_temperature': (
                'Site Outdoor Air DryBulb Temperature',
                'Environment'),
            'outdoor_wet_temperature': (
                'Site Outdoor Air WetBulb Temperature',
                'Environment'),
            'air_temperature': (
                'Zone Air Temperature',
                'DataCenter ZN'),
            'air_humidity': (
                'Zone Air Relative Humidity',
                'DataCenter ZN'),
            'CT_temperature': (
                'System Node Temperature',
                'Condenser Water Loop Supply Outlet Node'),
            'CW_temperature': (
                'System Node Temperature',
                '90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton Supply Outlet Water Node'),
            'CRAH_temperature_1': (
                'System Node Temperature',
                'CRAH Supply Outlet Node'),
            'CRAH_temperature_2': (
                'System Node Temperature',
                'CRAH Supply Inlet Node'),
            'act_Fan': (
                'Fan Air Mass Flow Rate',
                'CRAH FAN'),
            'act_Chiller_T': (
                'Schedule Value',
                'Chilled Water Loop Temp - 44F'),
            'act_Chiller_Pump': (
                'Pump Mass Flow Rate',
                'Chilled Water Loop Secondary Pump'),
            'act_CT_Pump': (
                'Pump Mass Flow Rate',
                'CONDENSER WATER LOOP CONSTANT PUMP'),
            'act_ITE': (
                'Schedule Value',
                'DataCenter Equipment_SCH')
        },
        "meters": {
            "Electricity:Facility": "Electricity:Facility",
            "ITE-CPU:InteriorEquipment:Electricity": "ITE-CPU:InteriorEquipment:Electricity",
            "Water:Facility": "Water:Facility"
        },
        'actuators': {
            'CRAH_Fan_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CRAH_Fan_Set'),
            'CT_Pump_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CT_Pump_Set'),
            'CRAH_T_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CRAH_T_Set'),
            'Chiller_T_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'Chiller_T_Set'),
            'ITE_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'ITE_Set')
        },
        'reward': PUE_Reward,
        'reward_kwargs': {
            'temperature_variables': ['air_temperature'],
            'energy_variables': ["Electricity:Facility"],
            'ITE_variables': ["ITE-CPU:InteriorEquipment:Electricity"],
            'range_comfort_winter': (18.0, 25.0),
            'range_comfort_summer': (18.0, 25.0),
            'energy_weight': 1/2,
            'lambda_energy': 1},
        'env_name': 'DC-DRL',
        'config_params': {
            'runperiod': (1, 1, 2025, 12, 31, 2025),
            'timesteps_per_hour': 1
        },
        'evaluation_flag': 0})

_register_if_missing(
    'Eplus-DC-Cooling-TES',
    entry_point='sinergym.envs:EplusEnv',
    kwargs={
        'building_file': 'DRL_DC_evaluation.epJSON',
        'weather_files': 'AUS_NSW_Sydney.Intl.AP.947670_TMYx.2009-2023.epw',
        'action_space': gym.spaces.Box(
            low=np.array([0, 0, 0, 0, 0, -1], dtype=np.float32),
            high=np.array([1, 1, 1, 1, 1, 1], dtype=np.float32),
            shape=(6,),
            dtype=np.float32),
        'time_variables': ['month', 'day_of_month', 'hour'],
        'variables': {
            'outdoor_temperature': (
                'Site Outdoor Air DryBulb Temperature',
                'Environment'),
            'outdoor_wet_temperature': (
                'Site Outdoor Air WetBulb Temperature',
                'Environment'),
            'air_temperature': (
                'Zone Air Temperature',
                'DataCenter ZN'),
            'air_humidity': (
                'Zone Air Relative Humidity',
                'DataCenter ZN'),
            'CT_temperature': (
                'System Node Temperature',
                'Condenser Water Loop Supply Outlet Node'),
            'CW_temperature': (
                'System Node Temperature',
                '90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton Supply Outlet Water Node'),
            'CRAH_temperature_1': (
                'System Node Temperature',
                'CRAH Supply Outlet Node'),
            'CRAH_temperature_2': (
                'System Node Temperature',
                'CRAH Supply Inlet Node'),
            'act_Fan': (
                'Fan Air Mass Flow Rate',
                'CRAH FAN'),
            'act_Chiller_T': (
                'Schedule Value',
                'Chilled Water Loop Temp - 44F'),
            'act_Chiller_Pump': (
                'Pump Mass Flow Rate',
                'Chilled Water Loop Secondary Pump'),
            'act_CT_Pump': (
                'Pump Mass Flow Rate',
                'CONDENSER WATER LOOP CONSTANT PUMP'),
            'act_ITE': (
                'Schedule Value',
                'DataCenter Equipment_SCH'),
            'TES_SOC': (
                'Schedule Value',
                'TES_SOC_Obs'),
            'TES_avg_temp': (
                'Schedule Value',
                'TES_Avg_Temp_Obs'),
        },
        "meters": {
            "Electricity:Facility": "Electricity:Facility",
            "ITE-CPU:InteriorEquipment:Electricity": "ITE-CPU:InteriorEquipment:Electricity",
            "Water:Facility": "Water:Facility"
        },
        'actuators': {
            'CRAH_Fan_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CRAH_Fan_Set'),
            'CT_Pump_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CT_Pump_Set'),
            'CRAH_T_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CRAH_T_Set'),
            'Chiller_T_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'Chiller_T_Set'),
            'ITE_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'ITE_Set'),
            'TES_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'TES_Set'),
        },
        'reward': PUE_TES_Reward,
        'reward_kwargs': {
            'temperature_variables': ['air_temperature'],
            'energy_variables': ["Electricity:Facility"],
            'ITE_variables': ["ITE-CPU:InteriorEquipment:Electricity"],
            'range_comfort_winter': (18.0, 25.0),
            'range_comfort_summer': (18.0, 25.0),
            'energy_weight': 1/2,
            'lambda_energy': 1,
            'lambda_temperature': 3.0,
            'soc_variable': 'TES_SOC',
            'soc_low': 0.15,
            'soc_high': 0.85,
            'soc_warn_low': 0.30,
            'soc_warn_high': 0.70,
            'lambda_soc': 5.0,
            'lambda_soc_warn': 3.0,
        },
        'env_name': 'DC-DRL-TES',
        'config_params': {
            'runperiod': (1, 1, 2025, 31, 12, 2025),
            'timesteps_per_hour': 1
        },
        'evaluation_flag': 0})

_register_if_missing(
    'Eplus-DC-Grid',
    entry_point='sinergym.envs:EplusEnv',
    kwargs={
        'building_file': 'DRL_DC.epJSON',
        'weather_files': 'USA_PA_Pittsburgh-Allegheny.County.AP.725205_TMY3.epw',
        'action_space': gym.spaces.Box(
            low=np.array([0,0,0,0,0,0,-1,0], dtype=np.float32),
            high=np.array([1,1,1,1,1,1,1,1], dtype=np.float32),
            shape=(8,),
            dtype=np.float32),
        'time_variables': ['month', 'day_of_month', 'hour'],
        'variables': {
            'outdoor_wind': (
                'Site Wind Speed',
                'Environment'),
            'outdoor_temperature': (
                'Site Outdoor Air DryBulb Temperature',
                'Environment'),
            'outdoor_wet_temperature': (
                'Site Outdoor Air WetBulb Temperature',
                'Environment'),
            'outdoor_Diffuse': (
                'Site Diffuse Solar Radiation Rate per Area',
                'Environment'),
            'outdoor_Direct': (
                'Site Direct Solar Radiation Rate per Area',
                'Environment'),
            'air_temperature': (
                'Zone Air Temperature',
                'DataCenter ZN'),
            'air_humidity': (
                'Zone Air Relative Humidity',
                'DataCenter ZN'),
            'CT_temperature': (
                'System Node Temperature',
                'Condenser Water Loop Supply Outlet Node'),
            'CW_temperature': (
                'System Node Temperature',
                '90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton Supply Outlet Water Node'),
            'CRAH_temperature_1': (
                'System Node Temperature',
                'CRAH Supply Outlet Node'),
            'CRAH_temperature_2': (
                'System Node Temperature',
                'CRAH Supply Inlet Node'),
            'act_Fan': (
                'Fan Air Mass Flow Rate',
                'CRAH FAN'),
            'act_Chiller_T': (
                'Schedule Value',
                'Chilled Water Loop Temp - 44F'),
            'act_Chiller_Pump': (
                'Pump Mass Flow Rate',
                'Chilled Water Loop Secondary Pump'),
            'act_CT_Pump': (
                'Pump Mass Flow Rate',
                'CONDENSER WATER LOOP CONSTANT PUMP'),
            'SoC': (
                'Electric Storage Battery Charge State',
                'LiIonBattery'),
            'SoC_V': (
                'Electric Storage Total Voltage',
                'LiIonBattery'),
            'act_Charge': (
                'Electric Storage Charge Power',
                'LiIonBattery'),
            'act_Discharge': (
                'Electric Storage Discharge Power',
                'LiIonBattery'),
            'act_ITE': (
                'Schedule Value',
                'DataCenter Equipment_SCH'),
            'grid_CF': (
                'Schedule Value',
                'grid_CF'),
            'grid_price': (
                'Schedule Value',
                'grid_price'),
            'grid_CF_flag': (
                'Schedule Value',
                'grid_CF'),
            'grid_price_flag': (
                'Schedule Value',
                'grid_price')
        },
         "meters": {
             "Electricity:Facility" : "Electricity:Facility",
             "WindTurbine:ElectricityProduced": "WindTurbine:ElectricityProduced",
             "Photovoltaic:ElectricityProduced": "Photovoltaic:ElectricityProduced",
             "ITE-CPU:InteriorEquipment:Electricity": "ITE-CPU:InteriorEquipment:Electricity",
             "Pumps:Electricity": "Pumps:Electricity",
             "Fans:Electricity": "Fans:Electricity",
             "Water:Facility" : "Water:Facility",
             "ElectricStorage:ElectricityProduced": "ElectricStorage:ElectricityProduced",
             "ElectricityPurchased:Facility": "ElectricityPurchased:Facility"
            },
        'actuators': {
            'CRAH_Fan_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CRAH_Fan_Set'),
            'Chiller_Pump_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'Chiller_Pump_Set'),
            'CT_Pump_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CT_Pump_Set'),
            'CRAH_T_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'CRAH_T_Set'),
            'Chiller_T_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'Chiller_T_Set'),
            'ITE_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'ITE_Set'),
            'Charge_Def_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'Charge_Def_Set'),
            'Charge_DRL': (
                'Schedule:Constant',
                'Schedule Value',
                'Charge_Set')
        },
        'reward': Grid_Reward,
        'reward_kwargs': {
            'temperature_variables': ['air_temperature'],
            'energy_variables': ["ElectricityPurchased:Facility"],
            'carbon_variables': ['grid_price'],
            'ITE_variables': ["ITE-CPU:InteriorEquipment:Electricity"],
            'range_comfort_winter': (18.0, 27.0),
            'range_comfort_summer': (18.0, 27.0),
            'energy_weight': 1/3,
            'ITE_weight': 1/3,
            'lambda_energy': 30,
            'lambda_ITE': 0},
        'env_name': 'DC-DRL',
        'grid_flag': 1,
        'config_params': {
            'runperiod': (1, 1, 2025, 12, 31, 2025),
            'timesteps_per_hour': 1
        },
        'evaluation_flag': 0})

# ------------------- Read environment configuration files ------------------- #
conf_files = []
configuration_path = os.path.join(
    os.path.dirname(__file__),
    'data/default_configuration')
for root, dirs, files in os.walk(configuration_path):
    for file in files:
        # Obtain the whole path for each configuration file
        file_path = os.path.join(root, file)
        conf_files.append(file_path)

# ---------------- For each conf file, setting up environments --------------- #
for conf_file in conf_files:
    with open(conf_file) as json_f:
        conf = json.load(json_f)

    # configurations = Dict [key=environment_id, value=env_kwargs dict]
    configurations = convert_conf_to_env_parameters(conf)

    for env_id, env_kwargs in configurations.items():

        if not conf.get('only_discrete', False):

            _register_if_missing(
                env_id,
                entry_point='sinergym.envs:EplusEnv',
                # additional_wrappers=additional_wrappers,
                # order_enforce=False,
                # disable_env_checker=True,
                kwargs=env_kwargs
            )

        # If discrete space is included, add the same environment with
        # discretization
        if conf.get('action_space_discrete'):
            # Copy the dictionary since is used by reference
            env_kwargs_discrete = env_kwargs.copy()

            # Action mapping must be included in constants.
            action_mapping = eval(
                "DEFAULT_" +
                conf["id_base"].upper() +
                "_DISCRETE_FUNCTION")

            discrete_wrapper_spec = WrapperSpec(
                name='DiscretizeEnv',
                entry_point='sinergym.utils.wrappers:DiscretizeEnv',
                kwargs={
                    'discrete_space': eval(conf['action_space_discrete']),
                    'action_mapping': action_mapping})
            additional_wrappers = (discrete_wrapper_spec,)

            env_kwargs_discrete['env_name'] = env_kwargs_discrete['env_name'].replace(
                'continuous', 'discrete')

            _register_if_missing(
                env_id.replace('continuous', 'discrete'),
                entry_point='sinergym.envs:EplusEnv',
                additional_wrappers=additional_wrappers,
                # order_enforce=False,
                # disable_env_checker=True,
                kwargs=env_kwargs_discrete
            )
