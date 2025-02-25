#!/bin/bash
# Script to deploy RFP Analyzer to EC2

# Exit on error
set -e

# Configuration
EC2_HOST="your-ec2-host"
EC2_USER="ubuntu"  # or ec2-user for Amazon Linux
SSH_KEY="path/to/your-ssh-key.pem"
DEPLOY_DIR="/home/$EC2_USER/rfp-analyzer"
REPOSITORY="https://github.com/yourusername/RFPExtractor.git"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Deploying RFP Analyzer to EC2 instance ${EC2_HOST}...${NC}"

# Connect to EC2 and set up the environment
echo -e "${GREEN}Setting up environment on EC2...${NC}"
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
    # Update system packages
    sudo apt-get update
    sudo apt-get upgrade -y

    # Install Docker and Docker Compose if not installed
    if ! command -v docker &> /dev/null; then
        echo "Installing Docker..."
        sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
        sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
        sudo apt-get update
        sudo apt-get install -y docker-ce
        sudo usermod -aG docker $USER
    fi

    if ! command -v docker-compose &> /dev/null; then
        echo "Installing Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/download/v2.14.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi

    # Install Nginx if not installed
    if ! command -v nginx &> /dev/null; then
        echo "Installing Nginx..."
        sudo apt-get install -y nginx
        sudo systemctl enable nginx
        sudo systemctl start nginx
    fi

    # Create deployment directory if it doesn't exist
    mkdir -p $DEPLOY_DIR
ENDSSH

# Clone or update the repository on the local machine
echo -e "${GREEN}Cloning/updating repository...${NC}"
if [ ! -d "temp_clone" ]; then
    git clone "$REPOSITORY" temp_clone
else
    cd temp_clone
    git pull
    cd ..
fi

# Copy the .env.template to .env if it doesn't exist on the EC2 instance
echo -e "${GREEN}Setting up configuration files...${NC}"
scp -i "$SSH_KEY" temp_clone/.env.template "$EC2_USER@$EC2_HOST:$DEPLOY_DIR/.env.template"

ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
    cd $DEPLOY_DIR
    if [ ! -f .env ]; then
        cp .env.template .env
        echo "Please edit the .env file with your configuration:"
        echo "nano $DEPLOY_DIR/.env"
    fi
ENDSSH

# Copy files to EC2
echo -e "${GREEN}Copying application files to EC2...${NC}"
scp -i "$SSH_KEY" -r temp_clone/* "$EC2_USER@$EC2_HOST:$DEPLOY_DIR/"

# Deploy on EC2
echo -e "${GREEN}Deploying application on EC2...${NC}"
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
    cd $DEPLOY_DIR
    
    # Make sure the data directory exists
    mkdir -p data
    
    # Build and start Docker containers
    sudo docker-compose down
    sudo docker-compose build
    sudo docker-compose up -d
    
    # Check if the service is running
    sleep 5
    if sudo docker-compose ps | grep rfp_analyzer | grep -q "Up"; then
        echo "RFP Analyzer is running successfully!"
    else
        echo "There was an issue starting RFP Analyzer. Check the logs:"
        sudo docker-compose logs
    fi
ENDSSH

# Configure Nginx (only needs to be done once)
echo -e "${GREEN}Configuring Nginx...${NC}"
scp -i "$SSH_KEY" temp_clone/nginx.conf "$EC2_USER@$EC2_HOST:/tmp/rfp_analyzer_nginx.conf"

ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
    # Replace the domain name with your actual domain
    sed -i "s/your-domain.com/your-actual-domain.com/g" /tmp/rfp_analyzer_nginx.conf
    
    # Copy to Nginx sites directory
    sudo cp /tmp/rfp_analyzer_nginx.conf /etc/nginx/sites-available/rfp_analyzer
    
    # Enable the site if not already enabled
    if [ ! -f /etc/nginx/sites-enabled/rfp_analyzer ]; then
        sudo ln -s /etc/nginx/sites-available/rfp_analyzer /etc/nginx/sites-enabled/
        sudo rm -f /etc/nginx/sites-enabled/default
    fi
    
    # Test Nginx configuration
    sudo nginx -t
    
    # Reload Nginx if the test is successful
    if [ $? -eq 0 ]; then
        sudo systemctl reload nginx
        echo "Nginx configured successfully!"
    else
        echo "Nginx configuration test failed. Please check the configuration."
    fi
ENDSSH

# Clean up local temp directory
rm -rf temp_clone

echo -e "${GREEN}Deployment completed!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. SSH into your EC2 instance and edit the .env file: ssh -i $SSH_KEY $EC2_USER@$EC2_HOST"
echo -e "2. From the EC2 instance, run: nano $DEPLOY_DIR/.env"
echo -e "3. Update your domain name in Nginx config: sudo nano /etc/nginx/sites-available/rfp_analyzer"
echo -e "4. Set up SSL certificates using Let's Encrypt:"
echo -e "   sudo certbot --nginx -d your-domain.com -d www.your-domain.com"
echo -e "5. Access your application at: https://your-domain.com"