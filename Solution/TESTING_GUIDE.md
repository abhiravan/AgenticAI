# 🧪 Testing Guide for Jira-GitHub Auto Fix Solution

## Prerequisites Checklist

Before testing, ensure you have:

- [ ] Python 3.10+ installed
- [ ] Git installed and configured
- [ ] Valid Jira account with API access
- [ ] Azure OpenAI resource with API key
- [ ] GitHub account with personal access token
- [ ] `.env` file configured in parent directory
- [ ] Test Jira issue available

## Setup for Testing

### 1. Environment Setup

```powershell
# Navigate to Solution folder
cd "c:\Users\asiva05\OneDrive - Safeway, Inc\Desktop\MEBP\MCP\AgenticAI V1\AgenticAI-1\Solution"

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Verify Configuration

```powershell
# Test Python and dependencies
python --version    # Should be 3.10+
pip list           # Should show Flask, jira, openai, etc.

# Test Git
git --version      # Should show Git version
```

### 3. Configuration Validation

Create a simple test script `test_config.py`:

```python
from config import Config

try:
    Config.validate()
    print("✅ Configuration is valid!")
    print(f"Jira URL: {Config.JIRA_BASE_URL}")
    print(f"GitHub Repo: {Config.get_github_repo()}")
    print(f"Azure Endpoint: {Config.AZURE_OPENAI_ENDPOINT}")
except Exception as e:
    print(f"❌ Configuration error: {e}")
```

Run it:
```powershell
python test_config.py
```

## Test Scenarios

### Test 1: Configuration Validation

**Purpose**: Verify all environment variables are loaded correctly

**Steps**:
1. Run `python app.py`
2. Check console output for "Configuration validated successfully"

**Expected Result**:
```
Configuration validated successfully
Starting server on http://localhost:5000
 * Running on http://0.0.0.0:5000
```

**Troubleshooting**:
- If "Missing required configuration" appears, check `.env` file
- Verify all required variables are set

---

### Test 2: Web UI Access

**Purpose**: Verify web interface loads correctly

**Steps**:
1. Start the application: `python app.py`
2. Open browser: `http://localhost:5000`

**Expected Result**:
- Beautiful gradient header
- "Jira-GitHub Auto Fix" title
- Input field for Jira issue key
- "Fetch Issue" button

**Troubleshooting**:
- If port 5000 is busy, Flask will show error
- Check firewall settings if browser can't connect

---

### Test 3: Jira Issue Fetch

**Purpose**: Test Jira API integration

**Test Data**:
- Use a real Jira issue key from your instance
- Example: `PROJ-123`

**Steps**:
1. Access web UI: `http://localhost:5000`
2. Enter Jira issue key
3. Click "Fetch Issue"

**Expected Result**:
- Issue card appears below input
- Shows: Key, Summary, Status, Priority, Assignee, Description
- "Auto-Fix & Create PR" button appears

**Success Indicators**:
```
✅ Issue key retrieved
✅ Summary displayed
✅ Description parsed (even if ADF format)
✅ Status and priority shown
✅ Link to Jira issue works
```

**Troubleshooting**:
- **Error: "Unable to connect to Jira"**
  - Check JIRA_BASE_URL in .env
  - Verify Jira is accessible from your network
  
- **Error: "Authentication failed"**
  - Verify JIRA_EMAIL and JIRA_TOKEN in .env
  - Regenerate API token if needed
  
- **Error: "Issue not found"**
  - Check issue key spelling
  - Verify you have access to the issue

---

### Test 4: Full Workflow (Happy Path)

**Purpose**: Test complete automation from Jira to PR

**Test Data**:
- Simple bug issue in Jira
- Code change that's relatively straightforward
- Example: "Fix typo in function name" or "Add null check"

**Steps**:
1. Fetch a Jira issue
2. Click "Auto-Fix & Create PR"
3. Watch progress log
4. Wait for completion (~2-5 minutes)

**Expected Progress Steps**:
```
1. fetch_issue         - Fetching Jira issue
   ✅ Success: Fetched issue details

2. analyze_issue       - Analyzing issue with AI
   ✅ Success: Analysis completed

3. prepare_repo        - Preparing Git repository
   ✅ Success: Repository cloned/updated

4. create_branch       - Creating branch: fix/proj-123-xxxxxx
   ✅ Success: Branch created

5. generate_fix        - Generating code fix with AI
   ✅ Success: Code fix generated

6. apply_patch         - Applying code changes
   ✅ Success: Code changes applied

7. commit_changes      - Committing changes
   ✅ Success: Changes committed

8. push_branch         - Pushing branch to GitHub
   ✅ Success: Branch pushed

9. create_pr           - Creating pull request
   ✅ Success: Pull request created: #42
```

**Expected Final Result**:
- Success message displayed
- PR number shown
- PR URL link displayed
- Clicking link opens GitHub PR

**Verify on GitHub**:
- Go to repository
- Find the new PR
- Check PR title matches issue
- Check PR description has:
  - Issue link
  - Root cause analysis
  - Proposed fix details
  - Files modified
  - Testing strategy

**Success Criteria**:
- [ ] All progress steps complete without errors
- [ ] PR created successfully
- [ ] PR has proper title and description
- [ ] Code changes are relevant to the issue
- [ ] Branch naming follows convention

---

### Test 5: Error Handling - Patch Apply Failure

**Purpose**: Test automatic patch refinement

**Simulation**:
This typically happens naturally when AI generates a patch that doesn't match the exact code structure.

**Expected Behavior**:
```
⚠️ Warning: Initial patch failed, refining...
✅ Success: Refined patch applied
```

**Indicators of Good Error Handling**:
- System doesn't crash
- Automatically requests refined patch from AI
- Second attempt succeeds
- Progress log shows the refinement step

---

### Test 6: API Endpoints

**Purpose**: Test REST API endpoints directly

**Tools**: Use PowerShell, Postman, or curl

**Test Cases**:

#### A. Health Check
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/health"
```

**Expected**:
```json
{
  "success": true,
  "status": "healthy",
  "timestamp": "2024-...",
  "active_workflows": 0
}
```

#### B. Fetch Issue
```powershell
$body = @{
    issue_key = "PROJ-123"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/api/fetch-issue" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

**Expected**:
```json
{
  "success": true,
  "data": {
    "key": "PROJ-123",
    "summary": "...",
    ...
  }
}
```

#### C. Create PR
```powershell
$body = @{
    issue_key = "PROJ-123"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:5000/api/create-pr" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

# Get workflow ID
$workflowId = $response.workflow_id

# Poll status
Start-Sleep -Seconds 2
Invoke-RestMethod -Uri "http://localhost:5000/api/workflow/$workflowId/status"
```

---

## Performance Testing

### Test 7: Response Times

**Metrics to Measure**:

1. **Jira Fetch**: < 2 seconds
2. **AI Analysis**: 5-15 seconds
3. **Code Generation**: 10-20 seconds
4. **Git Operations**: 2-5 seconds
5. **PR Creation**: 1-3 seconds

**Total Expected Time**: 2-5 minutes

**How to Test**:
- Add timing logs in workflow.py
- Use browser developer tools (Network tab)
- Check progress log timestamps

---

## Load Testing

### Test 8: Multiple Concurrent Requests

**Purpose**: Test system under load

**Steps**:
1. Open multiple browser tabs
2. Start workflows in different tabs
3. Monitor system resources

**Expected Behavior**:
- Each workflow runs independently
- No interference between workflows
- System remains responsive

**Note**: Production deployment would need proper queuing system

---

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: "Module not found"
**Solution**:
```powershell
pip install -r requirements.txt
```

#### Issue: "Port 5000 already in use"
**Solution**:
```powershell
# Find process using port 5000
netstat -ano | findstr :5000
# Kill the process
taskkill /F /PID <process_id>
```

#### Issue: "Git authentication failed"
**Solution**:
- Check GitHub token has repo permissions
- Verify token hasn't expired
- Try regenerating token

#### Issue: "Azure OpenAI rate limit"
**Solution**:
- Wait for rate limit reset
- Check Azure quota settings
- Implement retry with backoff (future enhancement)

#### Issue: "Patch won't apply"
**Solution**:
- Ensure base branch is up to date
- Check if code has changed since analysis
- May need manual intervention

---

## Test Checklist

Use this checklist for comprehensive testing:

### Pre-Launch Tests
- [ ] Configuration loads successfully
- [ ] All dependencies installed
- [ ] Environment variables validated
- [ ] Web UI accessible
- [ ] Health endpoint responds

### Functional Tests
- [ ] Jira issue fetch works
- [ ] Issue details display correctly
- [ ] AI analysis completes
- [ ] Repository clones/updates
- [ ] Branch creation succeeds
- [ ] Patch generates
- [ ] Patch applies
- [ ] Commit succeeds
- [ ] Push to GitHub works
- [ ] PR creation succeeds

### UI/UX Tests
- [ ] UI loads without errors
- [ ] Buttons work correctly
- [ ] Progress updates in real-time
- [ ] Success message displays
- [ ] Error messages are clear
- [ ] Links work correctly
- [ ] Responsive on different screen sizes

### Integration Tests
- [ ] Jira API connection
- [ ] Azure OpenAI API connection
- [ ] GitHub API connection
- [ ] Git operations
- [ ] End-to-end workflow

### Error Handling Tests
- [ ] Invalid Jira key
- [ ] Network errors
- [ ] API rate limits
- [ ] Patch application failures
- [ ] Git conflicts
- [ ] Missing permissions

---

## Automated Testing (Future)

For production, implement:

### Unit Tests
```python
def test_jira_service():
    service = JiraService()
    result = service.fetch_issue("PROJ-123")
    assert result['success'] == True

def test_llm_analysis():
    service = LLMService()
    result = service.analyze_issue(sample_issue)
    assert 'root_cause' in result['data']
```

### Integration Tests
```python
def test_full_workflow():
    orchestrator = WorkflowOrchestrator()
    result = orchestrator.execute("TEST-1")
    assert result['success'] == True
    assert 'pr_url' in result
```

### End-to-End Tests
- Use Selenium for UI testing
- Mock external APIs for consistent testing
- Set up CI/CD pipeline

---

## Success Metrics

Consider the solution successful if:

✅ **Reliability**: 95%+ success rate on valid issues  
✅ **Performance**: < 5 minutes average completion time  
✅ **Quality**: Generated PRs are mergeable  
✅ **Usability**: Non-technical users can operate  
✅ **Error Handling**: Graceful failures with clear messages  

---

## Next Steps After Testing

Once testing is complete:

1. **Document Issues**: Record any bugs or improvements
2. **Optimize Performance**: Identify bottlenecks
3. **Enhance Error Handling**: Add more retry logic
4. **Add Logging**: Implement proper logging system
5. **Security Audit**: Review security practices
6. **Deploy**: Move to production environment

---

## Test Report Template

After testing, document results:

```
# Test Report

Date: [Date]
Tester: [Name]
Environment: [Development/Staging/Production]

## Test Results

| Test Case | Status | Notes |
|-----------|--------|-------|
| Config Validation | ✅ Pass | All variables loaded |
| Web UI Access | ✅ Pass | Loads correctly |
| Jira Fetch | ✅ Pass | Issue displayed |
| Full Workflow | ✅ Pass | PR created #42 |
| Error Handling | ✅ Pass | Graceful recovery |

## Issues Found

1. [Issue description]
2. [Issue description]

## Recommendations

1. [Recommendation]
2. [Recommendation]

## Overall Assessment

[Pass/Fail] - [Summary]
```

---

🎉 **Happy Testing!**

Remember: The goal is to ensure a smooth, reliable experience from Jira issue to GitHub PR with minimal user intervention.
