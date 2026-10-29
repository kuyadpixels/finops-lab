# Weekly Lambda that reports orphaned EBS volumes, old snapshots and idle Elastic IPs.
data "archive_file" "waste" {
  type        = "zip"
  source_file = "${path.module}/../../lambda/waste_finder/handler.py"
  output_path = "${path.module}/.build/waste_finder.zip"
}

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "waste" {
  name_prefix        = "${var.name_prefix}-waste-"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "waste_logs" {
  role       = aws_iam_role.waste.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "waste" {
  statement {
    sid       = "ReadInventory"
    actions   = ["ec2:DescribeVolumes", "ec2:DescribeSnapshots", "ec2:DescribeImages", "ec2:DescribeAddresses"]
    resources = ["*"]
  }
  statement {
    sid       = "DeleteOnlyApproved"
    actions   = ["ec2:DeleteVolume", "ec2:DeleteSnapshot", "ec2:ReleaseAddress"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "ec2:ResourceTag/finops:cleanup"
      values   = ["approved"]
    }
  }
  statement {
    sid       = "WriteReport"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.finops.arn}/waste-reports/*"]
  }
  statement {
    sid       = "Notify"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
}

resource "aws_iam_role_policy" "waste" {
  role   = aws_iam_role.waste.id
  policy = data.aws_iam_policy_document.waste.json
}

resource "aws_lambda_function" "waste" {
  function_name    = "${var.name_prefix}-waste-finder"
  role             = aws_iam_role.waste.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.waste.output_path
  source_code_hash = data.archive_file.waste.output_base64sha256
  timeout          = 120
  memory_size      = 256
  depends_on = [aws_cloudwatch_log_group.waste]
  environment {
    variables = {
      REGIONS               = join(",", var.waste_regions)
      DRY_RUN               = tostring(var.dry_run)
      SNAPSHOT_MAX_AGE_DAYS = tostring(var.snapshot_max_age_days)
      REPORT_BUCKET         = aws_s3_bucket.finops.bucket
      SNS_TOPIC_ARN         = aws_sns_topic.alerts.arn
    }
  }
}

resource "aws_cloudwatch_log_group" "waste" {
  name              = "/aws/lambda/${var.name_prefix}-waste-finder"
  retention_in_days = 14
}

resource "aws_cloudwatch_event_rule" "weekly" {
  name                = "${var.name_prefix}-waste-weekly"
  schedule_expression = "cron(0 1 ? * MON *)" # Monday 09:00 MYT
}

resource "aws_cloudwatch_event_target" "waste" {
  rule = aws_cloudwatch_event_rule.weekly.name
  arn  = aws_lambda_function.waste.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.waste.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly.arn
}
