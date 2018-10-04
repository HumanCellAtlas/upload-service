from upload.common.logging import get_logger
from upload.lambdas.health_check.health_check import HealthCheck

logger = get_logger(__name__)


def health_check(event, context):
    HealthCheck().health_check()
