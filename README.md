This guide provides step-by-step instructions for deploying the GenAI Workbench using the PowerShell deployment script. The script automates the creation of AWS infrastructure including Docker Docker Desktop, GitHub, AWS CLI, VPC, ECS Fargate, Application Load Balancer, and container deployment. 

Prerequisites 

System requirements must support: 

* Operating System: Windows 10/11 or Windows Server 2016+ 
* PowerShell: Version 5.1 or later 
* Docker Desktop: Latest version (for local image building) 
* Git: Latest version 
* AWS CLI: Version 2.x (latest recommended) 

AWS Requirements 

* AWS Account: Active AWS account with appropriate permissions 
* IAM Permissions: Administrator access or specific permissions for: 
    * CloudFormation (full access) 
    * ECS (full access) 
    * ECR (full access) 
    * VPC (full access) 
    * IAM (role creation) 
    * S3 (bucket operations) 
    * Application Load Balancer 
* Key Pair: EC2 Key Pair in target region 
* Service Limits: Ensure adequate service limits for ECS, VPC, and ALB 

Installation Steps 

1. Environment Setup 
Automated Software Installation 
The script automatically installs all required software: 

* Chocolatey: Package manager for Windows 
* Git: Version control system 
* Docker Desktop: Container platform 
* AWS CLI: AWS command line tools 
* Node.js/npm: JavaScript runtime (for CDK fallback) 
* AWS CDK: Cloud Development Kit 
* PowerShell-YAML: YAML parsing module 

Manual Prerequisites 
# Verify PowerShell version (5.1+ required) 
$PSVersionTable.PSVersion 
 
# Run script as Administrator (required for software installation) 
# Right-click PowerShell → "Run as Administrator" 
  
2. Script Preparation 
Download the Script 

1. Ensure you have GenAIDeploy-Ready.ps1 script on your local system 
2. Place it in a dedicated folder (e.g., C:\GenAI-Deployment\) 

Set Execution Policy 
# Allow script execution (run as Administrator) 
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser  
 
 3. Pre-Deployment Configuration 
Required AWS Account Information 

* Account Number: 12-digit AWS account ID 
* Region: Target AWS region (e.g., us-east-1, us-west-2) 
* Key Pair: Existing EC2 key pair name in the target region 

Network Planning 

* VPC CIDR: Choose a private CIDR block that doesn't conflict with existing VPCs 
    * Valid ranges: 10.x.0.0/16, 172.16-31.0.0/16, 192.168.0.0/16 
    * Example: 10.1.0.0/16 

Repository Configuration 

* Git Repository: URL of the GenAI Workbench source code 
* Deployment Directory: Local path for cloning (e.g., C:\temp\genai-workbench) 

Deployment Process 

1. Launch the Script 
# Navigate to script directory 
cd C:\GenAI-Deployment\ 
 
# Run the deployment script 
.\GenAIDeploy-Ready.ps1 
  
2. Configure Deployment Settings 
Basic Configuration Tab 

1. AWS Account Number: Enter your 12-digit AWS account ID 
2. Region: Select target AWS region 
3. Key Pair Name: Enter existing EC2 key pair name 
4. VPC CIDR: Enter desired CIDR block (use CIDR checker) 

Advanced Configuration Tab 

1. Git Repository: Enter repository URL (Already set in script path) 
2. Deployment Directory: Choose local repository deployment path 
3. S3 Template URI: Leave default or specify custom S3 location 

AWS Credentials Tab 

1. Access Key ID: Enter AWS access key 
2. Secret Access Key: Enter AWS secret key 
3. Session Token: Enter if using temporary credentials (optional) 

T-Shirt Sizing option for Ai environment size setup 
Choose deployment size based on requirements: 
Development Environment 

* Use Case: Development, testing, proof of concept 
* Resources: API (0.25 CPU, 512MB), UI (0.25 CPU, 512MB) 
* Estimated Cost: $15-25/month 
* Suitable For: Small teams, development work 

Medium Production Environment 

* Use Case: Small to medium production workloads 
* Resources: API (0.5 CPU, 1024MB), UI (0.5 CPU, 1024MB) 
* Estimated Cost: $30-50/month 
* Suitable For: Production workloads, moderate traffic 

Enterprise Production Environment 

* Use Case: High-availability production workloads 
* Resources: API (1.0 CPU, 2048MB), UI (1.0 CPU, 2048MB) 
* Estimated Cost: $60-100/month 
* Suitable For: Enterprise workloads, high traffic 

3. Pre-Deployment Validation 
CIDR Validation 

1. Enter desired CIDR in the CIDR input field 
2. Click "Check CIDR" to validate against existing VPCs 
3. Ensure CIDR is available and follows RFC 1918 standards 

Credential Validation 

* Script automatically validates AWS credentials before deployment 
* Verifies account number matches provided credentials 
* Tests basic AWS API connectivity 

4. Execute Deployment 

1. Click "Deploy GenAI Workbench" button 
2. Monitor progress in the status window 
3. Deployment typically takes 5-15 minutes 

Deployment Steps 

The script performs the following automated steps: 

1. Repository Cloning: Downloads source code from Git repository 
2. Docker Image Building: Builds container images locally 
3. ECR Push: Pushes images to Amazon ECR (if build successful) 
4. CloudFormation Generation: Creates infrastructure template 
5. Stack Deployment: Deploys AWS resources via CloudFormation 

Infrastructure Components 

AWS Resources Created 

* VPC: Virtual Private Cloud with specified CIDR 
* Subnets: Public and private subnets across availability zones 
* Internet Gateway: For public internet access 
* NAT Gateway: For private subnet internet access 
* Security Groups: Configured for web traffic (port 80/443) 
* Application Load Balancer: For traffic distribution 
* ECS Cluster: Fargate-based container orchestration 
* ECS Services: API and UI services with auto-scaling 
* ECR Repository: Container image storage 
* IAM Roles: Service execution and task roles 
* CloudWatch: Logging and monitoring 

Network Architecture 

Internet Gateway 
 | 
Application Load Balancer (Public Subnets) 
 | 
ECS Fargate Services (Private Subnets) 
 | 
NAT Gateway (for outbound traffic) 
  

Post-Deployment 

1. Verify Deployment 
After successful deployment, verify the following: 
Check CloudFormation Stack 
# List CloudFormation stacks 
aws cloudformation list-stacks --region your-region 
 
# Get stack outputs 
aws cloudformation describe-stacks --stack-name genai-workbench-dev --region your-region 
  

1. Access Application 

1. Locate the Load Balancer DNS name in stack outputs 

Access the application via HTTP: http://your-alb-dns-name 

1. Verify both API and UI components are accessible 

2. Monitor Resources 

* CloudWatch: Monitor container logs and metrics 
* ECS Console: Check service health and task status 
* ALB Console: Monitor load balancer health checks 

3. Cost Management 

* AWS Cost Explorer: Monitor actual costs vs estimates 
* CloudWatch Billing: Set up billing alerts 
* Resource Optimization: Scale services based on usage 

Troubleshooting 

Common Issues 
Deployment Failures 

1. Credential Issues 
    1. Verify AWS credentials are correct 
    2. Check IAM permissions 
    3. Ensure account number matches credentials 
2. CIDR Conflicts 
    1. Use CIDR checker to validate availability 
    2. Choose different CIDR block if conflicts exist 
3. Resource Limits 
    1. Check AWS service limits in target region 
    2. Request limit increases if needed 
4. Docker Build Failures 
    1. Ensure Docker Desktop is running 
    2. Check repository accessibility 
    3. Verify Dockerfile syntax 

Runtime Issues 

1. Application Not Accessible 
    1. Check security group rules (port 80/443) 
    2. Verify load balancer health checks 
    3. Check ECS service status 
2. Container Startup Issues 
    1. Review CloudWatch logs 
    2. Check container resource allocation 
    3. Verify image availability in ECR 

Cleanup Process 

To remove all deployed resources: 
# Delete CloudFormation stack 
aws cloudformation delete-stack --stack-name genai-workbench-dev --region your-region 
 
# Monitor deletion progress 
aws cloudformation describe-stacks --stack-name genai-workbench-dev --region your-region 
  
Security Considerations 
Network Security 

* All application traffic flows through ALB on standard ports (80/443) 
* Private subnets isolate application containers 
* Security groups restrict access to necessary ports only 

Access Control 

* IAM roles follow principle of least privilege 
* No hardcoded credentials in templates 
* Session-based authentication for temporary access 

Data Protection 

* Container logs stored in CloudWatch 
* ECR repositories use encryption at rest 
* VPC flow logs available for network monitoring 

Maintenance and Updates 

Regular Maintenance 

1. Security Updates: Keep base images updated 
2. Cost Review: Monthly cost analysis and optimization 
3. Performance Monitoring: Review CloudWatch metrics 
4. Backup Strategy: Implement data backup procedures 

Scaling Operations 

* Horizontal Scaling: Adjust ECS service desired count 
* Vertical Scaling: Modify CPU/memory allocations 
* Auto Scaling: Configure based on CloudWatch metrics 

Version Updates 

1. Update source code in Git repository 
2. Re-run deployment script to update containers 
3. CloudFormation will update only changed resources 

Support and Resources 

AWS Documentation 

* ECS Fargate User Guide 
* CloudFormation User Guide 
* Application Load Balancer Guide 

Monitoring and Alerting 

* Set up CloudWatch alarms for critical metrics 
* Configure SNS notifications for deployment events 
* Use AWS X-Ray for application tracing (if implemented) 

Best Practices 

* Regular security assessments 
* Automated backup procedures 
* Disaster recovery planning 
* Performance optimization reviews 



Quick Reference 

Script Locations 

Main Script: GenAIDeploy-Ready.ps1 
Download path: Windows Powershell Install Script

Key Commands 
# Run deployment 
.\GenAIDeploy-Ready.ps1 
 
# Check AWS credentials 
aws sts get-caller-identity 
 
# List CloudFormation stacks 
aws cloudformation list-stacks 
 
# Delete deployment 
aws cloudformation delete-stack --stack-name genai-workbench-dev 
  
Support Contacts 

* AWS Support: Available through AWS Console 
* Documentation: AWS official documentation 
* Community: AWS forums and Stack Overflow 

