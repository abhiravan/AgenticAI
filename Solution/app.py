"""
Flask Web Application
Provides WebUI for the Jira-GitHub Auto Fix system
"""
from flask import Flask, render_template, request, jsonify, session
import threading
from datetime import datetime
from config import Config
from workflow import WorkflowOrchestrator

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['DEBUG'] = Config.DEBUG

# Store active workflows
active_workflows = {}


@app.route('/')
def index():
    """Main page with Jira issue input"""
    return render_template('index.html')


@app.route('/api/config/validate', methods=['GET'])
def validate_config():
    """Validate configuration"""
    try:
        Config.validate()
        return jsonify({
            'success': True,
            'message': 'Configuration is valid'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/fetch-issue', methods=['POST'])
def fetch_issue():
    """
    Fetch Jira issue details
    
    Request body:
        {
            "issue_key": "PROJ-123"
        }
    """
    try:
        data = request.get_json()
        issue_key = data.get('issue_key', '').strip().upper()
        
        if not issue_key:
            return jsonify({
                'success': False,
                'error': 'Issue key is required'
            }), 400
        
        # Import here to avoid circular imports
        from jira_service import JiraService
        
        jira_service = JiraService()
        result = jira_service.fetch_issue(issue_key)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/create-pr', methods=['POST'])
def create_pr():
    """
    Start the workflow to create a PR for a Jira issue
    
    Request body:
        {
            "issue_key": "PROJ-123"
        }
    """
    try:
        data = request.get_json()
        issue_key = data.get('issue_key', '').strip().upper()
        
        if not issue_key:
            return jsonify({
                'success': False,
                'error': 'Issue key is required'
            }), 400
        
        # Generate workflow ID
        workflow_id = f"{issue_key}_{datetime.utcnow().timestamp()}"
        
        # Create orchestrator
        orchestrator = WorkflowOrchestrator()
        
        # Store workflow
        active_workflows[workflow_id] = {
            'orchestrator': orchestrator,
            'status': 'running',
            'started_at': datetime.utcnow().isoformat(),
            'result': None
        }
        
        # Run workflow in background thread
        def run_workflow():
            try:
                result = orchestrator.execute(issue_key)
                active_workflows[workflow_id]['status'] = 'completed'
                active_workflows[workflow_id]['result'] = result
                active_workflows[workflow_id]['completed_at'] = datetime.utcnow().isoformat()
            except Exception as e:
                active_workflows[workflow_id]['status'] = 'failed'
                active_workflows[workflow_id]['result'] = {
                    'success': False,
                    'error': str(e)
                }
                active_workflows[workflow_id]['completed_at'] = datetime.utcnow().isoformat()
        
        thread = threading.Thread(target=run_workflow)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'workflow_id': workflow_id,
            'message': 'Workflow started'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/workflow/<workflow_id>/status', methods=['GET'])
def get_workflow_status(workflow_id):
    """
    Get workflow status and progress
    
    Returns:
        {
            "status": "running|completed|failed",
            "progress_log": [...],
            "result": {...}
        }
    """
    try:
        if workflow_id not in active_workflows:
            return jsonify({
                'success': False,
                'error': 'Workflow not found'
            }), 404
        
        workflow = active_workflows[workflow_id]
        orchestrator = workflow['orchestrator']
        
        return jsonify({
            'success': True,
            'status': workflow['status'],
            'started_at': workflow['started_at'],
            'completed_at': workflow.get('completed_at'),
            'progress_log': orchestrator.get_progress_log(),
            'result': workflow.get('result')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/workflow/<workflow_id>', methods=['DELETE'])
def delete_workflow(workflow_id):
    """Delete a workflow from memory"""
    try:
        if workflow_id in active_workflows:
            del active_workflows[workflow_id]
        
        return jsonify({
            'success': True,
            'message': 'Workflow deleted'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'active_workflows': len(active_workflows)
    })


@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    try:
        # Validate configuration on startup
        Config.validate()
        print("Configuration validated successfully")
        print(f"Starting server on http://localhost:5000")
        
        # Run Flask app
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=Config.DEBUG
        )
    except Exception as e:
        print(f"Failed to start application: {e}")
        exit(1)
