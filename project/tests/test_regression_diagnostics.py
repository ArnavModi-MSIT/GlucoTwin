import unittest
import numpy as np
from glucotwin.regression_diagnostics import error_summary,sliced_errors,select_guarded


class RegressionDiagnosticsTests(unittest.TestCase):
    def test_delta_and_level_errors_are_identical(self):
        current=np.array([50.,100.,250.]);future=np.array([80.,140.,180.]);delta=np.array([20.,30.,-60.])
        np.testing.assert_allclose(current+delta-future,delta-(future-current))
        self.assertEqual(error_summary(future,current+delta)['rmse'],error_summary(future-current,delta)['rmse'])

    def test_tail_metrics_and_slice_denominators(self):
        actual=np.array([60.,100.,200.]);predicted=np.array([10.,101.,270.])
        result=sliced_errors(actual,predicted)
        self.assertEqual(result['low']['n'],1);self.assertEqual(result['high']['n'],1)
        self.assertEqual(result['all']['fraction_error_gt40'],2/3)
        self.assertEqual(result['all']['fraction_error_gt60'],1/3)
        self.assertEqual(error_summary([],[])['mae'],None)

    def test_missing_slice_support_prevents_promotion(self):
        actual=np.array([100.,110.])
        rows=lambda p:[{'diagnostics':sliced_errors(actual,p)}]
        chosen,decisions=select_guarded({'ridge_original':rows([101.,111.]),'candidate':rows(actual)},
                                      {'minimum_slice_rows':30,'maximum_relative_worsening':0})
        self.assertEqual(chosen,'ridge_original');self.assertFalse(decisions['candidate']['meets_guardrails'])

    def test_worse_rmse_rejects_lower_mae(self):
        actual=np.array([60.,100.,200.,220.]);rows=lambda p:[{'diagnostics':sliced_errors(actual,p)}]
        chosen,decisions=select_guarded({'ridge_original':rows(actual+10),'candidate':rows(actual+np.array([0.,0.,0.,35.]))},
                                      {'minimum_slice_rows':1,'maximum_relative_worsening':0})
        self.assertEqual(chosen,'ridge_original');self.assertIn('all rmse worsened',decisions['candidate']['reasons'])
