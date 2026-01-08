// ===== API TESTING FUNCTIONS =====

// API base URLs for each service
const API_BASES = {
    'market-data': 'http://localhost:8004',
    'news': 'http://localhost:8005',
    'engine': 'http://localhost:8006',
    'user': 'http://localhost:8007'
};

// Test endpoint function
async function testEndpoint(service, endpoint) {
    const baseUrl = API_BASES[service];
    const responseElement = document.getElementById(`${service}-${endpoint}-response`);

    if (!responseElement) {
        console.error(`Response element not found: ${service}-${endpoint}-response`);
        return;
    }

    responseElement.textContent = 'Loading...';
    responseElement.style.color = '#6b7280';

    try {
        let url, method = 'GET', body = null;

        // Define endpoints for each service
        switch(service) {
            case 'market-data':
                switch(endpoint) {
                    case 'health':
                        url = `${baseUrl}/health`;
                        break;
                    case 'tick':
                        url = `${baseUrl}/api/v1/market/tick/BANKNIFTY`;
                        break;
                    case 'ohlc':
                        url = `${baseUrl}/api/v1/market/ohlc/BANKNIFTY?timeframe=minute&limit=5`;
                        break;
                    case 'options':
                        url = `${baseUrl}/api/v1/options/chain/BANKNIFTY`;
                        break;
                    case 'technical':
                        url = `${baseUrl}/api/v1/technical/indicators/BANKNIFTY`;
                        break;
                }
                break;

            case 'news':
                switch(endpoint) {
                    case 'health':
                        url = `${baseUrl}/health`;
                        break;
                    case 'banknifty':
                        url = `${baseUrl}/api/v1/news/BANKNIFTY`;
                        break;
                    case 'all':
                        url = `${baseUrl}/api/v1/news`;
                        break;
                    case 'sentiment':
                        url = `${baseUrl}/api/v1/news/sentiment`;
                        break;
                    case 'collect':
                        url = `${baseUrl}/api/v1/news/collect`;
                        method = 'POST';
                        body = JSON.stringify({"instruments": ["BANKNIFTY"]});
                        break;
                }
                break;

            case 'engine':
                switch(endpoint) {
                    case 'health':
                        url = `${baseUrl}/health`;
                        break;
                    case 'analyze':
                        url = `${baseUrl}/api/v1/analyze`;
                        method = 'POST';
                        body = JSON.stringify({"instrument": "BANKNIFTY", "context": {}});
                        break;
                    case 'signals':
                        url = `${baseUrl}/api/v1/signals/BANKNIFTY`;
                        break;
                    case 'initialize':
                        url = `${baseUrl}/api/v1/orchestrator/initialize`;
                        method = 'POST';
                        body = JSON.stringify({});
                        break;
                }
                break;

            case 'user':
                switch(endpoint) {
                    case 'health':
                        url = `${baseUrl}/health`;
                        break;
                    case 'positions':
                        url = `${baseUrl}/api/trading/positions`;
                        break;
                    case 'portfolio':
                        url = `${baseUrl}/api/portfolio`;
                        break;
                    case 'trades':
                        url = `${baseUrl}/api/recent-trades?limit=5`;
                        break;
                    case 'stats':
                        url = `${baseUrl}/api/trading/stats`;
                        break;
                    case 'agents':
                        url = `${baseUrl}/api/agent-status`;
                        break;
                }
                break;
        }

        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: body
        });

        const data = await response.json();

        responseElement.style.color = response.ok ? '#10b981' : '#ef4444';
        responseElement.textContent = JSON.stringify(data, null, 2);

        // Add status indicator
        const statusIndicator = `\n--- Status: ${response.status} ${response.statusText} ---`;
        responseElement.textContent += statusIndicator;

    } catch (error) {
        responseElement.style.color = '#ef4444';
        responseElement.textContent = `Error: ${error.message}\n\nPossible issues:\n- Service not running\n- Network connectivity\n- CORS issues\n- Invalid endpoint`;
    }
}

// Test all endpoints for a service
async function testAllEndpoints(service) {
    const endpoints = {
        'market-data': ['health', 'tick', 'ohlc', 'options', 'technical'],
        'news': ['health', 'banknifty', 'all', 'sentiment'],
        'engine': ['health', 'signals'],
        'user': ['health', 'positions', 'portfolio', 'trades', 'stats', 'agents']
    };

    if (endpoints[service]) {
        for (const endpoint of endpoints[service]) {
            await testEndpoint(service, endpoint);
            await new Promise(resolve => setTimeout(resolve, 500)); // Small delay between requests
        }
    }
}

// Test all services
async function testAllServices() {
    const services = ['market-data', 'news', 'engine', 'user'];

    for (const service of services) {
        console.log(`Testing ${service} service...`);
        await testAllEndpoints(service);
        await new Promise(resolve => setTimeout(resolve, 1000)); // Delay between services
    }
}

// Add test all buttons to each section
document.addEventListener('DOMContentLoaded', function() {
    // Add "Test All" buttons to each API section
    const sections = ['market-data-api', 'news-api', 'engine-api', 'user-api'];

    sections.forEach(sectionId => {
        const section = document.getElementById(sectionId);
        if (section) {
            const title = section.querySelector('.section-title');
            if (title) {
                const testAllBtn = document.createElement('button');
                testAllBtn.className = 'btn btn-success';
                testAllBtn.style.marginLeft = '15px';
                testAllBtn.textContent = 'Test All Endpoints';

                const service = sectionId.replace('-api', '');
                testAllBtn.onclick = () => testAllEndpoints(service);

                title.appendChild(testAllBtn);
            }
        }
    });

    // Add global "Test All Services" button
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        const testAllServicesBtn = document.createElement('button');
        testAllServicesBtn.className = 'btn btn-warning';
        testAllServicesBtn.style.margin = '10px';
        testAllServicesBtn.style.width = 'calc(100% - 20px)';
        testAllServicesBtn.textContent = '🔧 Test All Services';
        testAllServicesBtn.onclick = testAllServices;

        sidebar.appendChild(testAllServicesBtn);
    }
});