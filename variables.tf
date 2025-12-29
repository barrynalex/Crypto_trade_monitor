variable "aws_access_key" {
  description = "AWS Access Key"
  type        = string
  sensitive   = true  # 標記為敏感資料，避免顯示在 Log 中
}

variable "aws_secret_key" {
  description = "AWS Secret Key"
  type        = string
  sensitive   = true
}