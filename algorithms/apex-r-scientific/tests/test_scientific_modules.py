import math
import unittest

from apex_r.contracts import GateStatus
from apex_r.modules.hemodynamics import (
    WK2Parameters,
    equilibrium_pressure,
    pressure_derivative,
    simulate_wk2,
)
from apex_r.modules.identifiability import matrix_rank, validate_linear_design
from apex_r.modules.molecular import (
    calibrate_linear,
    delta_g_from_kd,
    kd_from_delta_g,
    kd_from_pkd,
    pkd_from_kd,
)
from apex_r.modules.pbpk import derivative, validate_mass_balance


class MolecularTests(unittest.TestCase):
    def test_affinity_round_trip_and_sign(self):
        kd = 1e-9
        delta_g = delta_g_from_kd(kd)
        self.assertLess(delta_g, 0)
        self.assertAlmostEqual(kd_from_delta_g(delta_g), kd, places=20)
        self.assertAlmostEqual(kd_from_pkd(pkd_from_kd(kd)), kd, places=20)

    def test_linear_calibration_recovers_coefficients(self):
        model = calibrate_linear([0, 1, 2, 3], [2, 5, 8, 11])
        self.assertAlmostEqual(model.intercept, 2)
        self.assertAlmostEqual(model.slope, 3)
        self.assertAlmostEqual(model.r_squared, 1)
        self.assertEqual(model.n, 4)


class IdentifiabilityTests(unittest.TestCase):
    def test_full_rank_design_passes(self):
        matrix = [[1, 0], [1, 1], [1, 2]]
        self.assertEqual(matrix_rank(matrix), 2)
        self.assertEqual(validate_linear_design(matrix).status, GateStatus.PASSED)

    def test_collinear_design_fails(self):
        matrix = [[1, 2], [2, 4], [3, 6]]
        self.assertEqual(validate_linear_design(matrix).status, GateStatus.FAILED)


class HemodynamicsTests(unittest.TestCase):
    def test_equilibrium_has_zero_derivative(self):
        params = WK2Parameters(resistance=2.0, compliance=1.5, venous_pressure=5.0)
        pressure = equilibrium_pressure(4.0, params)
        self.assertAlmostEqual(pressure, 13.0)
        self.assertAlmostEqual(pressure_derivative(pressure, 4.0, params), 0.0)

    def test_rk4_converges_to_constant_flow_equilibrium(self):
        params = WK2Parameters(resistance=2.0, compliance=1.0)
        _, pressures = simulate_wk2(0.0, 5.0, params, duration=20.0, dt=0.05)
        self.assertTrue(math.isclose(pressures[-1], 10.0, rel_tol=1e-4))


class PbpkTests(unittest.TestCase):
    def test_internal_transfers_conserve_mass(self):
        amounts = [100.0, 20.0, 5.0]
        transfers = [[0, 0.2, 0.1], [0.05, 0, 0.03], [0.02, 0.04, 0]]
        rates = derivative(amounts, transfers)
        self.assertAlmostEqual(sum(rates), 0.0)
        self.assertEqual(validate_mass_balance(amounts, transfers).status, GateStatus.PASSED)

    def test_elimination_and_input_are_accounted_for(self):
        gate = validate_mass_balance(
            [10.0, 2.0], [[0, 0.5], [0.25, 0]], [0.1, 0.2], [3.0, 0.0]
        )
        self.assertEqual(gate.status, GateStatus.PASSED)


if __name__ == "__main__":
    unittest.main()
