import json
import os

from proforma import CompositeComponent
from proforma.aws import ComputeEnvironment, JobQueue, Policy, IAMRole


class BatchValidationComputeEnvironment(ComputeEnvironment):
    def __init__(self, **options):
        options.update({
            'compute_source': 'SPOT',
        })
        super().__init__(name=f"dcp-upload-validation-cluster-{os.environ['DEPLOYMENT_STAGE']}", **options)


class BatchValidationJobQueue(JobQueue):
    def __init__(self, **options):
        compute_env = BatchValidationComputeEnvironment(quiet=True)
        compute_env.is_setup()  # load arn
        super().__init__(
            name=f"dcp-upload-validation-q-{os.environ['DEPLOYMENT_STAGE']}",
            compute_env_arn=compute_env.arn,
            **options
        )


class BatchValidationJobPolicy(Policy):
    def __init__(self, **options):
        options.update(
            name=f"dcp-upload-validation-job-{os.environ['DEPLOYMENT_STAGE']}",
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


class BatchValidationJobRole(IAMRole):
    def __init__(self, **options):
        options.update(
            name=f"dcp-upload-validation-job-{os.environ['DEPLOYMENT_STAGE']}",
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
            attach_policies=[BatchValidationJobPolicy(quiet=True).arn]
        )
        super().__init__(**options)


class BatchValidation(CompositeComponent):

    SUBCOMPONENTS = {
        'cenv': BatchValidationComputeEnvironment,
        'jobq': BatchValidationJobQueue,
        'policy': BatchValidationJobPolicy,
        'role': BatchValidationJobRole
    }

    def __str__(self):
        return "Validation:"
