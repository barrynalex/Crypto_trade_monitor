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
resource "aws_security_group" "allow_ssh_web" {
  name        = "allow_ssh_web"
  description = "Allow SSH and HTTP traffic"

  # 允許 SSH (Port 22) - 讓您可以登入
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # 0.0.0.0/0 代表允許全世界連入 (練習方便，正式環境建議鎖 IP)
  }

  # 允許 HTTP (Port 80) - 假設未來要架網站
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # 允許所有外連流量 (Egress) - 讓伺服器可以上網更新軟體
  # 如果沒加這段，伺服器會變成斷網狀態
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # -1 代表所有協定
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- 4. 建立伺服器 (並綁定上面的鑰匙和警衛) ---
resource "aws_instance" "my_server" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.micro"

  # 綁定鑰匙
  key_name = aws_key_pair.deployer.key_name

  # 綁定 Security Group (注意這裡是用 ID)
  vpc_security_group_ids = [aws_security_group.allow_ssh_web.id]

  tags = {
    Name = "My-Level2-Server"
  }
}

# --- 5. (新) Output: 告訴我 IP 是多少 ---
output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.my_server.public_ip
}