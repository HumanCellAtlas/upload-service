import unittest
from unittest.mock import patch

from upload.common.retry import Retry

call_count = 0


class Exception1(RuntimeError):
    pass


class Exception2(RuntimeError):
    pass


def raise_a_series_of_different_exceptions():
    global call_count
    call_count += 1
    if call_count % 2 == 1:
        raise Exception1()
    else:
        raise Exception2()


class TestRetry(unittest.TestCase):

    def setUp(self):
        global call_count
        call_count = 0

    @staticmethod
    def _ignore_exception1(e):
        return e.__class__ == Exception1

    @patch('upload.common.retry.Retry.EXPONENTIAL_BACKOFF_FACTOR', 0.0001)  # Speed things up
    def test_if_ignoring_all_exceptions_then_we_hit_max_attempts(self):
        with self.assertRaises(Exception2):
            Retry(max_attempts=4).retry(raise_a_series_of_different_exceptions)
        self.assertEqual(4, call_count)

    @patch('upload.common.retry.Retry.EXPONENTIAL_BACKOFF_FACTOR', 0.0001)  # Speed things up
    def test_if_ignoring_exception1_it_is_swallowed_but_exception2_bubbles_up(self):
        with self.assertRaises(Exception2):
            Retry(ignore_exceptions_func=self._ignore_exception1).retry(raise_a_series_of_different_exceptions)
        self.assertEqual(2, call_count)
