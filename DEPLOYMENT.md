# RFP Analyzer Deployment Guide

This guide provides detailed instructions for deploying the RFP Analyzer application to an Amazon EC2 instance using Docker and MongoDB for authentication.

## Prerequisites

1. An Amazon EC2 instance with:
   - Amazon Linux 2023 or Ubuntu Server 20.04 LTS or later
   - Minimum t2.medium instance type (recommended for processing PDFs)
   - At least 20GB of disk space
   - A security group that allows inbound traffic on ports 22 (SSH), 80 (HTTP), and 443 (HTTPS)

2. Optional: A domain name pointing to your EC2 instance's public IP address
   - You can use your EC2's public DNS (e.g., ec2-xx-xx-xx-xx.compute-1.amazonaws.com) instead

3. A MongoDB database:
   - You can use MongoDB Atlas (cloud-hosted)
   - Or set up your own MongoDB server

4. OpenAI API key

## Deployment Options

### Option 1: Automated Deployment

Use the provided deployment script:

1. Edit the configuration variables in `deploy_to_ec2.sh`:
   ```bash
   EC2_HOST="your-ec2-host-ip-or-domain"
   EC2_USER="ec2-user"  # for Amazon Linux or "ubuntu" for Ubuntu
   SSH_KEY="path/to/your-ssh-key.pem"
   REPOSITORY="https://github.com/yourusername/RFPExtractor.git"
   ```

2. Run the deployment script:
   ```bash
   chmod +x deploy_to_ec2.sh
   ./deploy_to_ec2.sh
   ```

3. SSH into your EC2 instance to configure the environment variables:
   ```bash
   ssh -i your-ssh-key.pem ec2-user@your-ec2-host
   cd rfp-analyzer
   nano .env
   ```

4. Optional - If you have a domain name and want to set up SSL:
   ```bash
   # For Ubuntu
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   
   # For Amazon Linux 2023
   sudo dnf install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```

### Option 2: Manual Deployment

#### For Ubuntu:

1. SSH into your EC2 instance:
   ```bash
   ssh -i your-ssh-key.pem ubuntu@your-ec2-host
   ```

2. Install Docker and Docker Compose:
   ```bash
   sudo apt update
   sudo apt install apt-transport-https ca-certificates curl software-properties-common
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
   sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
   sudo apt update
   sudo apt install docker-ce
   sudo usermod -aG docker ${USER}
   sudo curl -L "https://github.com/docker/compose/releases/download/v2.14.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

3. Install Nginx:
   ```bash
   sudo apt install nginx
   ```

#### For Amazon Linux 2023:

1. SSH into your EC2 instance:
   ```bash
   ssh -i your-ssh-key.pem ec2-user@your-ec2-host
   ```

2. Install Docker and Docker Compose:
   ```bash
   sudo dnf update -y
   sudo dnf install -y docker
   sudo systemctl enable docker
   sudo systemctl start docker
   sudo usermod -aG docker ${USER}
   
   # Get the latest compose version
   COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
   sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
   ```

3. Install Nginx:
   ```bash
   sudo dnf install -y nginx
   sudo systemctl enable nginx
   sudo systemctl start nginx
   ```

#### For both systems:

4. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/RFPExtractor.git rfp-analyzer
   cd rfp-analyzer
   ```

5. Create and configure the environment file:
   ```bash
   cp .env.template .env
   nano .env
   ```

6. Build and start the Docker containers:
   ```bash
   sudo docker-compose up -d
   ```

7. Configure Nginx:
   
   **For Ubuntu:**
   ```bash
   sudo cp nginx.conf /etc/nginx/sites-available/rfp_analyzer
   sudo ln -s /etc/nginx/sites-available/rfp_analyzer /etc/nginx/sites-enabled/
   sudo rm /etc/nginx/sites-enabled/default
   sudo nginx -t
   sudo systemctl reload nginx
   ```
   
   **For Amazon Linux 2023:**
   ```bash
   sudo cp nginx.conf /etc/nginx/conf.d/rfp_analyzer.conf
   # Edit the config file to use your EC2 hostname
   sudo sed -i "s/ec2-23-20-221-108.compute-1.amazonaws.com/$(curl -s http://169.254.169.254/latest/meta-data/public-hostname)/g" /etc/nginx/conf.d/rfp_analyzer.conf
   sudo nginx -t
   sudo systemctl reload nginx
   ```

8. Optional - If you have a domain, set up SSL:
   
   **For Ubuntu:**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```
   
   **For Amazon Linux 2023:**
   ```bash
   sudo dnf install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```

## Configuration

### Environment Variables

Edit the `.env` file with your configuration:

```
# MongoDB Configuration
MONGODB_URI=mongodb://username:password@mongodb_host:27017/rfp_analyzer
MONGODB_DB=rfp_analyzer

# OpenAI API Key
OPENAI_API_KEY=your-openai-api-key

# Initial Admin User
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=secure-password-here
ADMIN_NAME=System Administrator

# AWS Configuration (optional for S3/Lambda features)
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_DEFAULT_REGION=us-east-1
```

### Nginx Configuration

The default Nginx configuration is set up to work with your EC2's public DNS. If you want to use a domain name instead, edit the configuration file:

**For Ubuntu:**
```bash
sudo nano /etc/nginx/sites-available/rfp_analyzer
```

**For Amazon Linux 2023:**
```bash
sudo nano /etc/nginx/conf.d/rfp_analyzer.conf
```

Replace the `server_name` with your domain name or EC2 public DNS.

## Initial Setup

1. After deployment, access the application at your EC2 public DNS or domain name:
   - http://ec2-xx-xx-xx-xx.compute-1.amazonaws.com (or your domain)

2. Log in with the admin credentials specified in your `.env` file

3. You can now:
   - Create additional user accounts
   - Upload and analyze RFP documents
   - Use all features of the application

## Maintenance

### Updating the Application

1. SSH into your EC2 instance
2. Navigate to the application directory:
   ```bash
   cd rfp-analyzer
   ```
3. Pull the latest code:
   ```bash
   git pull origin main
   ```
4. Rebuild and restart the Docker containers:
   ```bash
   sudo docker-compose down
   sudo docker-compose build
   sudo docker-compose up -d
   ```

### Backup and Restore

#### MongoDB Backup

If using MongoDB Atlas, use their backup features.

For a self-hosted MongoDB:

```bash
mongodump --uri="mongodb://username:password@mongodb_host:27017/rfp_analyzer" --out=/path/to/backup/directory
```

#### MongoDB Restore

```bash
mongorestore --uri="mongodb://username:password@mongodb_host:27017/rfp_analyzer" /path/to/backup/directory
```

## Troubleshooting

### Viewing Logs

```bash
# Docker container logs
sudo docker-compose logs -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Common Issues

1. **Application not accessible**: Check Nginx configuration and Docker container status.
2. **Authentication failures**: Verify MongoDB connection string and credentials.
3. **RFP processing errors**: Check OpenAI API key and AWS credentials if using Lambda/S3.
4. **Nginx configuration differences**: Amazon Linux 2023 uses different paths than Ubuntu for Nginx configuration.

## Security Considerations

1. **API Keys**: Never commit API keys to the repository. Always use environment variables.
2. **Database Security**: Use strong passwords and restrict network access to your MongoDB instance.
3. **HTTPS**: Consider using HTTPS in production with valid SSL certificates (requires a domain name) or self-signed certificates.
4. **Regular Updates**: Keep the system, Docker, and application dependencies updated with security patches.
5. **Firewall**: Configure EC2 security groups to allow only necessary traffic.

## Using Without a Domain Name

You can use this application with just your EC2 instance's public DNS:

1. The deployment script automatically configures Nginx to use your EC2's public DNS 
2. Access your application at http://ec2-xx-xx-xx-xx.compute-1.amazonaws.com
3. For HTTPS without a domain, you'll need to:
   - Generate self-signed certificates
   - Update the nginx configuration to use these certificates
   - Note that browsers will show security warnings with self-signed certificates

To generate self-signed certificates:

```bash
# Create certificate directory
sudo mkdir -p /etc/nginx/ssl

# Generate self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/ssl/nginx.key -out /etc/nginx/ssl/nginx.crt

# Edit nginx config to uncomment the SSL section and use these certificates
sudo nano /etc/nginx/conf.d/rfp_analyzer.conf

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```