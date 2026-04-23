"""Implementation of reward functions."""


from datetime import datetime
from math import exp
from typing import Any, Dict, List, Tuple, Union

from sinergym.utils.constants import LOG_REWARD_LEVEL, YEAR
from sinergym.utils.logger import Logger


class BaseReward(object):

    logger = Logger().getLogger(name='REWARD',
                                level=LOG_REWARD_LEVEL)

    def __init__(self):
        """
        Base reward class.

        All reward functions should inherit from this class.

        Args:
            env (Env): Gym environment.
        """

    def __call__(self, obs_dict: Dict[str, Any]
                 ) -> Tuple[float, Dict[str, Any]]:
        """Method for calculating the reward function."""
        raise NotImplementedError(
            "Reward class must have a `__call__` method.")


class LinearReward(BaseReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        energy_weight: float = 0.5,
        lambda_energy: float = 1.0,
        lambda_temperature: float = 1.0
    ):
        """
        Linear reward function.

        It considers the energy consumption and the absolute difference to temperature comfort.

        .. math::
            R = - W * lambda_E * power - (1 - W) * lambda_T * (max(T - T_{low}, 0) + max(T_{up} - T, 0))

        Args:
            temperature_variables (List[str]): Name(s) of the temperature variable(s).
            energy_variables (List[str]): Name(s) of the energy/power variable(s).
            range_comfort_winter (Tuple[int,int]): Temperature comfort range for cold season. Depends on environment you are using.
            range_comfort_summer (Tuple[int,int]): Temperature comfort range for hot season. Depends on environment you are using.
            summer_start (Tuple[int,int]): Summer session tuple with month and day start. Defaults to (6,1).
            summer_final (Tuple[int,int]): Summer session tuple with month and day end. defaults to (9,30).
            energy_weight (float, optional): Weight given to the energy term. Defaults to 0.5.
            lambda_energy (float, optional): Constant for removing dimensions from power(1/W). Defaults to 1e-4.
            lambda_temperature (float, optional): Constant for removing dimensions from temperature(1/C). Defaults to 1.0.
        """

        super(LinearReward, self).__init__()

        # Name of the variables
        self.temp_names = temperature_variables
        self.energy_names = energy_variables

        # Reward parameters
        self.range_comfort_winter = range_comfort_winter
        self.range_comfort_summer = range_comfort_summer
        self.W_energy = energy_weight
        self.lambda_energy = lambda_energy
        self.lambda_temp = lambda_temperature

        # Summer period
        self.summer_start = summer_start  # (month,day)
        self.summer_final = summer_final  # (month,day)

        self.logger.info('Reward function initialized.')

    def __call__(self, obs_dict: Dict[str, Any]
                 ) -> Tuple[float, Dict[str, Any]]:
        """Calculate the reward function.

        Args:
            obs_dict (Dict[str, Any]): Dict with observation variable name (key) and observation variable value (value)

        Returns:
            Tuple[float, Dict[str, Any]]: Reward value and dictionary with their individual components.
        """
        # Check variables to calculate reward are available
        try:
            assert all(temp_name in list(obs_dict.keys())
                       for temp_name in self.temp_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the temperature variables specified are not present in observation.')
            raise err
        try:
            assert all(energy_name in list(obs_dict.keys())
                       for energy_name in self.energy_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise err

        # Energy calculation
        energy_consumed, energy_values = self._get_energy_consumed(obs_dict)
        energy_penalty = self._get_energy_penalty(energy_values)

        # Comfort violation calculation
        total_temp_violation, temp_violations = self._get_temperature_violation(
            obs_dict)
        comfort_penalty = self._get_comfort_penalty(temp_violations)

        # Weighted sum of both terms
        reward, energy_term, comfort_term = self._get_reward(
            energy_penalty, comfort_penalty)

        reward_terms = {
            'energy_term': energy_term,
            'comfort_term': comfort_term,
            'reward_weight': self.W_energy,
            'abs_energy_penalty': energy_penalty,
            'abs_comfort_penalty': comfort_penalty,
            'total_power_demand': energy_consumed,
            'total_temperature_violation': total_temp_violation
        }

        return reward, reward_terms

    def _get_energy_consumed(self, obs_dict: Dict[str,
                                                  Any]) -> Tuple[float,
                                                                 List[float]]:
        """Calculate the total energy consumed in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        energy_values = [
            v for k, v in obs_dict.items() if k in self.energy_names]

        # The total energy is the sum of energies
        total_energy = sum(energy_values)

        return total_energy, energy_values

    def _get_temperature_violation(
            self, obs_dict: Dict[str, Any]) -> Tuple[float, List[float]]:
        """Calculate the total temperature violation (ºC) in the current observation.

        Returns:
            Tuple[float, List[float]]: Total temperature violation (ºC) and list with temperature violation in each zone.
        """

        month = obs_dict['month']
        day = obs_dict['day_of_month']
        year = YEAR
        current_dt = datetime(int(year), int(month), int(day))

        # Periods
        summer_start_date = datetime(
            int(year),
            self.summer_start[0],
            self.summer_start[1])
        summer_final_date = datetime(
            int(year),
            self.summer_final[0],
            self.summer_final[1])

        if current_dt >= summer_start_date and current_dt <= summer_final_date:
            temp_range = self.range_comfort_summer
        else:
            temp_range = self.range_comfort_winter

        temp_values = [
            v for k, v in obs_dict.items() if k in self.temp_names]
        total_temp_violation = 0.0
        temp_violations = []
        for T in temp_values:
            if T < temp_range[0] or T > temp_range[1]:
                temp_violation = min(
                    abs(temp_range[0] - T), abs(T - temp_range[1]))
                temp_violations.append(temp_violation)
                total_temp_violation += temp_violation

        return total_temp_violation, temp_violations

    def _get_energy_penalty(self, energy_values: List[float]) -> float:
        """Calculate the negative absolute energy penalty based on energy values

        Args:
            energy_values (List[float]): Energy values

        Returns:
            float: Negative absolute energy penalty value
        """
        energy_penalty = -sum(energy_values)
        return energy_penalty

    def _get_comfort_penalty(self, temp_violations: List[float]) -> float:
        """Calculate the negative absolute comfort penalty based on temperature violation values

        Args:
            temp_violations (List[float]): Temperature violation values

        Returns:
            float: Negative absolute comfort penalty value
        """
        comfort_penalty = -sum(temp_violations)
        return comfort_penalty

    def _get_reward(self, energy_penalty: float,
                    comfort_penalty: float) -> Tuple[float, float, float]:
        """It calculates reward value using the negative absolute comfort and energy penalty calculates previously.

        Args:
            energy_penalty (float): Negative absolute energy penalty value.
            comfort_penalty (float): Negative absolute comfort penalty value.

        Returns:
            Tuple[float,float,float]: total reward calculated, reward term for energy, reward term for comfort.
        """
        energy_term = self.lambda_energy * self.W_energy * energy_penalty
        comfort_term = self.lambda_temp * \
            (1 - self.W_energy) * comfort_penalty
        reward = energy_term + comfort_term
        return reward, energy_term, comfort_term


class ExpReward(LinearReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        energy_weight: float = 0.5,
        lambda_energy: float = 1.0,
        lambda_temperature: float = 1.0
    ):
        """
        Reward considering exponential absolute difference to temperature comfort.

        .. math::
            R = - W * lambda_E * power - (1 - W) * lambda_T * exp( (max(T - T_{low}, 0) + max(T_{up} - T, 0)) )

        Args:
            temperature_variables (List[str]): Name(s) of the temperature variable(s).
            energy_variables (List[str]): Name(s) of the energy/power variable(s).
            range_comfort_winter (Tuple[int,int]): Temperature comfort range for cold season. Depends on environment you are using.
            range_comfort_summer (Tuple[int,int]): Temperature comfort range for hot season. Depends on environment you are using.
            summer_start (Tuple[int,int]): Summer session tuple with month and day start. Defaults to (6,1).
            summer_final (Tuple[int,int]): Summer session tuple with month and day end. defaults to (9,30).
            energy_weight (float, optional): Weight given to the energy term. Defaults to 0.5.
            lambda_energy (float, optional): Constant for removing dimensions from power(1/W). Defaults to 1e-4.
            lambda_temperature (float, optional): Constant for removing dimensions from temperature(1/C). Defaults to 1.0.
        """

        super(ExpReward, self).__init__(
            temperature_variables,
            energy_variables,
            range_comfort_winter,
            range_comfort_summer,
            summer_start,
            summer_final,
            energy_weight,
            lambda_energy,
            lambda_temperature
        )

    def _get_comfort_penalty(self, temp_violations: List[float]) -> float:
        """Calculate the negative absolute comfort penalty based on temperature violation values, using an exponential concept when temperature violation > 0.

        Args:
            temp_violations (List[float]): Temperature violation values

        Returns:
            float: Negative absolute comfort penalty value
        """
        comfort_penalty = -sum(list(map(lambda temp_violation: exp(
            temp_violation) if temp_violation > 0 else 0, temp_violations)))
        return comfort_penalty


class HourlyLinearReward(LinearReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        default_energy_weight: float = 0.5,
        lambda_energy: float = 1.0,
        lambda_temperature: float = 1.0,
        range_comfort_hours: tuple = (9, 19),
    ):
        """
        Linear reward function with a time-dependent weight for consumption and energy terms.

        Args:
            temperature_variables (List[str]]): Name(s) of the temperature variable(s).
            energy_variables (List[str]): Name(s) of the energy/power variable(s).
            range_comfort_winter (Tuple[int,int]): Temperature comfort range for cold season. Depends on environment you are using.
            range_comfort_summer (Tuple[int,int]): Temperature comfort range for hot season. Depends on environment you are using.
            summer_start (Tuple[int,int]): Summer session tuple with month and day start. Defaults to (6,1).
            summer_final (Tuple[int,int]): Summer session tuple with month and day end. defaults to (9,30).
            default_energy_weight (float, optional): Default weight given to the energy term when thermal comfort is considered. Defaults to 0.5.
            lambda_energy (float, optional): Constant for removing dimensions from power(1/W). Defaults to 1e-4.
            lambda_temperature (float, optional): Constant for removing dimensions from temperature(1/C). Defaults to 1.0.
            range_comfort_hours (tuple, optional): Hours where thermal comfort is considered. Defaults to (9, 19).
        """

        super(HourlyLinearReward, self).__init__(
            temperature_variables,
            energy_variables,
            range_comfort_winter,
            range_comfort_summer,
            summer_start,
            summer_final,
            default_energy_weight,
            lambda_energy,
            lambda_temperature
        )

        # Reward parameters
        self.range_comfort_hours = range_comfort_hours
        self.default_energy_weight = default_energy_weight

    def __call__(self, obs_dict: Dict[str, Any]
                 ) -> Tuple[float, Dict[str, Any]]:
        """Calculate the reward function.

        Args:
            obs_dict (Dict[str, Any]): Dict with observation variable name (key) and observation variable value (value)

        Returns:
            Tuple[float, Dict[str, Any]]: Reward value and dictionary with their individual components.
        """
        # Check variables to calculate reward are available
        try:
            assert all(temp_name in list(obs_dict.keys())
                       for temp_name in self.temp_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the temperature variables specified are not present in observation.')
            raise err
        try:
            assert all(energy_name in list(obs_dict.keys())
                       for energy_name in self.energy_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise err

        # Energy calculation
        energy_consumed, energy_values = self._get_energy_consumed(obs_dict)
        energy_penalty = self._get_energy_penalty(energy_values)

        # Comfort violation calculation
        total_temp_violation, temp_violations = self._get_temperature_violation(
            obs_dict)
        comfort_penalty = self._get_comfort_penalty(temp_violations)

        # Determine reward weight depending on the hour
        hour = obs_dict['hour']
        if hour >= self.range_comfort_hours[0] and hour <= self.range_comfort_hours[1]:
            self.W_energy = self.default_energy_weight
        else:
            self.W_energy = 1.0

        # Weighted sum of both terms
        reward, energy_term, comfort_term = self._get_reward(
            energy_penalty, comfort_penalty)

        reward_terms = {
            'energy_term': energy_term,
            'comfort_term': comfort_term,
            'reward_weight': self.W_energy,
            'abs_energy_penalty': energy_penalty,
            'abs_comfort_penalty': comfort_penalty,
            'total_power_demand': energy_consumed,
            'total_temperature_violation': total_temp_violation
        }

        return reward, reward_terms


class NormalizedLinearReward(LinearReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        energy_weight: float = 0.5,
        max_energy_penalty: float = 8,
        max_comfort_penalty: float = 12,
    ):
        """
        Linear reward function with a time-dependent weight for consumption and energy terms.

        Args:
            temperature_variables (List[str]]): Name(s) of the temperature variable(s).
            energy_variables (List[str]): Name(s) of the energy/power variable(s).
            range_comfort_winter (Tuple[int,int]): Temperature comfort range for cold season. Depends on environment you are using.
            range_comfort_summer (Tuple[int,int]): Temperature comfort range for hot season. Depends on environment you are using.
            summer_start (Tuple[int,int]): Summer session tuple with month and day start. Defaults to (6,1).
            summer_final (Tuple[int,int]): Summer session tuple with month and day end. defaults to (9,30).
            default_energy_weight (float, optional): Default weight given to the energy term when thermal comfort is considered. Defaults to 0.5.
            lambda_energy (float, optional): Constant for removing dimensions from power(1/W). Defaults to 1e-4.
            lambda_temperature (float, optional): Constant for removing dimensions from temperature(1/C). Defaults to 1.0.
            range_comfort_hours (tuple, optional): Hours where thermal comfort is considered. Defaults to (9, 19).
        """

        super(NormalizedLinearReward, self).__init__(
            temperature_variables,
            energy_variables,
            range_comfort_winter,
            range_comfort_summer,
            summer_start,
            summer_final,
            energy_weight
        )

        # Reward parameters
        self.max_energy_penalty = max_energy_penalty
        self.max_comfort_penalty = max_comfort_penalty

    def _get_reward(self, energy_penalty: float,
                    comfort_penalty: float) -> Tuple[float, float, float]:
        """It calculates reward value using energy consumption and grades of temperature out of comfort range. Aplying normalization

        Args:
            energy (float): Negative absolute energy penalty value.
            comfort (float): Negative absolute comfort penalty value.

        Returns:
            Tuple[float,float,float]: total reward calculated, reward term for energy and reward term for comfort.
        """
        # Update max energy and comfort
        self.max_energy_penalty = max(self.max_energy_penalty, energy_penalty)
        self.max_comfort_penalty = max(
            self.max_comfort_penalty, comfort_penalty)
        # Calculate normalization
        energy_norm = 0 if energy_penalty == 0 else energy_penalty / self.max_energy_penalty
        comfort_norm = 0 if comfort_penalty == 0 else comfort_penalty / self.max_comfort_penalty
        # Calculate reward terms with norm values
        energy_term = self.W_energy * energy_norm
        comfort_term = (1 - self.W_energy) * comfort_norm
        reward = energy_term + comfort_term
        return reward, energy_term, comfort_term


class LinearReward_DC_1(BaseReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        ITE_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        energy_weight: float = 1/3,
        ITE_weight: float = 1/3,
        lambda_energy: float = 1.0,
        lambda_ITE: float = 1.0,
        lambda_temperature: float = 1.0
    ):

        super(LinearReward_DC, self).__init__()

        # Name of the variables
        self.temp_names = temperature_variables
        self.energy_names = energy_variables
        self.ITE_names = ITE_variables

        # Reward parameters
        self.range_comfort_winter = range_comfort_winter
        self.range_comfort_summer = range_comfort_summer
        self.W_energy = energy_weight
        self.W_ITE = ITE_weight
        self.lambda_energy = lambda_energy
        self.lambda_ITE = lambda_ITE
        self.lambda_temp = lambda_temperature

        # Summer period
        self.summer_start = summer_start  # (month,day)
        self.summer_final = summer_final  # (month,day)

        self.logger.info('Reward function initialized.')

    def __call__(self, obs_dict: Dict[str, Any]
                 ) -> Tuple[float, Dict[str, Any]]:
        """Calculate the reward function.

        Args:
            obs_dict (Dict[str, Any]): Dict with observation variable name (key) and observation variable value (value)

        Returns:
            Tuple[float, Dict[str, Any]]: Reward value and dictionary with their individual components.
        """
        # Check variables to calculate reward are available
        try:
            assert all(temp_name in list(obs_dict.keys())
                       for temp_name in self.temp_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the temperature variables specified are not present in observation.')
            raise err
        try:
            assert all(energy_name in list(obs_dict.keys())
                       for energy_name in self.energy_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise
        try:
            assert all(ITE_name in list(obs_dict.keys())
                       for ITE_name in self.ITE_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise err

        # Energy calculation
        energy_consumed, energy_values = self._get_energy_consumed(obs_dict)
        energy_penalty = self._get_energy_penalty(energy_values)

        # Comfort violation calculation
        total_temp_violation, temp_violations = self._get_temperature_violation(
            obs_dict)
        comfort_penalty = self._get_comfort_penalty(temp_violations)

        # ITE utilization calculation
        ITE_used, ITE_values = self._get_ITE_used(obs_dict)
        ITE_penalty = self._get_ITE_penalty(ITE_values)

        # Weighted sum of all terms
        reward, energy_term, ITE_term, comfort_term = self._get_reward(
            energy_penalty, ITE_penalty, comfort_penalty)

        reward_terms = {
            'energy_term': energy_term,
            'ITE_term': ITE_term,
            'comfort_term': comfort_term,
            'reward_weight_1': self.W_energy,
            'reward_weight_2': self.W_ITE,
            'abs_energy_penalty': energy_penalty,
            'abs_ITE_penalty': ITE_penalty,
            'abs_comfort_penalty': comfort_penalty,
            'total_power_demand': energy_consumed,
            'total_ITE_used': ITE_used,
            'total_temperature_violation': total_temp_violation
        }

        return reward, reward_terms

    def _get_energy_consumed(self, obs_dict: Dict[str,
                                                  Any]) -> Tuple[float,
                                                                 List[float]]:
        """Calculate the total energy consumed in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        energy_values = [
            v for k, v in obs_dict.items() if k in self.energy_names]

        # The total energy is the sum of energies
        total_energy = sum(energy_values)

        return total_energy, energy_values

    def _get_ITE_used(self, obs_dict: Dict[str,
                                           Any]) -> Tuple[float,
                                                          List[float]]:
        """Calculate the total ITE used in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        ITE_values = [
            v for k, v in obs_dict.items() if k in self.ITE_names]

        # The total energy is the sum of energies
        total_ITE = sum(ITE_values)

        return total_ITE, ITE_values

    def _get_temperature_violation(
            self, obs_dict: Dict[str, Any]) -> Tuple[float, List[float]]:
        """Calculate the total temperature violation (ºC) in the current observation.

        Returns:
            Tuple[float, List[float]]: Total temperature violation (ºC) and list with temperature violation in each zone.
        """

        month = obs_dict['month']
        day = obs_dict['day_of_month']
        year = YEAR
        current_dt = datetime(int(year), int(month), int(day))

        # Periods
        summer_start_date = datetime(
            int(year),
            self.summer_start[0],
            self.summer_start[1])
        summer_final_date = datetime(
            int(year),
            self.summer_final[0],
            self.summer_final[1])

        if current_dt >= summer_start_date and current_dt <= summer_final_date:
            temp_range = self.range_comfort_summer
        else:
            temp_range = self.range_comfort_winter

        temp_values = [
            v for k, v in obs_dict.items() if k in self.temp_names]
        total_temp_violation = 0.0
        temp_violations = []
        for T in temp_values:
            if T < temp_range[0] or T > temp_range[1]:
                temp_violation = min(
                    abs(temp_range[0] - T), abs(T - temp_range[1]))
                temp_violations.append(temp_violation)
                total_temp_violation += temp_violation

        return total_temp_violation, temp_violations

    def _get_energy_penalty(self, energy_values: List[float]) -> float:
        """Calculate the negative absolute energy penalty based on energy values

        Args:
            energy_values (List[float]): Energy values

        Returns:
            float: Negative absolute energy penalty value
        """
        energy_penalty = -sum(energy_values)
        return energy_penalty

    def _get_ITE_penalty(self, ITE_values: List[float]) -> float:
        ITE_penalty = -sum(ITE_values)
        return ITE_penalty

    def _get_comfort_penalty(self, temp_violations: List[float]) -> float:
        """Calculate the negative absolute comfort penalty based on temperature violation values

        Args:
            temp_violations (List[float]): Temperature violation values

        Returns:
            float: Negative absolute comfort penalty value
        """
        comfort_penalty = -sum(temp_violations)
        return comfort_penalty

    def _get_reward(self, energy_penalty: float, ITE_penalty: float,
                    comfort_penalty: float) -> Tuple[float, float, float]:
        """It calculates reward value using the negative absolute comfort and energy penalty calculates previously.

        Args:
            energy_penalty (float): Negative absolute energy penalty value.
            ITE_penalty (float): Negative ITE use penalty value.
            comfort_penalty (float): Negative absolute comfort penalty value.

        Returns:
            Tuple[float,float,float]: total reward calculated, reward term for energy, reward term for comfort.
        """
        energy_term = self.lambda_energy * self.W_energy * -(energy_penalty/ITE_penalty)
        ITE_term = self.lambda_ITE * self.W_ITE * (1/ITE_penalty)
        comfort_term = self.lambda_temp * \
            (1 - self.W_energy - self.W_ITE) * comfort_penalty
        reward = energy_term + ITE_term + comfort_term
        return reward, energy_term, ITE_term, comfort_term

class LinearReward_DC_pureITEeff(BaseReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        ITE_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        energy_weight: float = 1/3,
        ITE_weight: float = 1/3,
        lambda_energy: float = 1.0,
        lambda_ITE: float = 1.0,
        lambda_temperature: float = 1.0
    ):

        super(LinearReward_DC, self).__init__()

        # Name of the variables
        self.temp_names = temperature_variables
        self.energy_names = energy_variables
        self.ITE_names = ITE_variables

        # Reward parameters
        self.range_comfort_winter = range_comfort_winter
        self.range_comfort_summer = range_comfort_summer
        self.W_energy = energy_weight
        self.W_ITE = ITE_weight
        self.lambda_energy = lambda_energy
        self.lambda_ITE = lambda_ITE
        self.lambda_temp = lambda_temperature

        # Summer period
        self.summer_start = summer_start  # (month,day)
        self.summer_final = summer_final  # (month,day)

        self.logger.info('Reward function initialized.')

    def __call__(self, obs_dict: Dict[str, Any]
                 ) -> Tuple[float, Dict[str, Any]]:
        """Calculate the reward function.

        Args:
            obs_dict (Dict[str, Any]): Dict with observation variable name (key) and observation variable value (value)

        Returns:
            Tuple[float, Dict[str, Any]]: Reward value and dictionary with their individual components.
        """
        # Check variables to calculate reward are available
        try:
            assert all(temp_name in list(obs_dict.keys())
                       for temp_name in self.temp_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the temperature variables specified are not present in observation.')
            raise err
        try:
            assert all(energy_name in list(obs_dict.keys())
                       for energy_name in self.energy_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise
        try:
            assert all(ITE_name in list(obs_dict.keys())
                       for ITE_name in self.ITE_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise err

        # Energy calculation
        energy_consumed, energy_values = self._get_energy_consumed(obs_dict)
        energy_penalty = self._get_energy_penalty(energy_values)

        # Comfort violation calculation
        total_temp_violation, temp_violations = self._get_temperature_violation(
            obs_dict)
        comfort_penalty = self._get_comfort_penalty(temp_violations)

        # ITE utilization calculation
        ITE_used, ITE_values = self._get_ITE_used(obs_dict)
        ITE_penalty = self._get_ITE_penalty(ITE_values)

        # Weighted sum of all terms
        reward, energy_term, ITE_term, comfort_term = self._get_reward(
            energy_penalty, ITE_penalty, comfort_penalty)

        reward_terms = {
            'energy_term': energy_term,
            'ITE_term': ITE_term,
            'comfort_term': comfort_term,
            'reward_weight_1': self.W_energy,
            'reward_weight_2': self.W_ITE,
            'abs_energy_penalty': energy_penalty,
            'abs_ITE_penalty': ITE_penalty,
            'abs_comfort_penalty': comfort_penalty,
            'total_power_demand': energy_consumed,
            'total_ITE_used': ITE_used,
            'total_temperature_violation': total_temp_violation
        }

        return reward, reward_terms

    def _get_energy_consumed(self, obs_dict: Dict[str,
                                                  Any]) -> Tuple[float,
                                                                 List[float]]:
        """Calculate the total energy consumed in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        energy_values = [
            v for k, v in obs_dict.items() if k in self.energy_names]

        # The total energy is the sum of energies
        total_energy = sum(energy_values)

        return total_energy, energy_values

    def _get_ITE_used(self, obs_dict: Dict[str,
                                           Any]) -> Tuple[float,
                                                          List[float]]:
        """Calculate the total ITE used in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        ITE_values = [
            v for k, v in obs_dict.items() if k in self.ITE_names]

        # The total energy is the sum of energies
        total_ITE = sum(ITE_values)

        return total_ITE, ITE_values

    def _get_temperature_violation(
            self, obs_dict: Dict[str, Any]) -> Tuple[float, List[float]]:
        """Calculate the total temperature violation (ºC) in the current observation.

        Returns:
            Tuple[float, List[float]]: Total temperature violation (ºC) and list with temperature violation in each zone.
        """

        month = obs_dict['month']
        day = obs_dict['day_of_month']
        year = YEAR
        current_dt = datetime(int(year), int(month), int(day))

        # Periods
        summer_start_date = datetime(
            int(year),
            self.summer_start[0],
            self.summer_start[1])
        summer_final_date = datetime(
            int(year),
            self.summer_final[0],
            self.summer_final[1])

        if current_dt >= summer_start_date and current_dt <= summer_final_date:
            temp_range = self.range_comfort_summer
        else:
            temp_range = self.range_comfort_winter

        temp_values = [
            v for k, v in obs_dict.items() if k in self.temp_names]
        total_temp_violation = 0.0
        temp_violations = []
        for T in temp_values:
            if T < temp_range[0] or T > temp_range[1]:
                temp_violation = min(
                    abs(temp_range[0] - T), abs(T - temp_range[1]))
                temp_violations.append(temp_violation)
                total_temp_violation += temp_violation

        return total_temp_violation, temp_violations

    def _get_energy_penalty(self, energy_values: List[float]) -> float:
        """Calculate the negative absolute energy penalty based on energy values

        Args:
            energy_values (List[float]): Energy values

        Returns:
            float: Negative absolute energy penalty value
        """
        energy_penalty = -sum(energy_values)
        return energy_penalty

    def _get_ITE_penalty(self, ITE_values: List[float]) -> float:
        ITE_penalty = -sum(ITE_values)
        return ITE_penalty

    def _get_comfort_penalty(self, temp_violations: List[float]) -> float:
        """Calculate the negative absolute comfort penalty based on temperature violation values

        Args:
            temp_violations (List[float]): Temperature violation values

        Returns:
            float: Negative absolute comfort penalty value
        """
        comfort_penalty = -sum(temp_violations)
        return comfort_penalty

    def _get_reward(self, energy_penalty: float, ITE_penalty: float,
                    comfort_penalty: float) -> Tuple[float, float, float]:
        """It calculates reward value using the negative absolute comfort and energy penalty calculates previously.

        Args:
            energy_penalty (float): Negative absolute energy penalty value.
            ITE_penalty (float): Negative ITE use penalty value.
            comfort_penalty (float): Negative absolute comfort penalty value.

        Returns:
            Tuple[float,float,float]: total reward calculated, reward term for energy, reward term for comfort.
        """
        energy_term = self.lambda_energy * self.W_energy * energy_penalty
        ITE_term = self.lambda_ITE * self.W_ITE * -(ITE_penalty/energy_penalty)
        comfort_term = self.lambda_temp * \
            (1 - self.W_energy - self.W_ITE) * comfort_penalty
        reward = energy_term + ITE_term + comfort_term
        return reward, energy_term, ITE_term, comfort_term


class LinearReward_DC(BaseReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        ITE_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        energy_weight: float = 1/3,
        ITE_weight: float = 1/3,
        lambda_energy: float = 1.0,
        lambda_ITE: float = 1.0,
        lambda_temperature: float = 1.0
    ):

        super(LinearReward_DC, self).__init__()

        # Name of the variables
        self.temp_names = temperature_variables
        self.energy_names = energy_variables
        self.ITE_names = ITE_variables

        # Reward parameters
        self.range_comfort_winter = range_comfort_winter
        self.range_comfort_summer = range_comfort_summer
        self.W_energy = energy_weight
        self.W_ITE = ITE_weight
        self.lambda_energy = lambda_energy
        self.lambda_ITE = lambda_ITE
        self.lambda_temp = lambda_temperature

        # Summer period
        self.summer_start = summer_start  # (month,day)
        self.summer_final = summer_final  # (month,day)

        self.logger.info('Reward function initialized.')

    def __call__(self, obs_dict: Dict[str, Any]
                 ) -> Tuple[float, Dict[str, Any]]:
        """Calculate the reward function.

        Args:
            obs_dict (Dict[str, Any]): Dict with observation variable name (key) and observation variable value (value)

        Returns:
            Tuple[float, Dict[str, Any]]: Reward value and dictionary with their individual components.
        """
        # Check variables to calculate reward are available
        try:
            assert all(temp_name in list(obs_dict.keys())
                       for temp_name in self.temp_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the temperature variables specified are not present in observation.')
            raise err
        try:
            assert all(energy_name in list(obs_dict.keys())
                       for energy_name in self.energy_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise
        try:
            assert all(ITE_name in list(obs_dict.keys())
                       for ITE_name in self.ITE_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise err

        # Energy calculation
        energy_consumed, energy_values = self._get_energy_consumed(obs_dict)
        energy_penalty = self._get_energy_penalty(energy_values)

        # Comfort violation calculation
        total_temp_violation, temp_violations = self._get_temperature_violation(
            obs_dict)
        comfort_penalty = self._get_comfort_penalty(temp_violations)

        # ITE utilization calculation
        ITE_used, ITE_values = self._get_ITE_used(obs_dict)
        ITE_penalty = self._get_ITE_penalty(ITE_values)

        # Weighted sum of all terms
        reward, energy_term, ITE_term, comfort_term = self._get_reward(
            energy_penalty, ITE_penalty, comfort_penalty)

        reward_terms = {
            'energy_term': energy_term,
            'ITE_term': ITE_term,
            'comfort_term': comfort_term,
            'reward_weight_1': self.W_energy,
            'reward_weight_2': self.W_ITE,
            'abs_energy_penalty': energy_penalty,
            'abs_ITE_penalty': ITE_penalty,
            'abs_comfort_penalty': comfort_penalty,
            'total_power_demand': energy_consumed,
            'total_ITE_used': ITE_used,
            'total_temperature_violation': total_temp_violation
        }

        return reward, reward_terms

    def _get_energy_consumed(self, obs_dict: Dict[str,
                                                  Any]) -> Tuple[float,
                                                                 List[float]]:
        """Calculate the total energy consumed in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        energy_values = [
            v for k, v in obs_dict.items() if k in self.energy_names]

        # The total energy is the sum of energies
        total_energy = sum(energy_values)

        return total_energy, energy_values

    def _get_ITE_used(self, obs_dict: Dict[str,
                                           Any]) -> Tuple[float,
                                                          List[float]]:
        """Calculate the total ITE used in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        ITE_values = [
            v for k, v in obs_dict.items() if k in self.ITE_names]

        for i in range(len(ITE_values)):
            ITE_values[i]=1-ITE_values[i]
        # The total energy is the sum of energies
        total_ITE = sum(ITE_values)

        return total_ITE, ITE_values

    def _get_temperature_violation(
            self, obs_dict: Dict[str, Any]) -> Tuple[float, List[float]]:
        """Calculate the total temperature violation (ºC) in the current observation.

        Returns:
            Tuple[float, List[float]]: Total temperature violation (ºC) and list with temperature violation in each zone.
        """

        month = obs_dict['month']
        day = obs_dict['day_of_month']
        year = YEAR
        current_dt = datetime(int(year), int(month), int(day))

        # Periods
        summer_start_date = datetime(
            int(year),
            self.summer_start[0],
            self.summer_start[1])
        summer_final_date = datetime(
            int(year),
            self.summer_final[0],
            self.summer_final[1])

        if current_dt >= summer_start_date and current_dt <= summer_final_date:
            temp_range = self.range_comfort_summer
        else:
            temp_range = self.range_comfort_winter

        temp_values = [
            v for k, v in obs_dict.items() if k in self.temp_names]
        total_temp_violation = 0.0
        temp_violations = []
        for T in temp_values:
            if T < temp_range[0] or T > temp_range[1]:
                temp_violation = min(
                    abs(temp_range[0] - T), abs(T - temp_range[1]))
                temp_violations.append(temp_violation)
                total_temp_violation += temp_violation

        return total_temp_violation, temp_violations

    def _get_energy_penalty(self, energy_values: List[float]) -> float:
        """Calculate the negative absolute energy penalty based on energy values

        Args:
            energy_values (List[float]): Energy values

        Returns:
            float: Negative absolute energy penalty value
        """
        energy_penalty = -sum(energy_values)
        return energy_penalty

    def _get_ITE_penalty(self, ITE_values: List[float]) -> float:
        ITE_penalty = -sum(ITE_values)
        return ITE_penalty

    def _get_comfort_penalty(self, temp_violations: List[float]) -> float:
        """Calculate the negative absolute comfort penalty based on temperature violation values

        Args:
            temp_violations (List[float]): Temperature violation values

        Returns:
            float: Negative absolute comfort penalty value
        """
        comfort_penalty = -sum(temp_violations)
        return comfort_penalty

    def _get_reward(self, energy_penalty: float, ITE_penalty: float,
                    comfort_penalty: float) -> Tuple[float, float, float]:
        """It calculates reward value using the negative absolute comfort and energy penalty calculates previously.

        Args:
            energy_penalty (float): Negative absolute energy penalty value.
            ITE_penalty (float): Negative ITE use penalty value.
            comfort_penalty (float): Negative absolute comfort penalty value.

        Returns:
            Tuple[float,float,float]: total reward calculated, reward term for energy, reward term for comfort.
        """
        energy_term = self.lambda_energy * self.W_energy * energy_penalty
        ITE_term = self.lambda_ITE * self.W_ITE * ITE_penalty
        comfort_term = self.lambda_temp * \
            (1 - self.W_energy - self.W_ITE) * comfort_penalty
        reward = energy_term + ITE_term + comfort_term
        return reward, energy_term, ITE_term, comfort_term


class PUE_Reward(BaseReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        ITE_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        energy_weight: float = 1/3,
        lambda_energy: float = 1.0,
        lambda_temperature: float = 1.0
    ):

        super(PUE_Reward, self).__init__()

        # Name of the variables
        self.temp_names = temperature_variables
        self.energy_names = energy_variables
        self.ITE_names = ITE_variables

        # Reward parameters
        self.range_comfort_winter = range_comfort_winter
        self.range_comfort_summer = range_comfort_summer
        self.W_energy = energy_weight
        self.lambda_energy = lambda_energy
        self.lambda_temp = lambda_temperature

        # Summer period
        self.summer_start = summer_start  # (month,day)
        self.summer_final = summer_final  # (month,day)

        self.logger.info('Reward function initialized.')

    def __call__(self, obs_dict: Dict[str, Any]
                 ) -> Tuple[float, Dict[str, Any]]:
        """Calculate the reward function.

        Args:
            obs_dict (Dict[str, Any]): Dict with observation variable name (key) and observation variable value (value)

        Returns:
            Tuple[float, Dict[str, Any]]: Reward value and dictionary with their individual components.
        """
        # Check variables to calculate reward are available
        try:
            assert all(temp_name in list(obs_dict.keys())
                       for temp_name in self.temp_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the temperature variables specified are not present in observation.')
            raise err
        try:
            assert all(energy_name in list(obs_dict.keys())
                       for energy_name in self.energy_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise err
        try:
            assert all(ITE_name in list(obs_dict.keys())
                       for ITE_name in self.ITE_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the ITE variables specified are not present in observation.')
            raise err

        # Energy calculation
        energy_consumed, energy_values = self._get_energy_consumed(obs_dict)
        energy_penalty = self._get_energy_penalty(energy_values)

        # Comfort violation calculation
        total_temp_violation, temp_violations = self._get_temperature_violation(
            obs_dict)
        comfort_penalty = self._get_comfort_penalty(temp_violations)

        # ITE utilization calculation
        ITE_used, ITE_values = self._get_ITE_used(obs_dict)
        ITE_penalty = self._get_ITE_penalty(ITE_values)

        # Weighted sum of all terms
        reward, energy_term, comfort_term = self._get_reward(
            energy_penalty, ITE_penalty, comfort_penalty)

        reward_terms = {
            'energy_term': energy_term,
            'comfort_term': comfort_term,
            'reward_weight': self.W_energy,
            'abs_energy_penalty': energy_penalty,
            'abs_comfort_penalty': comfort_penalty,
            'total_power_demand': energy_consumed,
            'total_temperature_violation': total_temp_violation
        }

        return reward, reward_terms

    def _get_energy_consumed(self, obs_dict: Dict[str,
                                                  Any]) -> Tuple[float,
                                                                 List[float]]:
        """Calculate the total energy consumed in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        energy_values = [
            v for k, v in obs_dict.items() if k in self.energy_names]

        total_energy = sum(energy_values)

        return total_energy, energy_values

    def _get_ITE_used(self, obs_dict: Dict[str,
                                           Any]) -> Tuple[float,
                                                          List[float]]:
        """Calculate the total ITE used in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        ITE_values = [
            v for k, v in obs_dict.items() if k in self.ITE_names]
        # The total energy is the sum of energies

        total_ITE = sum(ITE_values)

        return total_ITE, ITE_values

    def _get_temperature_violation(
            self, obs_dict: Dict[str, Any]) -> Tuple[float, List[float]]:
        """Calculate the total temperature violation (ºC) in the current observation.

        Returns:
            Tuple[float, List[float]]: Total temperature violation (ºC) and list with temperature violation in each zone.
        """

        month = obs_dict['month']
        day = obs_dict['day_of_month']
        year = YEAR
        current_dt = datetime(int(year), int(month), int(day))

        # Periods
        summer_start_date = datetime(
            int(year),
            self.summer_start[0],
            self.summer_start[1])
        summer_final_date = datetime(
            int(year),
            self.summer_final[0],
            self.summer_final[1])

        if current_dt >= summer_start_date and current_dt <= summer_final_date:
            temp_range = self.range_comfort_summer
        else:
            temp_range = self.range_comfort_winter

        temp_values = [
            v for k, v in obs_dict.items() if k in self.temp_names]
        total_temp_violation = 0.0
        temp_violations = []
        for T in temp_values:
            if T < temp_range[0] or T > temp_range[1]:
                temp_violation = min(
                    abs(temp_range[0] - T), abs(T - temp_range[1]))
                temp_violations.append(temp_violation)
                total_temp_violation += temp_violation

        return total_temp_violation, temp_violations

    def _get_energy_penalty(self, energy_values: List[float]) -> float:
        """Calculate the negative absolute energy penalty based on energy values

        Args:
            energy_values (List[float]): Energy values

        Returns:
            float: Negative absolute energy penalty value
        """
        energy_penalty = -sum(energy_values)
        return energy_penalty

    def _get_ITE_penalty(self, ITE_values: List[float]) -> float:
        ITE_penalty = -sum(ITE_values)
        return ITE_penalty

    def _get_comfort_penalty(self, temp_violations: List[float]) -> float:
        """Calculate comfort penalty using sqrt to dampen extreme violations.

        sqrt preserves monotonic gradient (higher T = worse) but prevents
        extreme values from destabilizing the critic network during training.

        Example: linear 10°C violation = -10, sqrt = -3.16

        Args:
            temp_violations (List[float]): Temperature violation values (positive, °C)

        Returns:
            float: Negative comfort penalty value
        """
        import math
        comfort_penalty = -sum(math.sqrt(v) for v in temp_violations)
        return comfort_penalty

    def _get_reward(self, energy_penalty: float, ITE_penalty: float,
                    comfort_penalty: float) -> Tuple[float, float, float]:
        """It calculates reward value using the negative absolute comfort and energy penalty calculates previously.

        Args:
            energy_penalty (float): Negative absolute energy penalty value.
            ITE_penalty (float): Negative ITE use penalty value.
            comfort_penalty (float): Negative absolute comfort penalty value.

        Returns:
            Tuple[float,float,float]: total reward calculated, reward term for energy, reward term for comfort.
        """
        # M2-E3b-v4 P3b (2026-04-23): 除零保护，ITE_penalty=0 时用 sign-preserving eps
        # （EnergyPlus 极端边界可能 ITE 全 0，避免 NaN 传播到 critic）
        ite_denom = ITE_penalty if abs(ITE_penalty) > 1e-6 else -1e-6
        energy_term = self.lambda_energy * self.W_energy * -energy_penalty / ite_denom
        comfort_term = self.lambda_temp * \
            (1 - self.W_energy ) * comfort_penalty
        reward = energy_term + comfort_term
        return reward, energy_term, comfort_term

class Grid_Reward(BaseReward):

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        carbon_variables: List[str],
        ITE_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        summer_start: Tuple[int, int] = (6, 1),
        summer_final: Tuple[int, int] = (9, 30),
        energy_weight: float = 1/3,
        ITE_weight: float = 1/3,
        lambda_energy: float = 1.0,
        lambda_ITE: float = 1.0,
        lambda_temperature: float = 1.0
    ):

        super(Grid_Reward, self).__init__()

        # Name of the variables
        self.temp_names = temperature_variables
        self.energy_names = energy_variables
        self.carbon_names = carbon_variables
        self.ITE_names = ITE_variables

        # Reward parameters
        self.range_comfort_winter = range_comfort_winter
        self.range_comfort_summer = range_comfort_summer
        self.W_energy = energy_weight
        self.W_ITE = ITE_weight
        self.lambda_energy = lambda_energy
        self.lambda_ITE = lambda_ITE
        self.lambda_temp = lambda_temperature

        # Summer period
        self.summer_start = summer_start  # (month,day)
        self.summer_final = summer_final  # (month,day)

        self.logger.info('Reward function initialized.')

    def __call__(self, obs_dict: Dict[str, Any]
                 ) -> Tuple[float, Dict[str, Any]]:
        """Calculate the reward function.

        Args:
            obs_dict (Dict[str, Any]): Dict with observation variable name (key) and observation variable value (value)

        Returns:
            Tuple[float, Dict[str, Any]]: Reward value and dictionary with their individual components.
        """
        # Check variables to calculate reward are available
        try:
            assert all(temp_name in list(obs_dict.keys())
                       for temp_name in self.temp_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the temperature variables specified are not present in observation.')
            raise err
        try:
            assert all(energy_name in list(obs_dict.keys())
                       for energy_name in self.energy_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise
        try:
            assert all(carbon_name in list(obs_dict.keys())
                       for carbon_name in self.carbon_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise
        try:
            assert all(ITE_name in list(obs_dict.keys())
                       for ITE_name in self.ITE_names)
        except AssertionError as err:
            self.logger.error(
                'Some of the energy variables specified are not present in observation.')
            raise err

        # Energy calculation
        energy_consumed, energy_values = self._get_energy_consumed(obs_dict)
        energy_penalty = self._get_energy_penalty(energy_values)

        # Comfort violation calculation
        total_temp_violation, temp_violations = self._get_temperature_violation(
            obs_dict)
        comfort_penalty = self._get_comfort_penalty(temp_violations)

        # ITE utilization calculation
        ITE_used, ITE_values = self._get_ITE_used(obs_dict)
        ITE_penalty = self._get_ITE_penalty(ITE_values)

        # Weighted sum of all terms
        reward, energy_term, ITE_term, comfort_term = self._get_reward(
            energy_penalty, ITE_penalty, comfort_penalty)

        reward_terms = {
            'energy_term': energy_term,
            'ITE_term': ITE_term,
            'comfort_term': comfort_term,
            'reward_weight_1': self.W_energy,
            'reward_weight_2': self.W_ITE,
            'abs_energy_penalty': energy_penalty,
            'abs_ITE_penalty': ITE_penalty,
            'abs_comfort_penalty': comfort_penalty,
            'total_power_demand': energy_consumed,
            'total_ITE_used': ITE_used,
            'total_temperature_violation': total_temp_violation
        }

        return reward, reward_terms

    def _get_energy_consumed(self, obs_dict: Dict[str,
                                                  Any]) -> Tuple[float,
                                                                 List[float]]:
        """Calculate the total energy consumed in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        energy_values = [
            v for k, v in obs_dict.items() if k in self.energy_names]
        carbon_values = [
            v for k, v in obs_dict.items() if k in self.carbon_names]
        ITE_values = [
            v for k, v in obs_dict.items() if k in self.ITE_names]

        # The total energy is the sum of energies
        for i in range (len(energy_values)):
            energy_values[i]=(energy_values[i]-ITE_values[i])*carbon_values[i]
        total_energy = sum(energy_values)

        return total_energy, energy_values

    def _get_ITE_used(self, obs_dict: Dict[str,
                                           Any]) -> Tuple[float,
                                                          List[float]]:
        """Calculate the total ITE used in the current observation.

        Args:
            obs_dict (Dict[str, Any]): Environment observation.

        Returns:
            Tuple[float, List[float]]: Total energy consumed (sum of variables) and List with energy consumed in each energy variable.
        """

        ITE_values = [
            v for k, v in obs_dict.items() if k in self.ITE_names]
        # The total energy is the sum of energies

        total_ITE = sum(ITE_values)

        return total_ITE, ITE_values

    def _get_temperature_violation(
            self, obs_dict: Dict[str, Any]) -> Tuple[float, List[float]]:
        """Calculate the total temperature violation (ºC) in the current observation.

        Returns:
            Tuple[float, List[float]]: Total temperature violation (ºC) and list with temperature violation in each zone.
        """

        month = obs_dict['month']
        day = obs_dict['day_of_month']
        year = YEAR
        current_dt = datetime(int(year), int(month), int(day))

        # Periods
        summer_start_date = datetime(
            int(year),
            self.summer_start[0],
            self.summer_start[1])
        summer_final_date = datetime(
            int(year),
            self.summer_final[0],
            self.summer_final[1])

        if current_dt >= summer_start_date and current_dt <= summer_final_date:
            temp_range = self.range_comfort_summer
        else:
            temp_range = self.range_comfort_winter

        temp_values = [
            v for k, v in obs_dict.items() if k in self.temp_names]
        total_temp_violation = 0.0
        temp_violations = []
        for T in temp_values:
            if T < temp_range[0] or T > temp_range[1]:
                temp_violation = min(
                    abs(temp_range[0] - T), abs(T - temp_range[1]))
                temp_violations.append(temp_violation)
                total_temp_violation += temp_violation

        return total_temp_violation, temp_violations

    def _get_energy_penalty(self, energy_values: List[float]) -> float:
        """Calculate the negative absolute energy penalty based on energy values

        Args:
            energy_values (List[float]): Energy values

        Returns:
            float: Negative absolute energy penalty value
        """
        energy_penalty = -sum(energy_values)
        return energy_penalty

    def _get_ITE_penalty(self, ITE_values: List[float]) -> float:
        ITE_penalty = -sum(ITE_values)
        return ITE_penalty

    def _get_comfort_penalty(self, temp_violations: List[float]) -> float:
        """Calculate the negative absolute comfort penalty based on temperature violation values

        Args:
            temp_violations (List[float]): Temperature violation values

        Returns:
            float: Negative absolute comfort penalty value
        """
        comfort_penalty = -sum(temp_violations)
        return comfort_penalty

    def _get_reward(self, energy_penalty: float, ITE_penalty: float,
                    comfort_penalty: float) -> Tuple[float, float, float]:
        """It calculates reward value using the negative absolute comfort and energy penalty calculates previously.

        Args:
            energy_penalty (float): Negative absolute energy penalty value.
            ITE_penalty (float): Negative ITE use penalty value.
            comfort_penalty (float): Negative absolute comfort penalty value.

        Returns:
            Tuple[float,float,float]: total reward calculated, reward term for energy, reward term for comfort.
        """
        energy_term = self.lambda_energy * self.W_energy * -energy_penalty/ITE_penalty
        ITE_term = self.lambda_ITE * self.W_ITE * ITE_penalty
        comfort_term = self.lambda_temp * \
            (1 - self.W_energy - self.W_ITE) * comfort_penalty
        reward = energy_term + ITE_term + comfort_term
        return reward, energy_term, ITE_term, comfort_term


class PUE_TES_Reward(PUE_Reward):
    """PUE reward for TES training.

    Inherits energy and sqrt comfort logic from PUE_Reward (M1 baseline).
    Adds two SOC penalty terms:
      - **Warning-zone quadratic**: soft gradient outside [soc_warn_low, soc_warn_high]
        buffer zone. NOT time-forward prediction; true lookahead deferred to M3
        with PV/price signals.
      - **Sharp soft barrier**: linear penalty inside soc_low/high band (near absolute limits)

    The parent class's ``lambda_temperature`` multiplier is used to scale the
    sqrt comfort penalty; raising it from 1.0 (E0.3 baseline) to 3.0 gives agent
    stronger signal to avoid zone overtemperature from TES over-discharge.
    """

    def __init__(
        self,
        temperature_variables: List[str],
        energy_variables: List[str],
        ITE_variables: List[str],
        range_comfort_winter: Tuple[int, int],
        range_comfort_summer: Tuple[int, int],
        soc_variable: str = 'TES_SOC',
        soc_low: float = 0.15,
        soc_high: float = 0.85,
        soc_warn_low: float = 0.30,
        soc_warn_high: float = 0.70,
        lambda_soc: float = 5.0,
        lambda_soc_warn: float = 3.0,
        **kwargs,
    ):
        super().__init__(
            temperature_variables=temperature_variables,
            energy_variables=energy_variables,
            ITE_variables=ITE_variables,
            range_comfort_winter=range_comfort_winter,
            range_comfort_summer=range_comfort_summer,
            **kwargs,
        )
        self.soc_variable = soc_variable
        self.soc_low = soc_low
        self.soc_high = soc_high
        self.soc_warn_low = soc_warn_low
        self.soc_warn_high = soc_warn_high
        self.lambda_soc = lambda_soc
        self.lambda_soc_warn = lambda_soc_warn

    def __call__(self, obs_dict: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        reward, terms = super().__call__(obs_dict)

        soc = obs_dict.get(self.soc_variable)
        if soc is None:
            terms['soc_penalty'] = 0.0
            terms['soc_warn_penalty'] = 0.0
            terms['soc_sharp_penalty'] = 0.0
            return reward, terms

        soc_val = float(soc)

        # Warning-zone quadratic penalty: soft gradient outside [soc_warn_low, soc_warn_high].
        # Normalized so penalty saturates at 1.0 * lambda_soc_warn when soc hits 0 (lower) or 1 (upper).
        if soc_val < self.soc_warn_low:
            norm = (self.soc_warn_low - soc_val) / max(self.soc_warn_low, 1e-6)
            warn_penalty = -norm ** 2 * self.lambda_soc_warn
        elif soc_val > self.soc_warn_high:
            norm = (soc_val - self.soc_warn_high) / max(1.0 - self.soc_warn_high, 1e-6)
            warn_penalty = -norm ** 2 * self.lambda_soc_warn
        else:
            warn_penalty = 0.0

        # Sharp soft barrier: linear penalty only when SOC is very close to physical limit
        if soc_val < self.soc_low:
            sharp_penalty = -(self.soc_low - soc_val) * self.lambda_soc
        elif soc_val > self.soc_high:
            sharp_penalty = -(soc_val - self.soc_high) * self.lambda_soc
        else:
            sharp_penalty = 0.0

        soc_penalty = warn_penalty + sharp_penalty
        reward = reward + soc_penalty
        terms['soc_penalty'] = soc_penalty
        terms['soc_warn_penalty'] = warn_penalty
        terms['soc_sharp_penalty'] = sharp_penalty
        terms['soc_value'] = soc_val
        return reward, terms


# ---------------------------------------------------------------------------
# M2 reward classes: RL-Cost and RL-Green (tech route §5.2 / §5.3)
# ---------------------------------------------------------------------------

# Cumulative days before each month (non-leap year, aligns with 8760 CSVs)
_DAYS_BEFORE_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def _hour_of_year(month: int, day: int, hour: int) -> int:
    """Map calendar triple → non-leap-year hour index ∈ [0, 8759]."""
    return (_DAYS_BEFORE_MONTH[int(month) - 1] + int(day) - 1) * 24 + int(hour)


class RL_Cost_Reward(PUE_TES_Reward):
    """M2 RL-Cost reward (tech route §5.2).

    Adds a cost term to the PUE+TES baseline:
        r = r_PUE_TES  - alpha * E_facility_MWh * price_usd_per_mwh
                       - beta  * comfort_penalty_extra   (optional multiplier)

    Note: the parent class already applies `lambda_temperature` to the comfort
    term; `beta` here acts as an *additional* multiplier on the parent's
    comfort_term. Set beta=1.0 to leave M1 comfort weighting unchanged, or
    raise it to tilt the agent toward comfort.
    """

    def __init__(
        self,
        temperature_variables,
        energy_variables,
        ITE_variables,
        range_comfort_winter,
        range_comfort_summer,
        price_series,
        alpha: float = 1e-6,
        beta: float = 1.0,
        kappa_shape: float = 2.0,
        gamma_pbrs: float = 0.99,
        **kwargs,
    ):
        super().__init__(
            temperature_variables=temperature_variables,
            energy_variables=energy_variables,
            ITE_variables=ITE_variables,
            range_comfort_winter=range_comfort_winter,
            range_comfort_summer=range_comfort_summer,
            **kwargs,
        )
        import numpy as np

        self.price_series = np.asarray(price_series, dtype=np.float32)
        if len(self.price_series) != 8760:
            raise ValueError(
                f"RL_Cost_Reward price_series must be 8760 hourly values, got {len(self.price_series)}"
            )
        self.alpha = float(alpha)
        self.beta = float(beta)

        # --- PBRS (analysis/pbrs_design_2026-04-23.md §4) -------------------
        # Ng-Harada-Russell potential shaping:
        #   Φ(s) = κ · (SOC(s) − 0.5) · (0.5 − price_norm(s))
        #   F(s,s') = γ · Φ(s') − Φ(s)
        # κ=2.0 bounds |Φ|≤0.5; γ=0.99 matches DSAC-T discount.
        #
        # IMPORTANT: obs_dict passed to __call__ is the RAW EnergyPlus dict
        # (see EplusEnv.step: self.reward_fn(obs)). Wrapper-added obs like
        # `price_current_norm` are appended to the obs ARRAY only, NOT to the
        # obs_dict. So we compute price_current_norm internally here, mirroring
        # the normalization in PriceSignalWrapper (z-score clipped to [-1, 2]).
        self.kappa_shape = float(kappa_shape)
        self.gamma_pbrs = float(gamma_pbrs)
        self._price_mean_phi = float(np.mean(self.price_series))
        self._price_std_phi = max(float(np.std(self.price_series)), 1e-6)
        # In [-1, 2] per PriceSignalWrapper; remap to [0, 1] for Φ. The linear
        # remap preserves monotonicity; 0.5 midpoint corresponds to z≈0.5
        # (slightly above mean), matching the "cheap-vs-dear" threshold.
        self._prev_phi = 0.0
        self._first_step = True

    def _lookup_price(self, obs_dict: Dict[str, Any]) -> float:
        m = obs_dict.get('month')
        d = obs_dict.get('day_of_month')
        h = obs_dict.get('hour')
        if m is None or d is None or h is None:
            return 0.0
        idx = _hour_of_year(m, d, h) % 8760
        return float(self.price_series[idx])

    def _energy_MWh(self, obs_dict: Dict[str, Any]) -> float:
        """Electricity:Facility meter is J accumulated over the last timestep.
        At 1 step/hour cadence, divide by 3.6e9 to get MWh."""
        e_joule = float(obs_dict.get(self.energy_names[0], 0.0))
        return e_joule / 3.6e9

    def _signal_norm(self, obs_dict: Dict[str, Any]) -> float:
        """Compute `price_current_norm` INTERNALLY (wrapper does not inject
        it into obs_dict — see docstring on self._prev_phi setup).

        Mirrors PriceSignalWrapper: z-score clipped to [-1, 2], then remapped
        to [0, 1] via (z+1)/3 so Φ midpoint aligns with mean price.
        """
        import numpy as np
        p = self._lookup_price(obs_dict)
        z = (p - self._price_mean_phi) / self._price_std_phi
        z_clipped = float(np.clip(z, -1.0, 2.0))
        # Remap [-1, 2] → [0, 1]; mean price (z=0) → 1/3
        return (z_clipped + 1.0) / 3.0

    def _phi(self, obs_dict: Dict[str, Any]) -> float:
        """PBRS potential: Φ = κ · (SOC − 0.5) · (0.5 − signal_norm).

        Positive when (high SOC & low price) or (low SOC & high price) —
        aligns with "charge cheap, discharge dear" under TOU.
        """
        soc = float(obs_dict.get(self.soc_variable, 0.5))
        sig = self._signal_norm(obs_dict)
        return self.kappa_shape * (soc - 0.5) * (0.5 - sig)

    def reset_episode(self) -> None:
        """Reset PBRS episode state. Called by EplusEnv.reset() if available."""
        self._prev_phi = 0.0
        self._first_step = True

    def __call__(self, obs_dict: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        import numpy as np

        reward, terms = super().__call__(obs_dict)

        price = self._lookup_price(obs_dict)
        mwh = self._energy_MWh(obs_dict)
        cost_usd = mwh * price
        cost_term_raw = -self.alpha * cost_usd
        # M2-E3b fix (Issue A, 2026-04-21): CAISO NP15 2023 price distribution has
        # kurtosis ≈ 120 (normal = 3) due to scarcity spikes (max = $1091/MWh vs
        # mean = $61) and ~1.6%/yr negative-price hours. These extreme tails
        # violate DSAC-T's Gaussian critic assumption, triggering variance
        # explosion (omega diverges) + SAC auto-temperature feedback → policy
        # collapse. ±3.0 clip preserves 99.9% of normal samples but bounds the
        # <0.1% pathological tails. `cost_term_raw` stashed for diagnostics.
        cost_term = float(np.clip(cost_term_raw, -3.0, 3.0))

        # beta scales parent's comfort_term as an extra multiplier (idempotent if beta=1)
        comfort_extra = (self.beta - 1.0) * terms.get('comfort_term', 0.0)

        reward = reward + cost_term + comfort_extra

        # --- PBRS: F = γ·Φ(s') − Φ(s_prev) ---------------------------------
        # First step of episode sets prev_phi via reset; first F is 0 (NHR
        # 1999 — any constant offset on Φ(s_0) is absorbed by γΦ telescoping).
        phi_s_prime = self._phi(obs_dict)
        if self._first_step:
            f_shape = 0.0
            self._first_step = False
        else:
            f_shape = self.gamma_pbrs * phi_s_prime - self._prev_phi
        self._prev_phi = phi_s_prime

        reward = reward + f_shape

        terms['cost_term'] = cost_term
        terms['cost_term_raw'] = cost_term_raw
        terms['cost_usd_step'] = cost_usd
        terms['mwh_step'] = mwh
        terms['lmp_usd_per_mwh'] = price
        terms['comfort_extra_term'] = comfort_extra
        terms['shaping_term'] = f_shape
        terms['phi_value'] = phi_s_prime
        return reward, terms


class RL_Green_Reward(RL_Cost_Reward):
    """M2 RL-Green reward (tech route §5.3).

    Uses a virtual effective price:
        c_eff(t) = min(c_market(t), c_pv)   when PV output > pv_threshold_kw
                 = c_market(t)              otherwise

    The virtual price is lower during PV hours (typically c_pv = 0 USD/MWh),
    so the energy charged in those hours contributes less to the cost term →
    agent learns to shift load toward PV peak.

    PV data is not injected into observation here (the PVSignalWrapper does
    that). This class only reads it as an exogenous series for the reward.
    """

    def __init__(
        self,
        temperature_variables,
        energy_variables,
        ITE_variables,
        range_comfort_winter,
        range_comfort_summer,
        price_series,
        pv_series,
        c_pv: float = 0.0,
        pv_threshold_kw: float = 100.0,
        alpha: float = 1e-6,
        beta: float = 1.0,
        **kwargs,
    ):
        super().__init__(
            temperature_variables=temperature_variables,
            energy_variables=energy_variables,
            ITE_variables=ITE_variables,
            range_comfort_winter=range_comfort_winter,
            range_comfort_summer=range_comfort_summer,
            price_series=price_series,
            alpha=alpha,
            beta=beta,
            **kwargs,
        )
        import numpy as np

        self.pv_series = np.asarray(pv_series, dtype=np.float32)
        if len(self.pv_series) != 8760:
            raise ValueError(
                f"RL_Green_Reward pv_series must be 8760 hourly values, got {len(self.pv_series)}"
            )
        self.c_pv = float(c_pv)
        self.pv_threshold_kw = float(pv_threshold_kw)

    def _lookup_pv(self, obs_dict: Dict[str, Any]) -> float:
        m = obs_dict.get('month')
        d = obs_dict.get('day_of_month')
        h = obs_dict.get('hour')
        if m is None or d is None or h is None:
            return 0.0
        idx = _hour_of_year(m, d, h) % 8760
        return float(self.pv_series[idx])

    def __call__(self, obs_dict: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        import numpy as np

        # Compute base reward with market price (super().__call__)
        reward, terms = super().__call__(obs_dict)

        # Swap the cost term from market-only to virtual-green.
        # M1 fix (2026-04-19): read energy directly from obs_dict instead of
        # reverse-dividing cost_usd_step by market_price — the latter silently
        # drops to 0 MWh when market_price == 0 (CAISO negative/near-zero price
        # hours, ~1.6%/yr), which would zero out new_cost_usd regardless of the
        # actual facility electricity.  `mwh_step` is also stashed by the parent
        # RL_Cost_Reward into `terms` so downstream consumers can reuse it.
        market_price = terms['lmp_usd_per_mwh']
        mwh = terms.get('mwh_step', self._energy_MWh(obs_dict))
        pv_kw = self._lookup_pv(obs_dict)

        if pv_kw > self.pv_threshold_kw:
            effective_price = min(market_price, self.c_pv)
        else:
            effective_price = market_price
        new_cost_usd = mwh * effective_price
        new_cost_term_raw = -self.alpha * new_cost_usd
        # M2-E3b fix (Issue A, 2026-04-21): mirror RL_Cost_Reward clip so the
        # virtual-green reward path has the same Gaussian-critic safety bound.
        # See RL_Cost_Reward.__call__ for full rationale.
        new_cost_term = float(np.clip(new_cost_term_raw, -3.0, 3.0))

        # Undo market cost, apply virtual-green cost.
        # Parent already applied clipped `cost_term`; subtract that same
        # clipped value so the net swap is consistent.
        old_cost_term = terms['cost_term']
        reward = reward - old_cost_term + new_cost_term

        terms['cost_term'] = new_cost_term
        terms['cost_term_raw'] = new_cost_term_raw
        terms['cost_usd_step'] = new_cost_usd
        terms['effective_price_usd_per_mwh'] = effective_price
        terms['pv_kw'] = pv_kw
        return reward, terms
