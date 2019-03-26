resource "aws_ecs_task_definition" "pgbouncer" {
  family                = "upload-service-pgbouncer-${var.deployment_stage}"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn = "${aws_iam_role.task_executor.arn}"
  task_role_arn = "${aws_iam_role.pgbouncer.arn}"
  container_definitions = <<DEFINITION
[
  {
    "portMappings": [
      {
        "hostPort": 5432,
        "protocol": "tcp",
        "containerPort": 5432
      }
    ],
    "environment": [
      {
        "name": "DATABASE_URL",
        "value": "postgresql://${var.db_username}:${var.db_password}@${aws_rds_cluster.upload.endpoint}/upload_${var.deployment_stage}"
      },
      {
        "name": "DEFAULT_POOL_SIZE",
        "value": "100"
      },
      {
        "name": "MIN_POOL_SIZE",
        "value": "20"
      },
      {
        "name": "MAX_CLIENT_CONN",
        "value": "4000"
      },
      {
        "name": "POOL_MODE",
        "value": "transaction"
      }
    ],
    "ulimits": [
      {
        "softLimit": 4100,
        "hardLimit": 4100,
        "name": "nofile"
      }
    ],
    "memory": 1024,
    "cpu": 512,
    "image": "humancellatlas/pgbouncer:1",
    "name": "pgbouncer-${var.deployment_stage}",
    "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${aws_cloudwatch_log_group.pgbouncer.name}",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
    }
  }
]
DEFINITION
  network_mode          = "awsvpc"
  cpu                   = "512"
  memory                = "1024"
}

resource "aws_cloudwatch_log_group" "pgbouncer" {
  name              = "/aws/service/upload-service-pgbouncer-${var.deployment_stage}"
  retention_in_days = 1827
}

resource "aws_iam_role" "task_executor" {
  name = "upload-service-PgbouncerTaskExecutionRole-${var.deployment_stage}"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "ecs.amazonaws.com",
          "ecs-tasks.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "task_executor_ecs" {
  role = "${aws_iam_role.task_executor.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "pgbouncer" {
  name = "upload-service-pgbouncer-${var.deployment_stage}"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "ecs-tasks.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy" "pgbouncer" {
  name = "upload-service-pgbouncer-policy-${var.deployment_stage}"
  role = "${aws_iam_role.pgbouncer.id}"
  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "${aws_cloudwatch_log_group.pgbouncer.arn}:*",
            "Effect": "Allow"
        },
        {
            "Effect": "Allow",
            "Action": "logs:CreateLogGroup",
            "Resource": "${aws_cloudwatch_log_group.pgbouncer.arn}"
        }
    ]
}
EOF
}

resource "aws_ecs_cluster" "pgbouncer" {
  name = "upload-service-pgbouncer-${var.deployment_stage}"
}

resource "aws_ecs_service" "pgbouncer" {
  name            = "upload-service-pgbouncer-${var.deployment_stage}"
  cluster         = "${aws_ecs_cluster.pgbouncer.id}"
  task_definition = "${aws_ecs_task_definition.pgbouncer.arn}"
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    security_groups = ["${aws_security_group.rds-postgres.id}"]
    subnets         = ["${var.pgbouncer_subnet_id}"]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = "${aws_lb_target_group.pgbouncer.id}"
    container_name   = "pgbouncer-${var.deployment_stage}"
    container_port   = "5432"
  }

  depends_on = [
    "aws_lb_listener.front_end", "aws_rds_cluster_instance.cluster_instances"
  ]
}

resource "aws_lb_listener" "front_end" {
  load_balancer_arn = "${aws_lb.main.id}"
  port              = "5432"
  protocol          = "TCP"

  default_action {
    target_group_arn = "${aws_lb_target_group.pgbouncer.id}"
    type             = "forward"
  }

}

resource "aws_lb" "main" {
  name            = "upload-pgbouncer-${var.deployment_stage}"
  subnets         = ["${var.lb_subnet_ids}"]
  load_balancer_type = "network"
  internal           = false
}

resource "aws_lb_target_group" "pgbouncer" {
  name        = "upload-pgbouncer-${var.deployment_stage}"
  port        = "5432"
  protocol    = "TCP"
  vpc_id      = "${var.vpc_id}"
  target_type = "ip"
  lifecycle {
     ignore_changes = "lambda_multi_value_headers_enabled"
   }
}
