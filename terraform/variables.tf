variable "aws_region" {
  type    = string
  default = "ap-south-1"
}
variable "instance_type" {
  type    = string
  default = "t3.small"
}
variable "key_name" {
  type        = string
  description = "Existing AWS EC2 key pair name"
}
variable "allowed_ssh_cidr" {
  type        = string
  description = "Trusted client CIDR, such as 203.0.113.10/32"
}
variable "ami_id" {
  type        = string
  default     = ""
  description = "Optional Ubuntu 22.04 AMI override for ap-south-1"
}
