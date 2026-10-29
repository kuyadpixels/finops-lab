variable "region" {
  description = "Region for the lab resources (bucket, Athena, Lambda)."
  type        = string
  default     = "ap-southeast-1"
}

variable "name_prefix" {
  type    = string
  default = "finops-lab"
}

variable "owner" {
  description = "Value for the Owner tag on everything this lab creates."
  type        = string
}

variable "alert_email" {
  description = "Email for budget, anomaly and waste alerts (confirm the SNS email after apply)."
  type        = string
}

variable "monthly_budget_usd" {
  type    = number
  default = 50
}

variable "anomaly_threshold_usd" {
  description = "Alert when an anomaly's total impact is at least this many USD."
  type        = number
  default     = 10
}

variable "required_tags" {
  description = "Tag keys every resource must carry (used by the Config rule)."
  type        = list(string)
  default     = ["CostCenter", "Environment", "Owner"]
}

variable "enable_config_rule" {
  description = "Create the AWS Config required-tags rule. Needs a Config recorder already running in this Region, and Config bills per evaluation."
  type        = bool
  default     = false
}

variable "waste_regions" {
  description = "Regions the waste finder scans."
  type        = list(string)
  default     = ["ap-southeast-1", "ap-southeast-5"]
}

variable "dry_run" {
  description = "true = report only. false = delete resources tagged finops:cleanup=approved."
  type        = bool
  default     = true
}

variable "snapshot_max_age_days" {
  type    = number
  default = 90
}
