output "bucket" {
  description = "Point the FOCUS data export here, with S3 prefix 'focus'."
  value       = aws_s3_bucket.finops.bucket
}

output "athena_workgroup" {
  value = aws_athena_workgroup.finops.name
}

output "glue_crawler" {
  value = aws_glue_crawler.focus.name
}

output "waste_finder_function" {
  value = aws_lambda_function.waste.function_name
}
