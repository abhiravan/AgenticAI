from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv
from jira_service import JiraService
from ai_fix_service import AIFixService
from git_service import GitService

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize services
jira_service = JiraService()
ai_service = AIFixService()
git_service = GitService()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/fetch_jira', methods=['POST'])
def fetch_jira():
    """Fetch Jira issue details"""
    jira_number = request.json.get('jira_number')
    
    if not jira_number:
        return jsonify({'error': 'Jira number is required'}), 400
    
    result = jira_service.fetch_issue(jira_number)
    return jsonify(result)

@app.route('/analyze_issue', methods=['POST'])
def analyze_issue():
    """Analyze the issue and identify files to fix"""
    data = request.json
    issue_summary = data.get('summary')
    issue_description = data.get('description')
    
    if not issue_summary or not issue_description:
        return jsonify({'error': 'Issue summary and description are required'}), 400
    
    result = ai_service.analyze_issue(issue_description, issue_summary)
    return jsonify(result)

@app.route('/show_file', methods=['POST'])
def show_file():
    """Show the content of a specific file"""
    filename = request.json.get('filename')
    
    if not filename:
        return jsonify({'error': 'Filename is required'}), 400
    
    result = git_service.get_file_content(filename)
    return jsonify(result)

@app.route('/fix_issue', methods=['POST'])  
def fix_issue():
    """Generate and apply AI-powered fix for the issue"""
    data = request.json
    issue_summary = data.get('summary')
    issue_description = data.get('description')
    filename = data.get('filename')
    jira_key = data.get('jira_key')
    
    if not all([issue_summary, issue_description, filename, jira_key]):
        return jsonify({'error': 'All parameters are required'}), 400
    
    # Get current file content
    file_result = git_service.get_file_content(filename)
    if not file_result.get('success'):
        return jsonify(file_result), 400
    
    file_content = file_result['content']
    
    # Generate fix using AI
    fixed_content = ai_service.generate_fix(issue_description, issue_summary, file_content, filename)
    
    if fixed_content.startswith('Error'):
        return jsonify({'error': fixed_content}), 500
    
    # Create branch for the fix
    branch_result = git_service.create_branch(jira_key)
    if not branch_result.get('success'):
        return jsonify(branch_result), 500
    
    branch_name = branch_result['branch']
    
    # Apply the fix
    commit_message = f"fix({jira_key}): {issue_summary}"
    apply_result = git_service.apply_fix(filename, fixed_content, commit_message)
    
    if not apply_result.get('success'):
        return jsonify(apply_result), 500
    
    # Push branch
    push_result = git_service.push_branch(branch_name)
    if not push_result.get('success'):
        return jsonify(push_result), 500
    
    # Create pull request
    pr_result = git_service.create_pull_request(
        branch_name, jira_key, issue_summary, 
        "AI-generated fix based on issue analysis"
    )
    
    return jsonify({
        'success': True,
        'message': 'Fix has been applied and PR created',
        'branch': branch_name,
        'pr_url': pr_result.get('pr_url'),
        'fixed_content': fixed_content
    })

if __name__ == '__main__':
    app.run(debug=True)
