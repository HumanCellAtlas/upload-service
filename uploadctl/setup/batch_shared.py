import json

from proforma import CompositeComponent, ExternalControl
from proforma.aws import IAMRole, ServiceLinkedRole, InstanceProfile, InstanceProfileRoleAttachment


class EcsInstanceRole(IAMRole):
    def __init__(self, **options):
        options.update(
            name="ecsInstanceRole",
            trust_document=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "ec2.amazonaws.com"
                            },
                            "Action": "sts:AssumeRole"
                        }
                    ]
                }
            ),
            attach_policies=["arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"]
        )
        super().__init__(**options)

    def tear_it_down(self):
        raise ExternalControl("Won't delete, this is shared between deployments.")


class EcsInstanceProfile(InstanceProfile):
    def __init__(self, **options):
        options.update(name='ecsInstanceRole')
        super().__init__(**options)

    def tear_it_down(self):
        raise ExternalControl("Won't delete, this is shared between deployments.")


class EcsInstanceProfileRoleAttachment(InstanceProfileRoleAttachment):
    def __init__(self, **options):
        options.update(instance_profile_name='ecsInstanceRole', role_name='ecsInstanceRole')
        super().__init__(**options)


class AWSBatchServiceRole(IAMRole):
    def __init__(self, **options):
        options.update(
            name="AWSBatchServiceRole",
            trust_document=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "batch.amazonaws.com"
                            },
                            "Action": "sts:AssumeRole"
                        }
                    ]
                }
            ),
            attach_policies=["arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"]
        )
        super().__init__(**options)

    def tear_it_down(self):
        raise ExternalControl("Won't delete, this is shared between deployments.")


class AmazonEC2SpotFleetRole(IAMRole):
    def __init__(self, **options):
        options.update(
            name="AmazonEC2SpotFleetRole",
            trust_document=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "spotfleet.amazonaws.com"
                            },
                            "Action": "sts:AssumeRole"
                        }
                    ]
                }
            ),
            attach_policies=['arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetRole']
        )
        super().__init__(**options)

    def tear_it_down(self):
        raise ExternalControl("Won't delete, this is shared between deployments.")


class AWSServiceRoleForEC2Spot(ServiceLinkedRole):
    def __init__(self, **options):
        options.update(
            name="AWSServiceRoleForEC2Spot",
            aws_service_name="spot.amazonaws.com")
        super().__init__(**options)

    def tear_it_down(self):
        raise ExternalControl("Won't delete, this is shared between deployments.")


class AWSServiceRoleForEC2SpotFleet(ServiceLinkedRole):
    def __init__(self, **options):
        options.update(
            name="AWSServiceRoleForEC2SpotFleet",
            aws_service_name="spotfleet.amazonaws.com")
        super().__init__(**options)

    def tear_it_down(self):
        raise ExternalControl("Won't delete, this is shared between deployments.")


class BatchSharedConfig(CompositeComponent):

    SUBCOMPONENTS = {
        'ecsInstanceRole': EcsInstanceRole,
        'ecsInstanceProfile': EcsInstanceProfile,
        'EcsInstanceProfileRoleAttachment': EcsInstanceProfileRoleAttachment,
        'AWSBatchServiceRole': AWSBatchServiceRole,
        'AmazonEC2SpotFleetRole': AmazonEC2SpotFleetRole,
        'AWSServiceRoleForEC2Spot': AWSServiceRoleForEC2Spot,
        'AWSServiceRoleForEC2SpotFleet': AWSServiceRoleForEC2SpotFleet
    }

    def __str__(self):
        return "Batch shared config:"
