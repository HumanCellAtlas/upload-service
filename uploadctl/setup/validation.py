import json
import os

from .component import CompositeComponent
from .aws.batch import ComputeEnvironment, JobQueue
from .aws.iam import Policy, IAMRole


class ValidationComputeEnvironment(ComputeEnvironment):
    def __init__(self, **options):
        super().__init__(name=f"dcp-upload-{os.environ['DEPLOYMENT_STAGE']}", **options)


class ValidationJobQueue(JobQueue):
    def __init__(self, **options):
        compute_env = ValidationComputeEnvironment(quiet=True)
        compute_env.is_setup()  # load arn
        super().__init__(
            name=f"dcp-upload-queue-{os.environ['DEPLOYMENT_STAGE']}",
            compute_env_arn=compute_env.arn,
            **options
        )


class ValidationJobPolicy(Policy):
    def __init__(self, **options):
        options.update(
            name=f"upload-batch-job-{os.environ['DEPLOYMENT_STAGE']}",
            document=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObject"
                            ],
                            "Resource": [
                                f"arn:aws:s3:::{os.environ['BUCKET_NAME']}/*"
                            ]
                        }
                    ]
                }
            )
        )
        super().__init__(**options)


class ValidationJobRole(IAMRole):
    def __init__(self, **options):
        options.update(
            name=f"upload-batch-job-{os.environ['DEPLOYMENT_STAGE']}",
            trust_document=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "ecs-tasks.amazonaws.com"
                            },
                            "Action": "sts:AssumeRole"
                        },
                        {
                            "Sid": "",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "lambda.amazonaws.com"
                            },
                            "Action": "sts:AssumeRole"
                        }
                    ]
                }
            ),
            attach_policies=[ValidationJobPolicy(quiet=True).arn]
        )
        super().__init__(**options)


class Validation(CompositeComponent):

    SUBCOMPONENTS = {
        'cenv': ValidationComputeEnvironment,
        'jobq': ValidationJobQueue,
        'policy': ValidationJobPolicy,
        'role': ValidationJobRole
    }

    def __str__(self):
        return "Validation:"
