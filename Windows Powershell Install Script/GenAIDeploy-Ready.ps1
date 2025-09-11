Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Ensure admin
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    [System.Windows.Forms.MessageBox]::Show("Please run this script as Administrator.", "Admin Privileges Required")
    exit 1
}

# Define the AllUsers module path
$allUsersModulePath = Join-Path ${env:ProgramFiles} 'WindowsPowerShell\Modules\powershell-yaml'

# Check if module is installed in AllUsers scope
if (-not (Test-Path $allUsersModulePath)) {
    Write-Host "powershell-yaml module not found for all users. Installing now..."
    Install-Module -Name powershell-yaml -Scope AllUsers -Force -AllowClobber -ErrorAction Stop
    Write-Host "powershell-yaml module installed successfully."
}
else {
    Write-Host "powershell-yaml module already installed."
}

Import-Module powershell-yaml -Force

# T-Shirt Size Environment configurations
$script:EnvironmentConfigs = @{
    'dev' = @{
        'DisplayName' = 'Development'
        'Description' = 'Single developer, light testing'
        'InstanceType' = 't3.medium'
        'MinSize' = 1
        'MaxSize' = 2
        'DesiredCapacity' = 1
        'DBInstanceClass' = 'db.t3.micro'
        'AllocatedStorage' = 20
        'Suffix' = '-dev'
        'ApiCpu' = 512
        'ApiMemory' = 1024
        'UiCpu' = 256
        'UiMemory' = 512
        'Cost' = '$50-100/month'
    }
    'medium-prod' = @{
        'DisplayName' = 'Medium Production'
        'Description' = '10-50 concurrent users'
        'InstanceType' = 't3.large'
        'MinSize' = 2
        'MaxSize' = 10
        'DesiredCapacity' = 2
        'DBInstanceClass' = 'db.t3.small'
        'AllocatedStorage' = 50
        'Suffix' = '-medium'
        'ApiCpu' = 1024
        'ApiMemory' = 2048
        'UiCpu' = 512
        'UiMemory' = 1024
        'Cost' = '$200-400/month'
    }
    'enterprise-prod' = @{
        'DisplayName' = 'Enterprise Production'
        'Description' = '100+ concurrent users'
        'InstanceType' = 't3.xlarge'
        'MinSize' = 3
        'MaxSize' = 20
        'DesiredCapacity' = 3
        'DBInstanceClass' = 'db.t3.medium'
        'AllocatedStorage' = 100
        'Suffix' = '-enterprise'
        'ApiCpu' = 2048
        'ApiMemory' = 4096
        'UiCpu' = 1024
        'UiMemory' = 2048
        'Cost' = '$500-1000/month'
    }
}

function Is-ValidPrivateCidr {
    param([string]$cidr)
    if (-not ($cidr -match '^\d{1,3}(\.\d{1,3}){3}\/16$')) {
        return $false
    }
    $ipParts = $cidr.Split('/')[0].Split('.')
    if ($ipParts.Count -ne 4) { return $false }
    foreach ($part in $ipParts) {
        if ([int]$part -lt 0 -or [int]$part -gt 255) { return $false }
    }
    $first = [int]$ipParts[0]
    $second = [int]$ipParts[1]
    # 10.0.0.0/8 (10.0.0.0 to 10.255.255.255)
    if ($first -eq 10) { return $true }
    # 172.16.0.0/12 (172.16.0.0 to 172.31.255.255)
    if ($first -eq 172 -and $second -ge 16 -and $second -le 31) { return $true }
    # 192.168.0.0/16 (192.168.0.0 to 192.168.255.255)
    if ($first -eq 192 -and $second -eq 168) { return $true }
    return $false
}

function Show-Message($msg, $title="GenAI Workbench Installer") {
    [System.Windows.Forms.MessageBox]::Show($msg, $title)
}

function Refresh-Environment {
    $envPathMachine = [System.Environment]::GetEnvironmentVariable('Path','Machine')
    $envPathUser = [System.Environment]::GetEnvironmentVariable('Path','User')
    $env:Path = $envPathMachine + ";" + $envPathUser
    Write-Host "Refreshed PATH environment variable."
}

function Add-NpmGlobalPathToUserPath {
    $npmGlobalBin = Join-Path $env:APPDATA "npm"
    $currentUserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
    if (-not ($currentUserPath.Split(';') -contains $npmGlobalBin)) {
        Write-Host "Adding npm global bin path to User PATH: $npmGlobalBin"
        $newUserPath = $currentUserPath + ";" + $npmGlobalBin
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, [EnvironmentVariableTarget]::User)
        $env:Path = $newUserPath + ";" + [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::Machine)
        Write-Host "Updated PATH in current session and permanently for user."
    }
}

function Ensure-ChocoInstalled {
    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        iex ((New-Object Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        $tries = 0
        while ($tries -lt 20 -and -not (Get-Command choco -ErrorAction SilentlyContinue)) {
            Start-Sleep -Seconds 2
            $tries++
        }
        if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
            Show-Message "Chocolatey installation failed. Please install manually and rerun." "Error"
            exit 1
        }
        Refresh-Environment
        Show-Message "Chocolatey installed successfully." "Success"
    }
}

function Install-ChocoDep {
    param([string]$package, [string]$cliCmd, [string]$url)
    if (Get-Command $cliCmd -ErrorAction SilentlyContinue) { return }
    $chocoArgs = "-y --ignore-checksums"
    if ($package -ieq "docker-desktop") {
        $chocoArgs += " --accept-license"
    }
    choco install $package $chocoArgs
    Refresh-Environment
    $tries = 0
    while ($tries -lt 15 -and -not (Get-Command $cliCmd -ErrorAction SilentlyContinue)) {
        Start-Sleep -Seconds 2
        Refresh-Environment
        $tries++
    }
    if (-not (Get-Command $cliCmd -ErrorAction SilentlyContinue)) {
        Show-Message "$package installation failed. Please install from $url" "Error"
        exit 1
    }
}

function Ensure-GitInstalled {
    Install-ChocoDep "git" "git" "https://git-scm.com/download/win"
}

function Ensure-HyperVEnabled {
    $hvFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
    if ($hvFeature.State -ne 'Enabled') {
        $r = [System.Windows.Forms.MessageBox]::Show(
            "Hyper-V is not enabled. Would you like to enable it now? A reboot may be required.",
            "Enable Hyper-V?",
            [System.Windows.Forms.MessageBoxButtons]::YesNo)
        if ($r -ne [System.Windows.Forms.DialogResult]::Yes) {
            Show-Message "Hyper-V required. Enable and rerun." "Error"
            exit 1
        }
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -NoRestart -All | Out-Null
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-Management-PowerShell -NoRestart -All | Out-Null
        Enable-WindowsOptionalFeature -Online -FeatureName Containers -NoRestart -All | Out-Null
        Show-Message "Hyper-V enabled. Please reboot and rerun the script." "Reboot Required"
        exit 0
    }
}

function Start-AndWaitDocker {
    if (-not (Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue)) {
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        Start-Sleep -Seconds 10
    }
    $maxWait = 120; $waited = 0
    while ($waited -lt $maxWait) {
        try {
            docker info | Out-Null
            return
        }
        catch {
            if ($waited -eq 0) { Show-Message "Waiting for Docker daemon to start..." "Info" }
            Start-Sleep -Seconds 5
            $waited += 5
        }
    }
    Show-Message "Docker daemon failed to start after waiting." "Error"
    exit 1
}

function Is-DockerDesktopExePresent {
    $dockerExePath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    return Test-Path $dockerExePath
}

function Reinstall-DockerDesktop {
    Write-Host "Docker Desktop executable not found. Reinstalling Docker Desktop via Chocolatey..."
    choco uninstall docker-desktop -y --ignore-checksums --allowempty -ErrorAction SilentlyContinue
    choco install docker-desktop -y --accept-license --ignore-checksums
    Refresh-Environment
    Start-Sleep -Seconds 30
    $script:dockerInstalledDuringScript = $true
}

function Clone-Repository {
    param([string]$repoUrl, [string]$targetDir)
    
    if (Test-Path $targetDir) {
        Write-Host "Repository already exists at $targetDir"
        return
    }
    
    Write-Host "Cloning repository from $repoUrl to $targetDir..."
    git clone $repoUrl $targetDir
    if ($LASTEXITCODE -ne 0) {
        Show-Message "Failed to clone repository from $repoUrl" "Error"
        exit 1
    }
}

function Build-DockerImages {
    param([string]$projectDir)
    
    Write-Host "Checking Docker daemon and project structure..."
    
    # Verify Docker is running
    try {
        docker info | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Docker daemon is not running. Please start Docker Desktop."
            return $false
        }
    } catch {
        Write-Host "Docker daemon is not accessible. Please ensure Docker Desktop is running."
        return $false
    }
    
    # Check if this is the chat-workbench structure
    $chatWorkbenchDir = Join-Path $projectDir "chat-workbench-main"
    if (Test-Path $chatWorkbenchDir) {
        $projectDir = $chatWorkbenchDir
        Write-Host "Using chat-workbench-main directory: $projectDir"
    }
    
    # Check for Docker files
    $backendDockerfile = Join-Path $projectDir "infrastructure\docker\backend\Dockerfile"
    $uiDockerfile = Join-Path $projectDir "ui\Dockerfile"
    
    if (-not (Test-Path $backendDockerfile)) {
        Write-Host "Backend Dockerfile not found at: $backendDockerfile"
        Write-Host "Skipping Docker image builds - will use default container"
        return $false
    }
    
    Write-Host "Building Docker images..."
    
    # Build backend image
    Write-Host "Building backend Docker image..."
    Push-Location $projectDir
    try {
        docker build -f infrastructure/docker/backend/Dockerfile -t eucai-backend:latest .
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Backend Docker build failed, using default container"
            Pop-Location
            return $false
        }
    } catch {
        Write-Host "Docker build exception: $_"
        Pop-Location
        return $false
    }
    Pop-Location
    
    Write-Host "Docker images built successfully!"
    return $true
}

function Push-ToECR {
    param([string]$accountNumber, [string]$region, [string]$environment)
    
    Write-Host "Setting up ECR and pushing images..."
    
    # Create ECR repository if it doesn't exist
    $config = $script:EnvironmentConfigs[$environment]
    $repoName = "eucai-backend$($config.Suffix)"
    
    Write-Host "Creating ECR repository: $repoName"
    $repoResult = aws ecr create-repository --repository-name $repoName --region $region 2>&1
    if ($LASTEXITCODE -ne 0 -and $repoResult -notmatch "RepositoryAlreadyExistsException") {
        Write-Host "Failed to create ECR repository: $repoResult"
        return $false
    }
    
    # Get ECR login token and login in one step
    Write-Host "Logging into ECR..."
    $loginResult = aws ecr get-login-password --region $region | docker login --username AWS --password-stdin "$accountNumber.dkr.ecr.$region.amazonaws.com" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to login to ECR: $loginResult"
        return $false
    }
    
    # Tag and push backend image
    $ecrUri = "$accountNumber.dkr.ecr.$region.amazonaws.com/$repoName`:latest"
    Write-Host "Tagging image: eucai-backend:latest -> $ecrUri"
    docker tag eucai-backend:latest $ecrUri
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to tag image"
        return $false
    }
    
    Write-Host "Pushing image to ECR..."
    docker push $ecrUri
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Successfully pushed to ECR: $ecrUri"
        return $ecrUri
    } else {
        Write-Host "Failed to push to ECR"
        return $false
    }
}

function Upload-TemplateToS3 {
    param([string]$templateContent, [string]$s3Uri, [string]$region)
    
    if (-not $s3Uri) { return $false }
    
    Write-Host "Uploading CloudFormation template to S3: $s3Uri"
    
    # Parse S3 URI
    if ($s3Uri -match '^s3://([^/]+)/(.+)$') {
        $bucketName = $matches[1]
        $keyName = $matches[2]
    } else {
        Write-Host "Invalid S3 URI format. Expected: s3://bucket-name/key-name"
        return $false
    }
    
    # Check if bucket exists, create if it doesn't
    Write-Host "Checking if S3 bucket exists: $bucketName"
    $bucketExists = aws s3api head-bucket --bucket $bucketName --region $region 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Bucket doesn't exist. Creating S3 bucket: $bucketName"
        if ($region -eq "us-east-1") {
            aws s3api create-bucket --bucket $bucketName --region $region
        } else {
            aws s3api create-bucket --bucket $bucketName --region $region --create-bucket-configuration LocationConstraint=$region
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to create S3 bucket: $bucketName"
            return $false
        }
        Write-Host "S3 bucket created successfully: $bucketName"
    }
    
    # Create temp file
    $tempFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($tempFile, $templateContent, [System.Text.Encoding]::UTF8)
        
        # Upload to S3
        aws s3 cp $tempFile $s3Uri --region $region
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Template uploaded successfully to S3"
            return $true
        } else {
            Write-Host "Failed to upload template to S3"
            return $false
        }
    }
    finally {
        Remove-Item $tempFile -ErrorAction SilentlyContinue
    }
}

function Get-ExistingVpcCidrs {
    try {
        $vpcsJson = aws ec2 describe-vpcs --output json 2>&1
        $vpcsObj = $null
        try { $vpcsObj = $vpcsJson | ConvertFrom-Json }
        catch { Show-Message "Failed to parse AWS CLI output for VPCs." "Error"; return @() }
        $cidrBlocks = @()
        foreach ($vpc in $vpcsObj.Vpcs) {
            foreach ($cidrBlockAssoc in $vpc.CidrBlockAssociationSet) {
                $cidrBlocks += $cidrBlockAssoc.CidrBlock
            }
        }
        return $cidrBlocks
    } catch {
        Show-Message "Failed to retrieve VPC CIDRs from AWS." "Error"; return @()
    }
}
function Generate-CloudFormationTemplate {
    param(
        [string]$vpcCidr,
        [string]$keyPairName,
        [string]$environment,
        [string]$ecrImageUri = $null
    )
    
    $config = $script:EnvironmentConfigs[$environment]
    $suffix = $config.Suffix
    
    # Use ECR image if available, otherwise default container
    $containerImage = if ($ecrImageUri) { $ecrImageUri } else { "public.ecr.aws/docker/library/nginx:alpine" }
    
    # Calculate subnet CIDRs
    $subnet1Cidr = $vpcCidr.Replace("/16", "/24").Replace(".0.0", ".1.0")
    $subnet2Cidr = $vpcCidr.Replace("/16", "/24").Replace(".0.0", ".2.0")
    
    # Build template with string replacement to avoid any expansion issues
    $templateBase = @'
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "GenAI Workbench Infrastructure",
  "Parameters": {
    "VpcCidr": {
      "Type": "String",
      "Default": "VPCCIDR_PLACEHOLDER",
      "Description": "CIDR block for VPC"
    }
  },
  "Resources": {
    "VPC": {
      "Type": "AWS::EC2::VPC",
      "Properties": {
        "CidrBlock": {"Ref": "VpcCidr"},
        "EnableDnsHostnames": true,
        "EnableDnsSupport": true,
        "Tags": [
          {"Key": "Name", "Value": "EUCaiVPCSUFFIX_PLACEHOLDER"}
        ]
      }
    },
    "Subnet1": {
      "Type": "AWS::EC2::Subnet",
      "Properties": {
        "VpcId": {"Ref": "VPC"},
        "CidrBlock": "SUBNET1_PLACEHOLDER",
        "AvailabilityZone": {"Fn::Select": [0, {"Fn::GetAZs": ""}]},
        "MapPublicIpOnLaunch": true
      }
    },
    "Subnet2": {
      "Type": "AWS::EC2::Subnet",
      "Properties": {
        "VpcId": {"Ref": "VPC"},
        "CidrBlock": "SUBNET2_PLACEHOLDER",
        "AvailabilityZone": {"Fn::Select": [1, {"Fn::GetAZs": ""}]},
        "MapPublicIpOnLaunch": true
      }
    },
    "IGW": {
      "Type": "AWS::EC2::InternetGateway"
    },
    "AttachGW": {
      "Type": "AWS::EC2::VPCGatewayAttachment",
      "Properties": {
        "VpcId": {"Ref": "VPC"},
        "InternetGatewayId": {"Ref": "IGW"}
      }
    },
    "RouteTable": {
      "Type": "AWS::EC2::RouteTable",
      "Properties": {
        "VpcId": {"Ref": "VPC"}
      }
    },
    "Route": {
      "Type": "AWS::EC2::Route",
      "DependsOn": "AttachGW",
      "Properties": {
        "RouteTableId": {"Ref": "RouteTable"},
        "DestinationCidrBlock": "0.0.0.0/0",
        "GatewayId": {"Ref": "IGW"}
      }
    },
    "SubnetAssoc1": {
      "Type": "AWS::EC2::SubnetRouteTableAssociation",
      "Properties": {
        "SubnetId": {"Ref": "Subnet1"},
        "RouteTableId": {"Ref": "RouteTable"}
      }
    },
    "SubnetAssoc2": {
      "Type": "AWS::EC2::SubnetRouteTableAssociation",
      "Properties": {
        "SubnetId": {"Ref": "Subnet2"},
        "RouteTableId": {"Ref": "RouteTable"}
      }
    },
    "ALBSG": {
      "Type": "AWS::EC2::SecurityGroup",
      "Properties": {
        "GroupDescription": "ALB Security Group",
        "VpcId": {"Ref": "VPC"},
        "SecurityGroupIngress": [
          {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "CidrIp": "0.0.0.0/0"}
        ]
      }
    },
    "ECSSG": {
      "Type": "AWS::EC2::SecurityGroup",
      "Properties": {
        "GroupDescription": "ECS Security Group",
        "VpcId": {"Ref": "VPC"},
        "SecurityGroupIngress": [
          {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "SourceSecurityGroupId": {"Ref": "ALBSG"}}
        ]
      }
    },
    "Cluster": {
      "Type": "AWS::ECS::Cluster",
      "Properties": {
        "ClusterName": "eucai-clusterSUFFIX_PLACEHOLDER"
      }
    },
    "ExecRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {"Service": "ecs-tasks.amazonaws.com"},
              "Action": "sts:AssumeRole"
            }
          ]
        },
        "ManagedPolicyArns": ["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"]
      }
    },
    "TaskRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {"Service": "ecs-tasks.amazonaws.com"},
              "Action": "sts:AssumeRole"
            }
          ]
        },
        "Policies": [
          {
            "PolicyName": "BedrockAccess",
            "PolicyDocument": {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Action": ["bedrock:*", "bedrock-runtime:*"],
                  "Resource": "*"
                }
              ]
            }
          }
        ]
      }
    },
    "ALB": {
      "Type": "AWS::ElasticLoadBalancingV2::LoadBalancer",
      "Properties": {
        "Name": "eucai-albSUFFIX_PLACEHOLDER",
        "Scheme": "internet-facing",
        "Type": "application",
        "Subnets": [{"Ref": "Subnet1"}, {"Ref": "Subnet2"}],
        "SecurityGroups": [{"Ref": "ALBSG"}]
      }
    },
    "TG": {
      "Type": "AWS::ElasticLoadBalancingV2::TargetGroup",
      "Properties": {
        "Name": "eucai-tgSUFFIX_PLACEHOLDER",
        "Port": 80,
        "Protocol": "HTTP",
        "VpcId": {"Ref": "VPC"},
        "TargetType": "ip",
        "HealthCheckPath": "/",
        "HealthCheckProtocol": "HTTP",
        "HealthCheckIntervalSeconds": 30,
        "HealthCheckTimeoutSeconds": 5,
        "HealthyThresholdCount": 2,
        "UnhealthyThresholdCount": 5,
        "Matcher": {"HttpCode": "200,404"}
      }
    },
    "Listener": {
      "Type": "AWS::ElasticLoadBalancingV2::Listener",
      "Properties": {
        "DefaultActions": [
          {
            "Type": "forward",
            "TargetGroupArn": {"Ref": "TG"}
          }
        ],
        "LoadBalancerArn": {"Ref": "ALB"},
        "Port": 80,
        "Protocol": "HTTP"
      }
    },
    "LogGroup": {
      "Type": "AWS::Logs::LogGroup",
      "Properties": {
        "LogGroupName": "/ecs/eucaiSUFFIX_PLACEHOLDER",
        "RetentionInDays": 7
      }
    },
    "TaskDef": {
      "Type": "AWS::ECS::TaskDefinition",
      "Properties": {
        "Family": "eucai-taskSUFFIX_PLACEHOLDER",
        "NetworkMode": "awsvpc",
        "RequiresCompatibilities": ["FARGATE"],
        "Cpu": "CPU_PLACEHOLDER",
        "Memory": "MEMORY_PLACEHOLDER",
        "ExecutionRoleArn": {"Ref": "ExecRole"},
        "TaskRoleArn": {"Ref": "TaskRole"},
        "ContainerDefinitions": [
          {
            "Name": "eucai-app",
            "Image": "IMAGE_PLACEHOLDER",
            "PortMappings": [
              {
                "ContainerPort": 80,
                "Protocol": "tcp"
              }
            ],
            "Essential": true,
            "LogConfiguration": {
              "LogDriver": "awslogs",
              "Options": {
                "awslogs-group": {"Ref": "LogGroup"},
                "awslogs-region": {"Ref": "AWS::Region"},
                "awslogs-stream-prefix": "ecs"
              }
            }
          }
        ]
      }
    },
    "Service": {
      "Type": "AWS::ECS::Service",
      "DependsOn": "Listener",
      "Properties": {
        "ServiceName": "eucai-serviceSUFFIX_PLACEHOLDER",
        "Cluster": {"Ref": "Cluster"},
        "TaskDefinition": {"Ref": "TaskDef"},
        "DesiredCount": CAPACITY_PLACEHOLDER,
        "LaunchType": "FARGATE",
        "NetworkConfiguration": {
          "AwsvpcConfiguration": {
            "SecurityGroups": [{"Ref": "ECSSG"}],
            "Subnets": [{"Ref": "Subnet1"}, {"Ref": "Subnet2"}],
            "AssignPublicIp": "ENABLED"
          }
        },
        "LoadBalancers": [
          {
            "ContainerName": "eucai-app",
            "ContainerPort": 80,
            "TargetGroupArn": {"Ref": "TG"}
          }
        ]
      }
    }
  },
  "Outputs": {
    "URL": {
      "Description": "Application URL",
      "Value": {"Fn::Sub": "http://${ALB.DNSName}"}
    },
    "VPCId": {
      "Description": "VPC ID",
      "Value": {"Ref": "VPC"}
    }
  }
}
'@
    
    # Replace placeholders with actual values
    $template = $templateBase.Replace('VPCCIDR_PLACEHOLDER', $vpcCidr)
    $template = $template.Replace('SUBNET1_PLACEHOLDER', $subnet1Cidr)
    $template = $template.Replace('SUBNET2_PLACEHOLDER', $subnet2Cidr)
    $template = $template.Replace('SUFFIX_PLACEHOLDER', $suffix)
    $template = $template.Replace('CPU_PLACEHOLDER', $config.ApiCpu.ToString())
    $template = $template.Replace('MEMORY_PLACEHOLDER', $config.ApiMemory.ToString())
    $template = $template.Replace('IMAGE_PLACEHOLDER', $containerImage)
    $template = $template.Replace('CAPACITY_PLACEHOLDER', $config.DesiredCapacity.ToString())
    
    return $template
}
function Deploy-CloudFormation {
    param(
        [string]$stackName,
        [string]$templateContent,
        [string]$region,
        [string]$s3Uri = $null
    )
    
    Write-Host "Deploying CloudFormation stack: $stackName"
    
    # Check template size
    $templateSize = [System.Text.Encoding]::UTF8.GetByteCount($templateContent)
    Write-Host "Template size: $templateSize bytes"
    
    if ($templateSize -gt 51200 -and -not $s3Uri) {
        Write-Host "Template size exceeds 50KB limit. S3 storage required for deployment."
        return $false
    }
    
    try {
        # Always use S3 to avoid PowerShell string expansion issues
        if (-not $s3Uri) {
            # Generate default S3 URI if not provided with DNS-compliant name
            $randomSuffix = Get-Random -Minimum 100000 -Maximum 999999
            $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
            $bucketName = "genai-wb-templates-$randomSuffix".ToLower()
            $s3Uri = "s3://$bucketName/template-$timestamp.json"
            Write-Host "No S3 URI provided, using: $s3Uri"
        }
        
        if (Upload-TemplateToS3 $templateContent $s3Uri $region) {
            # Convert S3 URI to HTTPS URL for CloudFormation
            if ($s3Uri -match '^s3://([^/]+)/(.+)$') {
                $bucketName = $matches[1]
                $keyName = $matches[2]
                $templateUrl = "https://$bucketName.s3.$region.amazonaws.com/$keyName"
                Write-Host "S3 URI: $s3Uri"
                Write-Host "Bucket: $bucketName"
                Write-Host "Key: $keyName"
                Write-Host "Template URL: $templateUrl"
            } else {
                Write-Host "Invalid S3 URI format: $s3Uri"
                return $false
            }
            
            # Deploy from S3
            Write-Host "Deploying from S3: $templateUrl"
            aws cloudformation create-stack --template-url $templateUrl --stack-name $stackName --capabilities CAPABILITY_IAM --region $region
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Stack creation initiated. Monitoring progress..."
                $waitStart = Get-Date
                do {
                    Start-Sleep -Seconds 30
                    $elapsed = [math]::Round(((Get-Date) - $waitStart).TotalMinutes, 1)
                    Write-Host "Stack creation in progress... ($elapsed minutes elapsed)"
                    $stackStatus = aws cloudformation describe-stacks --stack-name $stackName --region $region --query "Stacks[0].StackStatus" --output text 2>$null
                    
                    # Show which resource is currently being created
                    $currentResource = aws cloudformation describe-stack-events --stack-name $stackName --region $region --query "StackEvents[?ResourceStatus=='CREATE_IN_PROGRESS'][0].[LogicalResourceId,ResourceType]" --output text 2>$null
                    if ($currentResource) {
                        Write-Host "Currently creating: $currentResource"
                    }
                } while ($stackStatus -eq "CREATE_IN_PROGRESS" -and $elapsed -lt 25)
                
                if ($stackStatus -eq "CREATE_COMPLETE") {
                    Write-Host "Stack creation completed successfully!"
                } else {
                    Write-Host "Stack status: $stackStatus"
                }
            }
        } else {
            Write-Host "S3 upload failed, cannot proceed with deployment"
            return $false
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Stack deployment completed successfully!"
            return $true
        } else {
            Write-Host "Stack deployment failed with exit code: $LASTEXITCODE"
            return $false
        }
    }
    catch {
        Write-Host "Error during deployment: $($_.Exception.Message)"
        return $false
    }
}
# Initialize environment
Show-Message "Welcome - I will prepare your environment, please be patient as this setup may take time. Where missing requirements are identified I will install them. You may need to reboot your system.`n`nBefore running this script, ensure you have:`n`n(1) AWS Access Key, Secret Key, and Account Number with permissions to create VPC, ECS, IAM, and CloudFormation resources`n`n(2) A valid private CIDR block (like 192.168.0.0/16) that doesn't conflict with existing VPCs`n`n(3) Administrator privileges on this Windows machine`n`nThe script will automatically install all other required tools including Docker, Git, AWS CLI, and Node.js." "GenAI Workbench Setup"

$script:dockerInstalledDuringScript = $false
Ensure-ChocoInstalled
Ensure-GitInstalled
Ensure-HyperVEnabled
Add-NpmGlobalPathToUserPath

$deps = @(
    @{Name="AWS CLI"; Package="awscli"; Cmd="aws"; Url="https://aws.amazon.com/cli"},
    @{Name="Node.js"; Package="nodejs-lts"; Cmd="node"; Url="https://nodejs.org"},
    @{Name="npm"; Package="nodejs-lts"; Cmd="npm"; Url="https://nodejs.org"},
    @{Name="Docker Desktop"; Package="docker-desktop"; Cmd="docker"; Url="https://docs.docker.com"}
)

foreach ($dep in $deps) {
    if ($dep.Name -eq "Docker Desktop") {
        if (-not (Is-DockerDesktopExePresent)) {
            Reinstall-DockerDesktop
        }
        elseif (-not (Get-Command $dep.Cmd -ErrorAction SilentlyContinue)) {
            Install-ChocoDep $dep.Package $dep.Cmd $dep.Url
            $script:dockerInstalledDuringScript = $true
        }
    }
    else {
        Install-ChocoDep $dep.Package $dep.Cmd $dep.Url
    }
}

if ($dockerInstalledDuringScript) {
    $dockerMsg = @'
1. Navigate to the taskbar, right-click the Docker Desktop (Whale) icon, and select 'Quit Docker Desktop'.
2. Navigate to 'C:\Program Files\Docker\Docker\Docker Desktop.exe' and launch it manually.
3. Complete the First Run wizard.
Click OK once done to continue to Deployment Settings.
'@
    [System.Windows.Forms.MessageBox]::Show($dockerMsg, "Docker Desktop Setup Required")
}

Start-AndWaitDocker

if (-not (Get-Command cdk -ErrorAction SilentlyContinue)) {
    npm install -g aws-cdk
    Refresh-Environment
    Start-Sleep -Seconds 5
}

# Create GUI Form
$form = New-Object System.Windows.Forms.Form
$form.Text = "GenAI Workbench Installer v9.11 Complete T-Shirt"
$form.Size = New-Object System.Drawing.Size(800, 900)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$tabControl = New-Object System.Windows.Forms.TabControl
$tabControl.Dock = "Fill"

#-------------------------------------------#
# --- Pre Deployment Tab and Credentials ---
#-------------------------------------------#
$tabPreDeploy = New-Object System.Windows.Forms.TabPage "Pre Deployment Tests"
$tabPreDeploy.Text = "Pre Deployment Tests"

$lblStep1 = New-Object System.Windows.Forms.Label
$lblStep1.Text = "Step 1. Test Access to Account"
$lblStep1.Font = New-Object System.Drawing.Font("Microsoft Sans Serif",12,[System.Drawing.FontStyle]::Bold)
$lblStep1.Location = New-Object System.Drawing.Point(30, 10)
$lblStep1.Size = New-Object System.Drawing.Size(700, 30)
$tabPreDeploy.Controls.Add($lblStep1)

$lblAccessKey = New-Object System.Windows.Forms.Label
$lblAccessKey.Text = "AWS Access Key:"
$lblAccessKey.Location = New-Object System.Drawing.Point(30, 50)
$lblAccessKey.Size = New-Object System.Drawing.Size(150, 25)
$tabPreDeploy.Controls.Add($lblAccessKey)

$txtAccessKey = New-Object System.Windows.Forms.TextBox
$txtAccessKey.Location = New-Object System.Drawing.Point(200, 50)
$txtAccessKey.Size = New-Object System.Drawing.Size(330, 25)
$tabPreDeploy.Controls.Add($txtAccessKey)

$lblSecretKey = New-Object System.Windows.Forms.Label
$lblSecretKey.Text = "AWS Secret Key:"
$lblSecretKey.Location = New-Object System.Drawing.Point(30, 80)
$lblSecretKey.Size = New-Object System.Drawing.Size(150, 25)
$tabPreDeploy.Controls.Add($lblSecretKey)

$txtSecretKey = New-Object System.Windows.Forms.TextBox
$txtSecretKey.Location = New-Object System.Drawing.Point(200, 80)
$txtSecretKey.Size = New-Object System.Drawing.Size(330, 25)
$txtSecretKey.UseSystemPasswordChar = $true
$tabPreDeploy.Controls.Add($txtSecretKey)

$lblSessionToken = New-Object System.Windows.Forms.Label
$lblSessionToken.Text = "Session Token (optional):"
$lblSessionToken.Location = New-Object System.Drawing.Point(30, 110)
$lblSessionToken.Size = New-Object System.Drawing.Size(150, 25)
$tabPreDeploy.Controls.Add($lblSessionToken)

$txtSessionToken = New-Object System.Windows.Forms.TextBox
$txtSessionToken.Location = New-Object System.Drawing.Point(200, 110)
$txtSessionToken.Size = New-Object System.Drawing.Size(330, 25)
$txtSessionToken.UseSystemPasswordChar = $true
$tabPreDeploy.Controls.Add($txtSessionToken)

$btnTestCred = New-Object System.Windows.Forms.Button
$btnTestCred.Text = "Test AWS Credentials"
$btnTestCred.Size = New-Object System.Drawing.Size(170, 35)
$btnTestCred.Location = New-Object System.Drawing.Point(30, 145)
$tabPreDeploy.Controls.Add($btnTestCred)

# Step 2. System Components PreCheck
$lblStep2 = New-Object System.Windows.Forms.Label
$lblStep2.Text = "Step 2. System Components PreCheck"
$lblStep2.Font = New-Object System.Drawing.Font("Microsoft Sans Serif",12,[System.Drawing.FontStyle]::Bold)
$lblStep2.Location = New-Object System.Drawing.Point(30, 195)
$lblStep2.Size = New-Object System.Drawing.Size(400, 30)
$tabPreDeploy.Controls.Add($lblStep2)

$lblNpmStatus = New-Object System.Windows.Forms.Label
$lblNpmStatus.Location = New-Object System.Drawing.Point(30, 230)
$lblNpmStatus.Size = New-Object System.Drawing.Size(600, 30)
$lblNpmStatus.Text = "Click 'Check NPM and CDK Status' to begin."
$tabPreDeploy.Controls.Add($lblNpmStatus)

$buttonY = 265
$buttonHeight = 35
$buttonGap = 25
$btnWidth = 190
$btn1X = 30
$btn2X = $btn1X + $btnWidth + $buttonGap
$btn3X = $btn1X + 2*($btnWidth + $buttonGap)

$btnCheckNpmStatus = New-Object System.Windows.Forms.Button
$btnCheckNpmStatus.Text = "Check NPM and CDK Status"
$btnCheckNpmStatus.Size = New-Object System.Drawing.Size($btnWidth, $buttonHeight)
$btnCheckNpmStatus.Font = New-Object System.Drawing.Font("Microsoft Sans Serif", 10)
$btnCheckNpmStatus.Location = New-Object System.Drawing.Point($btn1X, $buttonY)
$tabPreDeploy.Controls.Add($btnCheckNpmStatus)

$btnReinstallCDK = New-Object System.Windows.Forms.Button
$btnReinstallCDK.Text = "Reinstall AWS CDK"
$btnReinstallCDK.Size = New-Object System.Drawing.Size($btnWidth, $buttonHeight)
$btnReinstallCDK.Font = New-Object System.Drawing.Font("Microsoft Sans Serif", 10)
$btnReinstallCDK.Location = New-Object System.Drawing.Point($btn2X, $buttonY)
$tabPreDeploy.Controls.Add($btnReinstallCDK)

$btnClearCache = New-Object System.Windows.Forms.Button
$btnClearCache.Text = "Clear NPM Cache"
$btnClearCache.Size = New-Object System.Drawing.Size($btnWidth, $buttonHeight)
$btnClearCache.Font = New-Object System.Drawing.Font("Microsoft Sans Serif", 10)
$btnClearCache.Location = New-Object System.Drawing.Point($btn3X, $buttonY)
$tabPreDeploy.Controls.Add($btnClearCache)

$lblNodeStatusY = $buttonY + $buttonHeight + 10
$lblNpmStatusVerY = $lblNodeStatusY + 30
$lblCdkStatusY = $lblNpmStatusVerY + 30

$lblNodeStatus = New-Object System.Windows.Forms.Label
$lblNodeStatus.Location = New-Object System.Drawing.Point(30, $lblNodeStatusY)
$lblNodeStatus.Size = New-Object System.Drawing.Size(350, 25)
$lblNodeStatus.Text = "Node.js: not checked"
$tabPreDeploy.Controls.Add($lblNodeStatus)

$lblNpmStatusVer = New-Object System.Windows.Forms.Label
$lblNpmStatusVer.Location = New-Object System.Drawing.Point(30, $lblNpmStatusVerY)
$lblNpmStatusVer.Size = New-Object System.Drawing.Size(350, 25)
$lblNpmStatusVer.Text = "npm: not checked"
$tabPreDeploy.Controls.Add($lblNpmStatusVer)

$lblCdkStatus = New-Object System.Windows.Forms.Label
$lblCdkStatus.Location = New-Object System.Drawing.Point(30, $lblCdkStatusY)
$lblCdkStatus.Size = New-Object System.Drawing.Size(350, 25)
$lblCdkStatus.Text = "AWS CDK: not checked"
$tabPreDeploy.Controls.Add($lblCdkStatus)

function Add-GreenCheckMark($text) { return "[OK] " + $text }
function Add-RedXMark($text) { return "[ERROR] " + $text }

# Step 3. Check Network CIDR
$lblStep3 = New-Object System.Windows.Forms.Label
$lblStep3.Text = "Step 3. Check for '/16' Network CIDR Availability"
$lblStep3.Font = New-Object System.Drawing.Font("Microsoft Sans Serif",12,[System.Drawing.FontStyle]::Bold)
$lblStep3.Location = New-Object System.Drawing.Point(30, 420)
$lblStep3.Size = New-Object System.Drawing.Size(500, 30)
$tabPreDeploy.Controls.Add($lblStep3)

$lblCidrCheck = New-Object System.Windows.Forms.Label
$lblCidrCheck.Text = "CIDR to check:"
$lblCidrCheck.Location = New-Object System.Drawing.Point(30, 460)
$lblCidrCheck.Size = New-Object System.Drawing.Size(100, 25)
$tabPreDeploy.Controls.Add($lblCidrCheck)

$txtCidrInput = New-Object System.Windows.Forms.TextBox
$txtCidrInput.Location = New-Object System.Drawing.Point(150, 460)
$txtCidrInput.Size = New-Object System.Drawing.Size(150, 25)
$tabPreDeploy.Controls.Add($txtCidrInput)

$btnCidrCheck = New-Object System.Windows.Forms.Button
$btnCidrCheck.Text = "Check CIDR"
$btnCidrCheck.Location = New-Object System.Drawing.Point(320, 460)
$btnCidrCheck.Size = New-Object System.Drawing.Size(120, 30)
$tabPreDeploy.Controls.Add($btnCidrCheck)

$lblCidrResult = New-Object System.Windows.Forms.Label
$lblCidrResult.Location = New-Object System.Drawing.Point(30, 495)
$lblCidrResult.Size = New-Object System.Drawing.Size(600, 40)
$tabPreDeploy.Controls.Add($lblCidrResult)

# ---------------------- #
# --- DEPLOYMENT TAB---
# ---------------------- #
$tabDeploy = New-Object System.Windows.Forms.TabPage "Deployment Settings"
$tabDeploy.Text = "Deployment Settings"

# T-Shirt Size Selection
$sizeLabel = New-Object System.Windows.Forms.Label
$sizeLabel.Location = New-Object System.Drawing.Point(30, 20)
$sizeLabel.Size = New-Object System.Drawing.Size(150, 20)
$sizeLabel.Text = "Deployment Size:"
$sizeLabel.Font = New-Object System.Drawing.Font("Microsoft Sans Serif", 10, [System.Drawing.FontStyle]::Bold)
$tabDeploy.Controls.Add($sizeLabel)

$sizeComboBox = New-Object System.Windows.Forms.ComboBox
$sizeComboBox.Location = New-Object System.Drawing.Point(200, 18)
$sizeComboBox.Size = New-Object System.Drawing.Size(300, 25)
$sizeComboBox.DropDownStyle = "DropDownList"
$sizeComboBox.Items.AddRange(@(
    $script:EnvironmentConfigs['dev'].DisplayName,
    $script:EnvironmentConfigs['medium-prod'].DisplayName,
    $script:EnvironmentConfigs['enterprise-prod'].DisplayName
))
$sizeComboBox.SelectedIndex = 0
$tabDeploy.Controls.Add($sizeComboBox)

# Size Info Display
$sizeInfoLabel = New-Object System.Windows.Forms.Label
$sizeInfoLabel.Location = New-Object System.Drawing.Point(30, 50)
$sizeInfoLabel.Size = New-Object System.Drawing.Size(550, 60)
$sizeInfoLabel.ForeColor = [System.Drawing.Color]::Blue
$sizeInfoLabel.Font = New-Object System.Drawing.Font("Microsoft Sans Serif", 9)
$tabDeploy.Controls.Add($sizeInfoLabel)

# VPC CIDR
$vpcLabel = New-Object System.Windows.Forms.Label
$vpcLabel.Location = New-Object System.Drawing.Point(30, 130)
$vpcLabel.Size = New-Object System.Drawing.Size(150, 20)
$vpcLabel.Text = "VPC CIDR Block:"
$tabDeploy.Controls.Add($vpcLabel)

$vpcTextBox = New-Object System.Windows.Forms.TextBox
$vpcTextBox.Location = New-Object System.Drawing.Point(200, 128)
$vpcTextBox.Size = New-Object System.Drawing.Size(200, 25)
$vpcTextBox.Text = "10.0.0.0/16"
$tabDeploy.Controls.Add($vpcTextBox)

# Key Pair
$keyLabel = New-Object System.Windows.Forms.Label
$keyLabel.Location = New-Object System.Drawing.Point(30, 170)
$keyLabel.Size = New-Object System.Drawing.Size(150, 20)
$keyLabel.Text = "EC2 Key Pair Name:"
$tabDeploy.Controls.Add($keyLabel)

$keyTextBox = New-Object System.Windows.Forms.TextBox
$keyTextBox.Location = New-Object System.Drawing.Point(200, 168)
$keyTextBox.Size = New-Object System.Drawing.Size(200, 25)
$keyTextBox.Text = "my-key-pair"
$tabDeploy.Controls.Add($keyTextBox)

# AWS Region
$regionLabel = New-Object System.Windows.Forms.Label
$regionLabel.Location = New-Object System.Drawing.Point(30, 210)
$regionLabel.Size = New-Object System.Drawing.Size(150, 20)
$regionLabel.Text = "AWS Region:"
$tabDeploy.Controls.Add($regionLabel)

$regionTextBox = New-Object System.Windows.Forms.TextBox
$regionTextBox.Location = New-Object System.Drawing.Point(200, 208)
$regionTextBox.Size = New-Object System.Drawing.Size(200, 25)
$regionTextBox.Text = "Enter Region (e.g. us-east-1)"
$tabDeploy.Controls.Add($regionTextBox)

# AWS Account Number
$accountLabel = New-Object System.Windows.Forms.Label
$accountLabel.Location = New-Object System.Drawing.Point(30, 250)
$accountLabel.Size = New-Object System.Drawing.Size(150, 20)
$accountLabel.Text = "AWS Account Number:"
$tabDeploy.Controls.Add($accountLabel)

$accountTextBox = New-Object System.Windows.Forms.TextBox
$accountTextBox.Location = New-Object System.Drawing.Point(200, 248)
$accountTextBox.Size = New-Object System.Drawing.Size(200, 25)
$accountTextBox.Text = "Enter AWS Account #"
$tabDeploy.Controls.Add($accountTextBox)

# Git Repository URL
$gitLabel = New-Object System.Windows.Forms.Label
$gitLabel.Location = New-Object System.Drawing.Point(30, 290)
$gitLabel.Size = New-Object System.Drawing.Size(150, 20)
$gitLabel.Text = "Git Repository URL:"
$tabDeploy.Controls.Add($gitLabel)

$gitTextBox = New-Object System.Windows.Forms.TextBox
$gitTextBox.Location = New-Object System.Drawing.Point(200, 288)
$gitTextBox.Size = New-Object System.Drawing.Size(350, 25)
$gitTextBox.Text = "https://github.com/NoMereMortal/EUCAIBigBoy.git"
$tabDeploy.Controls.Add($gitTextBox)

# Deployment Directory
$deployDirLabel = New-Object System.Windows.Forms.Label
$deployDirLabel.Location = New-Object System.Drawing.Point(30, 330)
$deployDirLabel.Size = New-Object System.Drawing.Size(150, 20)
$deployDirLabel.Text = "Deployment Directory:"
$tabDeploy.Controls.Add($deployDirLabel)

$deployDirTextBox = New-Object System.Windows.Forms.TextBox
$deployDirTextBox.Location = New-Object System.Drawing.Point(200, 328)
$deployDirTextBox.Size = New-Object System.Drawing.Size(270, 25)
$deployDirTextBox.Text = "Enter path to where you want your local repo to be"
$tabDeploy.Controls.Add($deployDirTextBox)

# Browse Button for Deployment Directory
$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Location = New-Object System.Drawing.Point(480, 328)
$btnBrowse.Size = New-Object System.Drawing.Size(70, 25)
$btnBrowse.Text = "Browse"
$tabDeploy.Controls.Add($btnBrowse)

# S3 Template URI (Optional)
$s3Label = New-Object System.Windows.Forms.Label
$s3Label.Location = New-Object System.Drawing.Point(30, 370)
$s3Label.Size = New-Object System.Drawing.Size(150, 20)
$s3Label.Text = "S3 Template URI:"
$tabDeploy.Controls.Add($s3Label)

$s3TextBox = New-Object System.Windows.Forms.TextBox
$s3TextBox.Location = New-Object System.Drawing.Point(200, 368)
$s3TextBox.Size = New-Object System.Drawing.Size(350, 25)
$s3TextBox.Text = "s3://my-bucket/templates/genai-workbench.json"
$tabDeploy.Controls.Add($s3TextBox)

$s3HelpLabel = New-Object System.Windows.Forms.Label
$s3HelpLabel.Location = New-Object System.Drawing.Point(200, 395)
$s3HelpLabel.Size = New-Object System.Drawing.Size(350, 30)
$s3HelpLabel.Text = "(Required - S3 storage bypasses PowerShell JSON formatting issues)"
$s3HelpLabel.ForeColor = [System.Drawing.Color]::DarkBlue
$tabDeploy.Controls.Add($s3HelpLabel)

# Deploy Button
$deployButton = New-Object System.Windows.Forms.Button
$deployButton.Location = New-Object System.Drawing.Point(350, 440)
$deployButton.Size = New-Object System.Drawing.Size(100, 30)
$deployButton.Text = "Deploy"
$deployButton.BackColor = [System.Drawing.Color]::LightGreen
$tabDeploy.Controls.Add($deployButton)

# Status TextBox
$statusTextBox = New-Object System.Windows.Forms.TextBox
$statusTextBox.Location = New-Object System.Drawing.Point(30, 490)
$statusTextBox.Size = New-Object System.Drawing.Size(720, 330)
$statusTextBox.Multiline = $true
$statusTextBox.ScrollBars = "Vertical"
$statusTextBox.ReadOnly = $true
$statusTextBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$tabDeploy.Controls.Add($statusTextBox)
# Update size info when selection changes
$sizeComboBox.Add_SelectedIndexChanged({
    $selectedIndex = $sizeComboBox.SelectedIndex
    $sizeKey = @('dev', 'medium-prod', 'enterprise-prod')[$selectedIndex]
    $config = $script:EnvironmentConfigs[$sizeKey]
    
    $sizeInfoLabel.Text = "$($config.Description)`n" +
                         "API: $($config.ApiCpu) CPU, $($config.ApiMemory)MB RAM | UI: $($config.UiCpu) CPU, $($config.UiMemory)MB RAM`n" +
                         "Capacity: $($config.MinSize)-$($config.MaxSize) instances | Est. Cost: $($config.Cost)"
})

# Initialize size info display
$selectedIndex = $sizeComboBox.SelectedIndex
$sizeKey = @('dev', 'medium-prod', 'enterprise-prod')[$selectedIndex]
$config = $script:EnvironmentConfigs[$sizeKey]
$sizeInfoLabel.Text = "$($config.Description)`n" +
                     "API: $($config.ApiCpu) CPU, $($config.ApiMemory)MB RAM | UI: $($config.UiCpu) CPU, $($config.UiMemory)MB RAM`n" +
                     "Capacity: $($config.MinSize)-$($config.MaxSize) instances | Est. Cost: $($config.Cost)"

# Event Handlers
$btnTestCred.Add_Click({
    $btnTestCred.Text = "Testing..."
    $btnTestCred.Enabled = $false
    try {
        $accessKey = $txtAccessKey.Text.Trim()
        $secretKey = $txtSecretKey.Text.Trim()
        $sessionToken = $txtSessionToken.Text.Trim()
        if (-not $accessKey -or -not $secretKey) {
            Show-Message "AWS Access Key and Secret Key are required." "Error"
            return
        }
        aws configure set aws_access_key_id $accessKey
        aws configure set aws_secret_access_key $secretKey
        if ($sessionToken) {
            aws configure set aws_session_token $sessionToken
        }
        $regionToUse = $regionTextBox.Text.Trim()
        if ($regionToUse) {
            aws configure set region $regionToUse
        }
        $callerIdentityJson = aws sts get-caller-identity --output json | ConvertFrom-Json
        $actualAccountId = $callerIdentityJson.Account
        $enteredAccountId = $accountTextBox.Text.Trim()
        if ($actualAccountId -eq $enteredAccountId) {
            [System.Windows.Forms.MessageBox]::Show("AWS credentials are valid and Account Number matches!", "Success")
        }
        else {
            [System.Windows.Forms.MessageBox]::Show("AWS credentials are valid, but Account Number does NOT match the entered value.`nActual Account ID: $actualAccountId`nEntered Account ID: $enteredAccountId", "Warning")
        }
    }
    catch {
        [System.Windows.Forms.MessageBox]::Show("AWS credentials test failed: $_", "Error")
    }
    finally {
        $btnTestCred.Text = "Test AWS Credentials"
        $btnTestCred.Enabled = $true
    }
})

$btnCheckNpmStatus.Add_Click({
    $lblNpmStatus.Text = "Checking Node.js, npm, and AWS CDK versions..."
    $nodeOk = $false
    $npmOk = $false
    $cdkOk = $false
    try {
        $nodeVersionRaw = (& node -v) 2>&1
        if ($LASTEXITCODE -eq 0 -and $nodeVersionRaw -match '^v\d+\.\d+\.\d+$') {
            $nodeOk = $true
            $nodeVersion = $nodeVersionRaw.Trim()
            $lblNodeStatus.Text = Add-GreenCheckMark("Node.js version: $nodeVersion")
        } else { throw "Node.js version check failed" }
    } catch { $lblNodeStatus.Text = Add-RedXMark("Node.js not found or invalid version.") }
    try {
        $npmVersionRaw = (& npm -v) 2>&1
        if ($LASTEXITCODE -eq 0 -and $npmVersionRaw -match '^\d+\.\d+\.\d+$') {
            $npmOk = $true
            $npmVersion = $npmVersionRaw.Trim()
            $lblNpmStatusVer.Text = Add-GreenCheckMark("npm version: $npmVersion")
        } else { throw "npm version check failed" }
    } catch { $lblNpmStatusVer.Text = Add-RedXMark("npm not found or invalid version.") }
    try {
        $cdkVersionRaw = powershell -Command "npx cdk --version" 2>&1
        if ($LastExitCode -eq 0 -and $cdkVersionRaw -match '^\d+\.\d+\.\d+') {
            $cdkOk = $true
            $cdkVersion = $cdkVersionRaw.Trim()
            $lblCdkStatus.Text = Add-GreenCheckMark("AWS CDK version: $cdkVersion")
        } else { throw "cdk version check failed" }
    } catch { $lblCdkStatus.Text = Add-RedXMark("AWS CDK not found or invalid version.") }
    if ($nodeOk -and $npmOk -and $cdkOk) {
        $lblNpmStatus.Text = "All components are installed and functioning correctly."
    } else {
        $lblNpmStatus.Text = "Some components need attention. Use the buttons below to reinstall AWS CDK or clear the npm cache."
    }
})

$btnReinstallCDK.Add_Click({
    $lblNpmStatus.Text = "Reinstalling AWS CDK globally..."
    try {
        npm install -g aws-cdk
        Refresh-Environment
        Start-Sleep -Seconds 5
        $lblNpmStatus.Text = "AWS CDK reinstalled successfully. Please re-check status."
    } catch {
        $lblNpmStatus.Text = "Failed to reinstall AWS CDK. $_"
    }
})

$btnClearCache.Add_Click({
    $lblNpmStatus.Text = "Clearing npm cache..."
    try {
        npm cache clean --force
        $lblNpmStatus.Text = "npm cache cleared. Please re-check status."
    } catch {
        $lblNpmStatus.Text = "Failed to clear npm cache. $_"
    }
})

$btnBrowse.Add_Click({
    $folderBrowser = New-Object System.Windows.Forms.FolderBrowserDialog
    $folderBrowser.Description = "Select folder for local repository"
    $folderBrowser.SelectedPath = [Environment]::GetFolderPath('UserProfile')
    $folderBrowser.ShowNewFolderButton = $true
    
    if ($folderBrowser.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $deployDirTextBox.Text = $folderBrowser.SelectedPath
    }
})

$btnCidrCheck.Add_Click({
    $btnCidrCheck.Text = "Checking..."
    $btnCidrCheck.Enabled = $false
    try {
        $cidr = $txtCidrInput.Text.Trim()
        if ([string]::IsNullOrWhiteSpace($cidr)) {
            Show-Message "Please enter a CIDR to check." "Error"
            return
        }
        
        # First validate if it's a valid private CIDR
        if (-not (Is-ValidPrivateCidr $cidr)) {
            $lblCidrResult.ForeColor = [System.Drawing.Color]::Red
            $lblCidrResult.Text = "INVALID: '$cidr' is not a valid private CIDR range. Use: 10.x.0.0/16, 172.16-31.0.0/16, or 192.168.0.0/16"
            Show-Message "Invalid CIDR Range: '$cidr'`n`nValid private CIDR ranges (RFC 1918):`n- 10.0.0.0/16 to 10.255.0.0/16`n- 172.16.0.0/16 to 172.31.0.0/16`n- 192.168.0.0/16`n`nExample: Try 10.1.0.0/16 or 172.20.0.0/16" "Invalid CIDR"
            return
        }
        
        $existingCidrs = Get-ExistingVpcCidrs
        if ($existingCidrs.Count -eq 0) {
            Show-Message "No existing VPCs found." "Warning"
            return
        }
        $conflict = $false
        foreach ($existing in $existingCidrs) {
            if ($existing -eq $cidr) {
                $conflict = $true
                break
            }
        }
        if (-not $conflict) {
            $lblCidrResult.ForeColor = [System.Drawing.Color]::Green
            $lblCidrResult.Text = "CIDR $cidr is available and has been added to deployment settings."
            $vpcTextBox.Text = $cidr
            $btnCidrCheck.Text = "CIDR Added"
        }
        else {
            $lblCidrResult.ForeColor = [System.Drawing.Color]::Red
            $lblCidrResult.Text = "CIDR $cidr conflicts with existing VPC."
        }
    }
    catch {
        Show-Message "Failed to retrieve CIDRs. $_" "Error"
    }
    finally {
        $btnCidrCheck.Enabled = $true
        if ($btnCidrCheck.Text -ne "CIDR Added") {
            $btnCidrCheck.Text = "Check CIDR"
        }
    }
})
# Deploy Button Click Event with T-Shirt Sizing
$deployButton.Add_Click({
    $statusTextBox.Clear()
    $statusTextBox.AppendText("Starting GenAI Workbench deployment...`r`n")
    $deployButton.Enabled = $false
    $form.Enabled = $false
    
    try {
        # Get selected t-shirt size
        $selectedIndex = $sizeComboBox.SelectedIndex
        $sizeKey = @('dev', 'medium-prod', 'enterprise-prod')[$selectedIndex]
        $selectedConfig = $script:EnvironmentConfigs[$sizeKey]
        
        $statusTextBox.AppendText("$($selectedConfig.DisplayName) - $($selectedConfig.Description)`r`n")
        $statusTextBox.AppendText("Resources: API $($selectedConfig.ApiCpu)CPU/$($selectedConfig.ApiMemory)MB, UI $($selectedConfig.UiCpu)CPU/$($selectedConfig.UiMemory)MB`r`n")
        $statusTextBox.AppendText("Estimated Cost: $($selectedConfig.Cost)`r`n`r`n")
        
        # Validate inputs
        $vpcCidr = $vpcTextBox.Text.Trim()
        $keyPair = $keyTextBox.Text.Trim()
        $region = $regionTextBox.Text.Trim()
        $accountNumber = $accountTextBox.Text.Trim()
        $environment = $sizeKey  # Use selected t-shirt size
        $s3Uri = $s3TextBox.Text.Trim()
        $repo = $gitTextBox.Text.Trim()
        $deployDir = $deployDirTextBox.Text.Trim()
        $accessKey = $txtAccessKey.Text.Trim()
        $secretKey = $txtSecretKey.Text.Trim()
        $sessionToken = $txtSessionToken.Text.Trim()
        
        if (-not (Is-ValidPrivateCidr $vpcCidr)) {
            $statusTextBox.AppendText("ERROR: Invalid VPC CIDR '$vpcCidr'. Must use RFC 1918 private ranges:`r`n")
            $statusTextBox.AppendText("  - 10.0.0.0/16 to 10.255.0.0/16 (Class A private)`r`n")
            $statusTextBox.AppendText("  - 172.16.0.0/16 to 172.31.0.0/16 (Class B private)`r`n")
            $statusTextBox.AppendText("  - 192.168.0.0/16 (Class C private)`r`n")
            return
        }
        
        if (-not $keyPair -or -not $region -or -not $accountNumber) {
            $statusTextBox.AppendText("ERROR: Key pair name, region, and account number are required`r`n")
            return
        }
        
        if (-not $accessKey -or -not $secretKey) {
            $statusTextBox.AppendText("ERROR: AWS credentials are required`r`n")
            return
        }
        
        # Validate account number format (12 digits)
        if ($accountNumber -notmatch '^\d{12}$') {
            $statusTextBox.AppendText("ERROR: AWS Account Number must be exactly 12 digits`r`n")
            return
        }
        
        # Clear S3 URI if default
        if ($s3Uri -eq "s3://my-bucket/templates/genai-workbench.json") {
            $s3Uri = ""
        }
        
        $statusTextBox.AppendText("Environment: $environment`r`n")
        $statusTextBox.AppendText("VPC CIDR: $vpcCidr`r`n")
        $statusTextBox.AppendText("Region: $region`r`n")
        if ($s3Uri) {
            $statusTextBox.AppendText("S3 Template URI: $s3Uri`r`n")
        }
        $statusTextBox.AppendText("`r`n")
        
        # Set AWS credentials
        $env:AWS_ACCESS_KEY_ID = $accessKey
        $env:AWS_SECRET_ACCESS_KEY = $secretKey
        if (-not [string]::IsNullOrWhiteSpace($sessionToken)) {
            $env:AWS_SESSION_TOKEN = $sessionToken
        }
        
        # Test AWS credentials before proceeding
        $statusTextBox.AppendText("Validating AWS credentials...`r`n")
        try {
            $callerIdentity = aws sts get-caller-identity --output json 2>&1
            if ($LASTEXITCODE -ne 0) {
                $statusTextBox.AppendText("ERROR: AWS credentials validation failed: $callerIdentity`r`n")
                return
            }
            $identity = $callerIdentity | ConvertFrom-Json
            if ($identity.Account -ne $accountNumber) {
                $statusTextBox.AppendText("ERROR: Account number mismatch. Expected: $accountNumber, Actual: $($identity.Account)`r`n")
                return
            }
            $statusTextBox.AppendText("AWS credentials validated successfully`r`n")
        } catch {
            $statusTextBox.AppendText("ERROR: Failed to validate AWS credentials: $_`r`n")
            return
        }
        
        # Step 1: Clone repository
        $statusTextBox.AppendText("Step 1: Cloning repository...`r`n")
        Clone-Repository $repo $deployDir
        $statusTextBox.AppendText("Repository cloned successfully`r`n")
        
        # Step 2: Build Docker images
        $statusTextBox.AppendText("Step 2: Building Docker images...`r`n")
        $dockerBuildSuccess = Build-DockerImages $deployDir
        
        # Step 3: Push to ECR if build successful
        $containerImage = "public.ecr.aws/docker/library/nginx:alpine"
        if ($dockerBuildSuccess) {
            $statusTextBox.AppendText("Step 3: Pushing images to ECR...`r`n")
            $statusTextBox.Refresh()
            $ecrImage = Push-ToECR $accountNumber $region $environment
            if ($ecrImage) {
                $containerImage = $ecrImage
                $statusTextBox.AppendText("Using ECR image: $containerImage`r`n")
            } else {
                $statusTextBox.AppendText("ECR push failed, using default container`r`n")
            }
        } else {
            $statusTextBox.AppendText("Using default nginx container (no custom images built)`r`n")
        }
        $statusTextBox.Refresh()
        
        # Step 4: Generate CloudFormation template
        $statusTextBox.AppendText("Step 4: Generating CloudFormation template...`r`n")
        $template = Generate-CloudFormationTemplate -vpcCidr $vpcCidr -keyPairName $keyPair -environment $environment -ecrImageUri $containerImage
        
        # Step 5: Deploy stack
        $config = $script:EnvironmentConfigs[$environment]
        $stackName = "genai-workbench$($config.Suffix)"
        
        $statusTextBox.AppendText("Step 5: Deploying CloudFormation stack: $stackName`r`n")
        
        # Show expectation-setting message
        Show-Message "CloudFormation deployment is starting. This process will create your AWS infrastructure including VPC, ECS cluster, load balancer, and other resources.`n`nExpected time: 5-15 minutes`n`nYou can monitor progress in the status window and AWS CloudFormation console." "Deployment In Progress"
        
        $success = Deploy-CloudFormation -stackName $stackName -templateContent $template -region $region -s3Uri $s3Uri
        
        if ($success) {
            $statusTextBox.AppendText("`r`nDEPLOYMENT COMPLETED SUCCESSFULLY!`r`n")
            
            # Get stack outputs
            $outputs = aws cloudformation describe-stacks --stack-name $stackName --region $region --query "Stacks[0].Outputs" --output json 2>$null
            if ($outputs) {
                $outputsObj = $outputs | ConvertFrom-Json
                $statusTextBox.AppendText("`r`nStack Outputs:`r`n")
                foreach ($output in $outputsObj) {
                    $statusTextBox.AppendText("$($output.Description): $($output.OutputValue)`r`n")
                }
            }
            
            $statusTextBox.AppendText("`r`nYour GenAI Workbench infrastructure is now deployed!`r`n")
            $statusTextBox.AppendText("Check the AWS Console for detailed resource information.`r`n")
        } else {
            $statusTextBox.AppendText("`r`nDEPLOYMENT FAILED!`r`n")
            
            # Get more detailed error information
            $stackEvents = aws cloudformation describe-stack-events --stack-name $stackName --region $region --query "StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='UPDATE_FAILED'].{Resource:LogicalResourceId,Reason:ResourceStatusReason}" --output json 2>$null
            if ($stackEvents) {
                try {
                    $events = $stackEvents | ConvertFrom-Json
                    if ($events.Count -gt 0) {
                        $statusTextBox.AppendText("Stack creation errors:`r`n")
                        foreach ($event in $events) {
                            $statusTextBox.AppendText("- $($event.Resource): $($event.Reason)`r`n")
                        }
                    }
                } catch {
                    $statusTextBox.AppendText("Could not parse stack events`r`n")
                }
            }
            
            $statusTextBox.AppendText("Check AWS CloudFormation console for detailed error information.`r`n")
        }
    }
    catch {
        $statusTextBox.AppendText("`r`nDEPLOYMENT ERROR: $_`r`n")
    }
    finally {
        # Clear AWS credentials from environment
        try {
            $env:AWS_ACCESS_KEY_ID = $null
            $env:AWS_SECRET_ACCESS_KEY = $null
            $env:AWS_SESSION_TOKEN = $null
        } catch { }
        
        $deployButton.Enabled = $true
        $form.Enabled = $true
        $statusTextBox.AppendText("`r`nDeployment process completed.`r`n")
    }
})

# Attach tabs and show form
$tabControl.Controls.Add($tabPreDeploy)
$tabControl.Controls.Add($tabDeploy)
$form.Controls.Add($tabControl)
$form.Topmost = $true
$form.Add_Shown({
    $form.Activate()
    # Start on Pre-Deployment tab
    $tabControl.SelectedTab = $tabPreDeploy
})

[void]$form.ShowDialog()