output "public_ip" {
  value = aws_instance.app.public_ip
}
output "public_dns" {
  value = aws_instance.app.public_dns
}
output "security_group_id" {
  value = aws_security_group.web.id
}
output "vpc_id" {
  value = aws_vpc.foodie.id
}
