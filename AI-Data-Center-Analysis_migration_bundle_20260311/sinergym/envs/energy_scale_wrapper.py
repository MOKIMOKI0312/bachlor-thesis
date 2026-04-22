"""Scale raw Joule-cumulative energy obs dims to MWh/h.

EnergyPlus Output:Meter reports accumulated Joules per timestep. At 1
step/hour cadence, Electricity:Facility ~ 3e10 J/h ~ 8.6 MWh/h. Without
rescaling, these two dims are 10+ orders of magnitude above other obs
and destabilize NormalizeObservation's RunningMeanStd.

B3 fix (2026-04-23): introduced to address obs 14/15 (1-indexed) mean
values of 3.10e10 / 2.33e10 in mean.txt while all other 39 dims sit in
[-5e-6, 1560]. The NormalizeObservation RunningMeanStd Welford update
loses float32 precision under such extreme dynamic range, producing
non-stationary normalization during training and coinciding with
critic sigma blow-up around ep50-70 in seed5.
"""
import gymnasium as gym
import numpy as np


class EnergyScaleWrapper(gym.ObservationWrapper):
    """Multiply specified obs indices by a constant scale factor.

    Default scale 1/3.6e9 converts Joules/hour to MWh/hour. Wrapper is
    intended to sit between WorkloadWrapper (last semantic wrapper) and
    NormalizeObservation (first statistical wrapper) so the downstream
    RunningMeanStd sees values in the same order of magnitude as the
    other 39 obs dims.

    Args:
        env: wrapped env with 41-dim obs (post WorkloadWrapper).
        energy_indices: 0-indexed positions of Joule-cumulative dims.
            For the §6.1 41-dim layout these are [12, 13]:
              - 12: Electricity:Facility
              - 13: ITE-CPU:InteriorEquipment:Electricity
        scale: multiplier, default 1.0/3.6e9 (J/h -> MWh/h).
    """

    def __init__(self, env, energy_indices, scale=1.0 / 3.6e9):
        super().__init__(env)
        self.energy_indices = list(energy_indices)
        self.scale = float(scale)

    def observation(self, obs):
        obs = np.asarray(obs, dtype=np.float32).copy()
        for i in self.energy_indices:
            obs[i] = obs[i] * self.scale
        return obs
