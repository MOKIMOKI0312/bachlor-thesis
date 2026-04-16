import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import gymnasium as gym
import numpy as np
from stable_baselines3 import SAC

from sinergym.utils.common import get_ids
from sinergym.utils.logger import CSVLogger
from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation

class CustomCSVLogger(CSVLogger):
    def __init__(self, monitor_header: str, progress_header: str, log_progress_file: str, log_file: Optional[str] = None, flag: bool = True):
        super().__init__(monitor_header, progress_header, log_progress_file, log_file, flag)
        self.last_10_steps_reward = [0] * 10
    def _create_row_content(self, obs: List[Any], action: Union[int, np.ndarray, List[Any]], terminated: bool, truncated: bool, info: Optional[Dict[str, Any]]) -> List:
        if info.get('reward') is not None:
            self.last_10_steps_reward.pop(0)
            self.last_10_steps_reward.append(info['reward'])
        return [info.get('timestep', 0), *list(obs), *list(action), info.get('time_elapsed(hours)', 0), info.get('reward', None), info.get('energy_term'), info.get('comfort_term'), terminated, truncated]


def main() -> None:
    if 'Eplus-DC-Cooling' not in get_ids():
        raise RuntimeError('Eplus-DC-Cooling is not registered')
    experiment_name = datetime.today().strftime('%Y-%m-%d_%H-%M-%S') + '_codex_one_episode_probe'
    env = gym.make('Eplus-DC-Cooling', env_name=experiment_name, building_file=['DRL_DC_training.epJSON'], weather_files=[
        'AUS_NSW_Sydney.Intl.AP.947670_TMYx.2009-2023.epw','DEU_HE_Frankfurt.AP.106370_TMYx.2009-2023.epw','SGP_SG_Singapore-Changi.Intl.AP.486980_TMYx.2009-2023.epw','SWE_NB_Lulea.AP.021860_TMYx.2009-2023.epw','USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw','USA_IA_Des.Moines.Intl.AP.725460_TMYx.2009-2023.epw','USA_NE_Omaha-Eppley.AF.Intl.AP.725500_TMYx.2009-2023.epw','USA_NY_New.York-Kennedy.Intl.AP.744860_TMYx.2009-2023.epw','USA_TX_Dallas-Fort.Worth.Intl.AP.722590_TMYx.2009-2023.epw','USA_VA_Dulles-Washington.Dulles.Intl.AP.724030_TMYx.2009-2023.epw'
    ], config_params={'runperiod': (1,1,2025,31,12,2025), 'timesteps_per_hour': 1})
    env = NormalizeObservation(env)
    env = LoggerWrapper(env, logger_class=CustomCSVLogger, monitor_header=['timestep'] + env.get_wrapper_attr('observation_variables') + env.get_wrapper_attr('action_variables') + ['time (hours)', 'reward', 'energy_term', 'ITE_term', 'comfort_term', 'terminated', 'truncated'])
    model = SAC('MlpPolicy', env, batch_size=512, learning_rate=5e-5, learning_starts=8760, gamma=0.99, policy_kwargs=dict(net_arch=[512]), verbose=0)
    timesteps = env.get_wrapper_attr('timestep_per_episode') - 1
    started = time.perf_counter()
    model.learn(total_timesteps=timesteps, log_interval=500)
    elapsed = time.perf_counter() - started
    workspace_path = Path(env.get_wrapper_attr('workspace_path'))
    env.close()
    print(json.dumps({'timesteps': timesteps, 'elapsed_seconds': elapsed, 'workspace_path': str(workspace_path)}, indent=2))

if __name__ == '__main__':
    main()
