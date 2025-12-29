provider "aws" {
  region = "us-east-1"
  # 我們已經設定好 aws configure，所以不需要在這裡寫 access key
}

# --- 1. 自動尋找最新的 Amazon Linux 2023 ---
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# --- 2. (新) 上傳鑰匙給 AWS ---
resource "aws_key_pair" "deployer" {
  key_name   = "my-terraform-key"       # 在 AWS 裡顯示的鑰匙名稱
  public_key = file("${path.module}/id_ed25519.pub") # 讀取您剛剛產生的公鑰檔案
}

# --- 3. (新) 設定警衛 (Security Group) ---
resource "aws_security_group" "allow_kafka_flink" {
  name        = "allow_kafka_flink"
  description = "Allow SSH, HTTP, Kafka, Flink"

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Flink Web UI
  ingress {
    from_port   = 8081
    to_port     = 8081
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Kafka Broker (外部連線用)
  ingress {
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- 4. 建立伺服器 (並綁定上面的鑰匙和警衛) ---
resource "aws_instance" "my_server" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.medium" # 強烈建議！t3.micro 記憶體太小跑不動 Java (Kafka+Flink)
  
  key_name      = aws_key_pair.deployer.key_name
  vpc_security_group_ids = [aws_security_group.allow_kafka_flink.id]

  # 讀取新的腳本
  user_data = file("${path.module}/scripts/deploy_aws.sh")
  user_data_replace_on_change = true 

  tags = {
    Name = "Kafka-Flink-Box"
  }
}

output "flink_ui" {
  value = "http://${aws_instance.my_server.public_ip}:8081"
}

output "kafka_broker" {
  value = "${aws_instance.my_server.public_ip}:9092"
}