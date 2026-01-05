"""Check if agents are producing analysis."""
import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.getcwd())

try:
    from core_kernel.mongodb_schema import get_mongo_client, get_collection
    from config.settings import settings
    
    mongo_client = get_mongo_client()
    db = mongo_client[settings.mongodb_db_name]
    analysis_collection = get_collection(db, "agent_decisions")
    
    # Check for analysis in the last 10 minutes
    cutoff_time = datetime.now() - timedelta(minutes=10)
    cutoff_iso = cutoff_time.isoformat()
    
    # Find latest analysis
    latest_analysis = analysis_collection.find_one(
        sort=[("timestamp", -1)]
    )
    
    if not latest_analysis:
        print('AGENT_ANALYSIS_NOT_FOUND')
        print('No agent analysis found in MongoDB')
        sys.exit(1)
    
    # Check timestamp
    analysis_time_str = latest_analysis.get("timestamp", "")
    if analysis_time_str:
        try:
            # Handle various timestamp formats
            timestamp_clean = analysis_time_str.replace('Z', '+00:00')
            # Remove microseconds if present for compatibility
            if '.' in timestamp_clean and '+' in timestamp_clean:
                parts = timestamp_clean.split('+')
                if len(parts) == 2:
                    timestamp_clean = parts[0].split('.')[0] + '+' + parts[1]
            elif '.' in timestamp_clean:
                timestamp_clean = timestamp_clean.split('.')[0]
            
            try:
                analysis_time = datetime.fromisoformat(timestamp_clean)
            except ValueError:
                # Try parsing without timezone
                timestamp_no_tz = timestamp_clean.split('+')[0].split('-')[0:3]
                if len(timestamp_no_tz) >= 3:
                    timestamp_no_tz = '-'.join(timestamp_no_tz[:3]) + ' ' + timestamp_clean.split('T')[1].split('+')[0].split('.')[0]
                    analysis_time = datetime.strptime(timestamp_no_tz, '%Y-%m-%d %H:%M:%S')
                else:
                    raise
            
            if analysis_time.tzinfo is None:
                # Assume local time if no timezone
                now = datetime.now()
                time_diff = (now - analysis_time).total_seconds() / 60  # minutes
            else:
                from datetime import timezone
                now = datetime.now(timezone.utc)
                time_diff = (now - analysis_time).total_seconds() / 60  # minutes
            
            if time_diff > 10:
                print('AGENT_ANALYSIS_STALE')
                print(f'Latest analysis is {time_diff:.1f} minutes old (should be < 10 minutes)')
                sys.exit(1)
        except Exception as e:
            print(f'AGENT_ANALYSIS_TIMESTAMP_ERROR: {str(e)[:50]}')
            # Don't exit on timestamp error - continue with other checks
            pass
    
    # Check agent decisions exist
    agent_decisions = latest_analysis.get("agent_decisions", {})
    if not agent_decisions:
        print('AGENT_ANALYSIS_EMPTY')
        print('Agent analysis found but agent_decisions is empty')
        sys.exit(1)
    
    # Check required agents
    required_agents = ['technical', 'fundamental', 'sentiment', 'macro']
    missing_agents = []
    empty_agents = []
    
    for agent_name in required_agents:
        if agent_name not in agent_decisions:
            missing_agents.append(agent_name)
        else:
            agent_data = agent_decisions[agent_name]
            # Check if agent data is empty or just default values
            if not agent_data or agent_data == {} or agent_data == []:
                empty_agents.append(agent_name)
            elif isinstance(agent_data, dict):
                # Check for common empty/default patterns
                if all(v is None or v == "" or v == "No recent news available" 
                       for v in agent_data.values() if not isinstance(v, (int, float))):
                    empty_agents.append(agent_name)
            elif isinstance(agent_data, str):
                if agent_data.lower() in ['none', 'null', '', 'no recent news available']:
                    empty_agents.append(agent_name)
    
    if missing_agents:
        print('AGENT_ANALYSIS_MISSING_AGENTS')
        print(f'Missing agents: {", ".join(missing_agents)}')
        sys.exit(1)
    
    if empty_agents:
        print('AGENT_ANALYSIS_EMPTY_AGENTS')
        print(f'Agents with empty analysis: {", ".join(empty_agents)}')
        sys.exit(1)
    
    # Check that analysis has meaningful content
    # At least one agent should have non-empty analysis
    has_content = False
    for agent_name, agent_data in agent_decisions.items():
        if isinstance(agent_data, dict):
            # Check if dict has meaningful keys/values
            if len(agent_data) > 0:
                non_empty_values = [v for v in agent_data.values() 
                                  if v is not None and v != "" and v != "No recent news available"]
                if non_empty_values:
                    has_content = True
                    break
        elif isinstance(agent_data, str) and agent_data.strip():
            if agent_data.lower() not in ['none', 'null', '']:
                has_content = True
                break
    
    if not has_content:
        print('AGENT_ANALYSIS_NO_CONTENT')
        print('Agent analysis exists but contains no meaningful content')
        sys.exit(1)
    
    # Success
    signal = latest_analysis.get("final_signal", "UNKNOWN")
    timestamp = latest_analysis.get("timestamp", "UNKNOWN")
    agent_count = len(agent_decisions)
    
    print('AGENT_ANALYSIS_OK')
    print(f'Signal: {signal}, Agents: {agent_count}, Time: {timestamp[:19] if len(timestamp) > 19 else timestamp}')
    sys.exit(0)
    
except ImportError as e:
    print('AGENT_ANALYSIS_MODULE_MISSING')
    print(f'Required module missing: {str(e)[:50]}')
    sys.exit(1)
except Exception as e:
    print('AGENT_ANALYSIS_ERROR')
    print(f'Error checking agent analysis: {str(e)[:100]}')
    sys.exit(1)

