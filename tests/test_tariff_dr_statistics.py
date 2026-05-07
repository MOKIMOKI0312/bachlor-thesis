import pytest

from mpc_v2.core.io_schemas import UnsupportedFeatureError
from mpc_v2.scripts.generate_china_matrix import main as generate_china_matrix_main
from mpc_v2.scripts.generate_result_reports import main as generate_result_reports_main


def test_old_china_matrix_generator_fails_explicitly():
    with pytest.raises(UnsupportedFeatureError, match="deferred"):
        generate_china_matrix_main([])


def test_old_advanced_report_generator_fails_explicitly():
    with pytest.raises(UnsupportedFeatureError, match="deferred"):
        generate_result_reports_main([])
