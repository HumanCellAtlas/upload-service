import logging
import time

import botocore

logger = logging.getLogger(__name__)


class Retry:

    EXPONENTIAL_BACKOFF_FACTOR = 1.618

    def __init__(self, max_attempts=None, ignore_exceptions_func=None):
        self.start_time = None
        self.attempt_number = 0
        self.backoff_seconds = 1.0
        self.max_attempts = max_attempts
        self.ignore_exceptions_matcher = ignore_exceptions_func

    def retry(self, func, *args, **kwargs):
        self.start_time = time.time()
        while True:
            try:
                self.attempt_number += 1
                retval = func(*args, **kwargs)
                if self.attempt_number > 1:
                    logger.debug("Function {func} attempt {attempt} succeeded after {duration} seconds total".format(
                        func=func, attempt=self.attempt_number, duration=int(time.time() - self.start_time)
                    ))
                return retval
            except Exception as e:
                logger.debug(f"Function {func} attempt {self.attempt_number} failed ({e.__class__})")
                if self.max_attempts and self.attempt_number >= self.max_attempts:
                    raise e
                if self.ignore_exceptions_matcher:  # Ignore some exceptions
                    if self.ignore_exceptions_matcher(e):
                        logger.debug(f"Ignoring {e}")
                    else:
                        raise e
                else:  # Ignore all exceptions
                    pass
                self._back_off()

    def _back_off(self):
        time.sleep(self.backoff_seconds)
        self.backoff_seconds = min(30.0, self.backoff_seconds * self.EXPONENTIAL_BACKOFF_FACTOR)


def retry_on_aws_too_many_requests(func):

    def ingore_exceptions_matcher(e):
        return e.__class__ == botocore.exceptions.ClientError and \
            e.response['Error']['Code'] == 'TooManyRequestsException'

    def wrapper(*args, **kwargs):
        return Retry(ignore_exceptions_func=ingore_exceptions_matcher, max_attempts=20).retry(func, *args, **kwargs)

    return wrapper
