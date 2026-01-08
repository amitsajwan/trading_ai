// Agent timestamp updater for dashboard
// This script updates the "Updated X ago" timestamps on agent status cards

async function updateAgentStatusTimestamps() {
    try {
        const response = await fetch('/api/agent-status');
        if (!response.ok) {
            console.log('Agent status API not available');
            return;
        }
        
        const data = await response.json();
        const freshness = data.data_freshness || {};
        const lastAnalysis = freshness.analysis_timestamp || data.last_analysis;
        
        if (lastAnalysis) {
            const analysisDate = new Date(lastAnalysis);
            const now = new Date();
            const diffMs = now - analysisDate;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            
            let timeAgo;
            if (diffMins < 1) timeAgo = 'now';
            else if (diffMins < 60) timeAgo = diffMins + 'm ago';
            else if (diffHours < 24) timeAgo = diffHours + 'h ago';
            else timeAgo = Math.floor(diffHours / 24) + 'd ago';
            
            const formattedTime = analysisDate.toLocaleString('en-IN', { 
                timeZone: 'Asia/Kolkata', 
                hour: '2-digit', 
                minute: '2-digit',
                hour12: true 
            });
            
            const displayText = `● Updated ${timeAgo} (${formattedTime} IST)`;
            const titleText = `Last analysis: ${analysisDate.toLocaleString()}`;
            
            // Update all agent timestamp headers
            const timestampIds = [
                'agent-summary-timestamp',
                'agent-conditions-timestamp',
                'agent-decisions-timestamp'
            ];
            
            timestampIds.forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.textContent = displayText;
                    el.title = titleText;
                    el.style.color = freshness.analysis_stale ? '#dc3545' : '#28a745';
                }
            });
            
            console.log(`Agent timestamps updated: ${timeAgo}`);
        } else {
            // No analysis data available
            const noDataText = '● No analysis data';
            const timestampIds = [
                'agent-summary-timestamp',
                'agent-conditions-timestamp',
                'agent-decisions-timestamp'
            ];
            
            timestampIds.forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.textContent = noDataText;
                    el.style.color = '#dc3545';
                }
            });
        }
    } catch (error) {
        console.log('Error updating agent timestamps:', error);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Update immediately
    updateAgentStatusTimestamps();
    
    // Update every 10 seconds
    setInterval(updateAgentStatusTimestamps, 10000);
});
