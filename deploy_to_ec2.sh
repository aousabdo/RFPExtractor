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

# Clean up any existing temp directory
echo -e "${GREEN}Cleaning up any existing temp directory...${NC}"
rm -rf temp_clone

# Clone the repository directly (not as a submodule)
echo -e "${GREEN}Cloning repository...${NC}"
git clone "$REPOSITORY" temp_clone

# Check if .env.template exists
echo -e "${GREEN}Checking for .env.template...${NC}"
if [ -f ".env.template" ]; then
    ENV_TEMPLATE=".env.template"
    echo "Found .env.template in current directory"
elif [ -f "temp_clone/.env.template" ]; then
    ENV_TEMPLATE="temp_clone/.env.template"
    echo "Found .env.template in temp_clone directory" 
else
    echo -e "${RED}Error: .env.template not found in either current directory or cloned repository${NC}"
    echo "Creating a basic .env.template file..."
    
    # Create a basic .env.template file
    cat > temp_clone/.env.template << EOF
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
EOF
    
    ENV_TEMPLATE="temp_clone/.env.template"
    echo "Created basic .env.template file"
fi

# Copy the .env.template to .env if it doesn't exist on the EC2 instance
echo -e "${GREEN}Setting up configuration files...${NC}"
echo "Copying $ENV_TEMPLATE to EC2"
scp -i "$SSH_KEY" "$ENV_TEMPLATE" "$EC2_USER@$EC2_HOST:$DEPLOY_DIR/.env.template"

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
    
    # Disable the default server block to avoid conflicts
    if [ -f /etc/nginx/nginx.conf ]; then
        # Backup the original file first
        sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak
        
        # Check if there's a default server block and comment it out if found
        if grep -q "server {" /etc/nginx/nginx.conf; then
            echo "Commenting out default server blocks in the main nginx.conf..."
            sudo sed -i 's/^[ \t]*server {/#server {/g' /etc/nginx/nginx.conf
            sudo sed -i 's/^[ \t]*location /#location /g' /etc/nginx/nginx.conf
        fi
    fi
    
    # Test Nginx configuration
    echo "Testing Nginx configuration..."
    sudo nginx -t
    
    # Remove any existing default site
    if [ -f /etc/nginx/conf.d/default.conf ]; then
        echo "Removing default Nginx site..."
        sudo mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.bak
    fi
    
    # Restart Nginx (not just reload) to ensure changes are applied
    echo "Restarting Nginx service..."
    sudo systemctl restart nginx
    
    # Verify Nginx is running
    echo "Checking Nginx status..."
    sudo systemctl status nginx
    
    # Ensure Docker and Streamlit are running
    echo "Checking if Streamlit app is running..."
    cd ${DEPLOY_DIR}
    sudo docker-compose ps
    
    # Show running containers
    echo "Listing all running Docker containers:"
    sudo docker ps
    
    # Check if port 8501 is being used
    echo "Checking if port 8501 is in use:"
    sudo ss -tulpn | grep 8501 || echo "Port 8501 not in use!"
    
    echo "Setup complete! Your application should be accessible at http://${EC2_HOST}"
ENDSSH

# Clean up local temp directory
rm -rf temp_clone

echo -e "${GREEN}Deployment completed!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. SSH into your EC2 instance and edit the .env file: ssh -i $SSH_KEY $EC2_USER@$EC2_HOST"
echo -e "2. From the EC2 instance, run: nano $DEPLOY_DIR/.env"
echo -e "3. Access your application at: http://$EC2_HOST (not http://$EC2_HOST/8501)"
echo -e "4. If still having issues, run these commands on the EC2 instance:"
echo -e "   - sudo systemctl status nginx"
echo -e "   - cd $DEPLOY_DIR && sudo docker-compose logs"
echo -e "   - sudo docker ps"
echo -e ""
echo -e "Note: If you want to set up SSL later, you'll need to:"
echo -e "1. Uncomment the SSL section in /etc/nginx/conf.d/rfp_analyzer.conf"
echo -e "2. Create a self-signed certificate or use Let's Encrypt if you get a domain"