terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_ami" "ubuntu" {
  count       = var.ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_vpc" "foodie" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "aifoodie-vpc" }
}

resource "aws_internet_gateway" "foodie" {
  vpc_id = aws_vpc.foodie.id
  tags   = { Name = "aifoodie-igw" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.foodie.id
  cidr_block              = "10.20.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"
  tags                    = { Name = "aifoodie-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.foodie.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.foodie.id
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "web" {
  name        = "aifoodie-web"
  description = "SSH and HTTP/API access"
  vpc_id      = aws_vpc.foodie.id
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "aifoodie-web-sg" }
}

resource "aws_instance" "app" {
  ami                    = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu[0].id
  instance_type          = var.instance_type
  key_name               = var.key_name
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]
  user_data              = <<-EOF
    #!/bin/bash
    set -eux
    apt-get update
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    usermod -aG docker ubuntu
    systemctl enable --now docker
  EOF
  tags = { Name = "aifoodie-app" }
}
