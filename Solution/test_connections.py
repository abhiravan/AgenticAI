"""
Diagnostic script to test Jira, GitHub, and Azure OpenAI connections
Run this to verify all services are accessible
"""
import sys
import os

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

print("=" * 60)
print("🔍 Service Connection Diagnostics")
print("=" * 60)

# Test 1: Configuration Validation
print("\n1️⃣ Testing Configuration...")
try:
    Config.validate()
    print("   ✅ All configuration variables present")
except Exception as e:
    print(f"   ❌ Configuration error: {e}")
    sys.exit(1)

# Test 2: Jira Connection
print("\n2️⃣ Testing Jira Connection...")
try:
    from jira import JIRA
    
    print(f"   📍 Connecting to: {Config.JIRA_BASE_URL}")
    print(f"   👤 User: {Config.JIRA_EMAIL}")
    
    jira_client = JIRA(
        server=Config.JIRA_BASE_URL,
        basic_auth=(Config.JIRA_EMAIL, Config.JIRA_TOKEN)
    )
    
    # Test by getting server info
    server_info = jira_client.server_info()
    print(f"   ✅ Connected to Jira!")
    print(f"   📊 Server: {server_info.get('serverTitle', 'N/A')}")
    print(f"   📦 Version: {server_info.get('version', 'N/A')}")
    
    # Try to get current user
    try:
        myself = jira_client.myself()
        print(f"   👤 Authenticated as: {myself.get('displayName', 'N/A')}")
    except:
        pass
        
except Exception as e:
    print(f"   ❌ Jira connection failed: {str(e)}")
    print("\n   💡 Troubleshooting:")
    print("   - Check JIRA_BASE_URL is correct")
    print("   - Verify JIRA_EMAIL is correct")
    print("   - Ensure JIRA_TOKEN is valid (regenerate if needed)")
    print("   - Check if Jira instance is accessible from your network")
    print("   - Try accessing Jira URL in browser first")

# Test 3: Azure OpenAI Connection
print("\n3️⃣ Testing Azure OpenAI Connection...")
try:
    from openai import AzureOpenAI
    
    print(f"   📍 Endpoint: {Config.AZURE_OPENAI_ENDPOINT}")
    print(f"   🚀 Deployment: {Config.AZURE_OPENAI_DEPLOYMENT_NAME}")
    
    client = AzureOpenAI(
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version=Config.AZURE_OPENAI_API_VERSION
    )
    
    # Test with a simple completion
    response = client.chat.completions.create(
        model=Config.AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10
    )
    
    print(f"   ✅ Azure OpenAI connected!")
    print(f"   🤖 Test response received")
    
except Exception as e:
    print(f"   ❌ Azure OpenAI connection failed: {str(e)}")
    print("\n   💡 Troubleshooting:")
    print("   - Check AZURE_OPENAI_ENDPOINT is correct")
    print("   - Verify AZURE_OPENAI_API_KEY is valid")
    print("   - Ensure AZURE_OPENAI_DEPLOYMENT_NAME exists")
    print("   - Check Azure OpenAI resource is active")

# Test 4: GitHub Connection
print("\n4️⃣ Testing GitHub Connection...")
try:
    import requests
    
    print(f"   📍 Repository: {Config.get_github_repo()}")
    
    headers = {
        'Authorization': f'Bearer {Config.GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json'
    }
    
    # Test user authentication
    response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
    
    if response.status_code == 200:
        user_data = response.json()
        print(f"   ✅ GitHub connected!")
        print(f"   👤 Authenticated as: {user_data.get('login', 'N/A')}")
        
        # Test repository access
        repo = Config.get_github_repo()
        if repo:
            repo_response = requests.get(
                f'https://api.github.com/repos/{repo}',
                headers=headers,
                timeout=10
            )
            if repo_response.status_code == 200:
                print(f"   📦 Repository access: ✅")
            else:
                print(f"   ⚠️  Repository access: Limited or denied")
    else:
        print(f"   ❌ GitHub authentication failed: {response.status_code}")
        
except Exception as e:
    print(f"   ❌ GitHub connection failed: {str(e)}")
    print("\n   💡 Troubleshooting:")
    print("   - Check GITHUB_TOKEN is valid")
    print("   - Verify token has repo permissions")
    print("   - Ensure GITHUB_REPO_URL is correct")

# Test 5: Git Installation
print("\n5️⃣ Testing Git Installation...")
try:
    import subprocess
    result = subprocess.run(['git', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   ✅ Git installed: {result.stdout.strip()}")
    else:
        print(f"   ❌ Git not found")
except Exception as e:
    print(f"   ❌ Git check failed: {str(e)}")

print("\n" + "=" * 60)
print("🏁 Diagnostic Complete")
print("=" * 60)
print("\n💡 If any tests failed, fix those issues before running the app")
print("   Run this script again after making changes to verify fixes\n")
