# RFP Analyzer Deployment Guide

This guide provides detailed instructions for deploying the RFP Analyzer application to an Amazon EC2 instance using Docker and MongoDB for authentication.

## Prerequisites

1. An Amazon EC2 instance with:
   - Ubuntu Server 20.04 LTS or later
   - Minimum t2.medium instance type (recommended for processing PDFs)
   - At least 20GB of disk space
   - A security group that allows inbound traffic on ports 22 (SSH), 80 (HTTP), and 443 (HTTPS)

2. A domain name pointing to your EC2 instance's public IP address

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
   EC2_USER="ubuntu"  # or ec2-user for Amazon Linux
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
   ssh -i your-ssh-key.pem ubuntu@your-ec2-host
   cd rfp-analyzer
   nano .env
   ```

4. Set up SSL certificates with Let's Encrypt:
   ```bash
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```

### Option 2: Manual Deployment

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
   ```bash
   sudo cp nginx.conf /etc/nginx/sites-available/rfp_analyzer
   sudo ln -s /etc/nginx/sites-available/rfp_analyzer /etc/nginx/sites-enabled/
   sudo rm /etc/nginx/sites-enabled/default
   sudo nginx -t
   sudo systemctl reload nginx
   ```

8. Set up SSL with Let's Encrypt:
   ```bash
   sudo apt install certbot python3-certbot-nginx
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

Edit the Nginx configuration file to match your domain:

```bash
sudo nano /etc/nginx/sites-available/rfp_analyzer
```

Replace `your-domain.com` with your actual domain name in the server_name directives.

## Initial Setup

1. After deployment, access the application at your domain (https://yourdomain.com)

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

## Security Considerations

1. **API Keys**: Never commit API keys to the repository. Always use environment variables.
2. **Database Security**: Use strong passwords and restrict network access to your MongoDB instance.
3. **HTTPS**: Always use HTTPS in production with valid SSL certificates.
4. **Regular Updates**: Keep the system, Docker, and application dependencies updated with security patches.
5. **Firewall**: Configure EC2 security groups to allow only necessary traffic.