#!/bin/bash
# Script to deploy RFP Analyzer to EC2

# Exit on error
set -e

# Configuration
EC2_HOST="ec2-23-20-221-108.compute-1.amazonaws.com"
EC2_USER="ec2-user"  # Amazon Linux AMI user
SSH_KEY="/Users/aousabdo/aset_ragflow_server.pem"
DEPLOY_DIR="/home/$EC2_USER/rfp-analyzer"
REPOSITORY="https://github.com/aousabdo/RFPExtractor.git"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Deploying RFP Analyzer to EC2 instance ${EC2_HOST}...${NC}"

# Connect to EC2 and set up the environment
echo -e "${GREEN}Setting up environment on EC2...${NC}"
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << ENDSSH
    # Update system packages
    sudo dnf update -y

    # Install Docker and Docker Compose if not installed
    if ! command -v docker &> /dev/null; then
        echo "Installing Docker..."
        sudo dnf install -y docker
        sudo systemctl enable docker
        sudo systemctl start docker
        sudo usermod -aG docker $USER
    fi

    if ! command -v docker-compose &> /dev/null; then
        echo "Installing Docker Compose..."
        # Get the latest version of docker-compose
        COMPOSE_VERSION=\$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
        echo "Installing Docker Compose version \${COMPOSE_VERSION}..."
        
        # Download and install docker-compose
        sudo curl -L "https://github.com/docker/compose/releases/download/\${COMPOSE_VERSION}/docker-compose-\$(uname -s)-\$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
        
        # Verify installation
        docker-compose --version
    fi

    # Install Nginx if not installed
    if ! command -v nginx &> /dev/null; then
        echo "Installing Nginx..."
        sudo dnf install -y nginx
        sudo systemctl enable nginx
        sudo systemctl start nginx
    fi

    # Create deployment directory if it doesn't exist
    mkdir -p ${DEPLOY_DIR}
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

ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << ENDSSH
    cd ${DEPLOY_DIR}
    if [ ! -f .env ]; then
        cp .env.template .env
        echo "Please edit the .env file with your configuration:"
        echo "nano ${DEPLOY_DIR}/.env"
    fi
ENDSSH

# Copy files to EC2
echo -e "${GREEN}Copying application files to EC2...${NC}"
scp -i "$SSH_KEY" -r temp_clone/* "$EC2_USER@$EC2_HOST:$DEPLOY_DIR/"

# Deploy on EC2
echo -e "${GREEN}Deploying application on EC2...${NC}"
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << ENDSSH
    cd ${DEPLOY_DIR}
    
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

ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << ENDSSH
    # Replace the server_name with EC2 hostname
    sed -i "s/ec2-23-20-221-108.compute-1.amazonaws.com/${EC2_HOST}/g" /tmp/rfp_analyzer_nginx.conf
    
    # Copy to Nginx conf directory (Amazon Linux uses different location than Ubuntu)
    sudo mkdir -p /etc/nginx/conf.d
    sudo cp /tmp/rfp_analyzer_nginx.conf /etc/nginx/conf.d/rfp_analyzer.conf
    
    # Make sure default config doesn't conflict
    if [ -f /etc/nginx/nginx.conf ]; then
        # Check if there's a default server block and back it up if needed
        if grep -q "server {" /etc/nginx/nginx.conf; then
            sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak
            # Comment out any server blocks in the main nginx.conf
            sudo sed -i 's/server {/#server {/g' /etc/nginx/nginx.conf
        fi
    fi
    
    # Test Nginx configuration
    sudo nginx -t
    
    # Reload Nginx if the test is successful
    if [ \$? -eq 0 ]; then
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
echo -e "3. Access your application at: http://$EC2_HOST"
echo -e ""
echo -e "Note: If you want to set up SSL later, you'll need to:"
echo -e "1. Uncomment the SSL section in /etc/nginx/conf.d/rfp_analyzer.conf"
echo -e "2. Create a self-signed certificate or use Let's Encrypt if you get a domain"