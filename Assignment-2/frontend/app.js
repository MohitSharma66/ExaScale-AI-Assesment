const API_BASE = (() => {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://127.0.0.1:8001/api';
    }
    if (hostname.includes('railway.app')) {
        return 'https://brilliant-strength-production-df8a.up.railway.app/api';
    }
    return '/api';
})();

let charts = {
    yoy: null,
    hotspot1: null,
    hotspot2: null,
    hotspot3: null,
    trend: null
};

let allRecords = [];
let overrideRecordId = null;

function getToday() {
    return new Date().toISOString().split('T')[0];
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatNumber(num) {
    return Number(num).toLocaleString('en-US', { maximumFractionDigits: 2 });
}

function getScopeBadge(scope) {
    return `<span class="scope-badge scope-${scope}">Scope ${scope}</span>`;
}

function getStatusBadge(isOverride) {
    return isOverride ? 
        '<span class="status-badge status-override">⚠️ Override</span>' : 
        '<span class="status-badge status-original">✅ Original</span>';
}

function getSourceBadge(isExcel) {
    return isExcel ? 
        '<span class="status-badge" style="background:#bee3f8;color:#2b6cb0;">📊 Excel</span>' : 
        '<span class="status-badge" style="background:#c6f6d5;color:#276749;">✏️ User</span>';
}

function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    
    document.getElementById(tabName).classList.add('active');
    
    const tabs = document.querySelectorAll('.tab');
    const tabMap = { 
        'dashboard': 0, 
        'entry': 1, 
        'metrics': 2,
        'intensity': 3,
        'source-details': 4,
        'records': 5,
        'audit': 6
    };
    if (tabMap[tabName] !== undefined) {
        tabs[tabMap[tabName]].classList.add('active');
    }
    
    if (tabName === 'dashboard') refreshDashboard();
    else if (tabName === 'metrics') loadMetrics();
    else if (tabName === 'intensity') updateIntensityAnalysis();
    else if (tabName === 'source-details') loadSourceOptions();
    else if (tabName === 'records') { loadAllRecords(); loadMaterialFilter(); }
    else if (tabName === 'audit') loadAuditLog();
}

async function refreshDashboard() {
    try {
        await Promise.all([
            loadKPIs(),
            loadYoYChart(),
            loadHotspotCharts(),
            loadTrendChart('quarterly')
        ]);
    } catch (error) {
        console.error('Error refreshing dashboard:', error);
        showNotification('Error loading dashboard data', 'error');
    }
}

async function loadKPIs() {
    try {
        const response = await fetch(`${API_BASE}/emissions/`);
        const records = await response.json();
        
        let totals = { scope1: 0, scope2: 0, scope3: 0, all: 0 };
        records.forEach(record => {
            if (record.scope === 1) totals.scope1 += record.calculated_emission;
            else if (record.scope === 2) totals.scope2 += record.calculated_emission;
            else if (record.scope === 3) totals.scope3 += record.calculated_emission;
            totals.all += record.calculated_emission;
        });
        document.getElementById('totalEmissions').textContent = formatNumber(totals.all);
        document.getElementById('scope1Total').textContent = formatNumber(totals.scope1);
        document.getElementById('scope2Total').textContent = formatNumber(totals.scope2);
        document.getElementById('scope3Total').textContent = formatNumber(totals.scope3);
        
        await loadDashboardIntensity();
    } catch (error) {
        console.error('Error loading KPIs:', error);
    }
}

async function loadDashboardIntensity() {
    try {
        const metric = document.getElementById('dashIntensityMetric').value;
        const year = document.getElementById('dashIntensityYear').value;
        const start = `${year}-01-01`;
        const end = `${year}-12-31`;
        const response = await fetch(
            `${API_BASE}/analytics/intensity?start_date=${start}&end_date=${end}&metric_name=${encodeURIComponent(metric)}`
        );
        const data = await response.json();
        const selectedOption = document.getElementById('dashIntensityMetric').selectedOptions[0];
        const unitDisplay = selectedOption ? selectedOption.textContent.split('(')[1]?.replace(')', '').trim() || 'unit' : 'unit';
        document.getElementById('intensityValue').textContent = formatNumber(data.intensity || 0);
        document.getElementById('intensityUnit').textContent = `kgCO₂e/${unitDisplay}`;
    } catch (error) {
        console.error('Error loading dashboard intensity:', error);
    }
}

async function loadYoYChart() {
    try {
        const yearSelect = document.getElementById('yoyYear');
        const year = yearSelect ? parseInt(yearSelect.value) : 2024;
        const response = await fetch(`${API_BASE}/analytics/yoy?year=${year}`);
        const data = await response.json();
        
        const ctx = document.getElementById('yoyChart').getContext('2d');
        
        if (charts.yoy) charts.yoy.destroy();
        
        const years = Object.keys(data).sort();
        const scope1Data = years.map(y => data[y].scope_1 || 0);
        const scope2Data = years.map(y => data[y].scope_2 || 0);
        const scope3Data = years.map(y => data[y].scope_3 || 0);
        
        charts.yoy = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: years,
                datasets: [
                    {
                        label: 'Scope 1',
                        data: scope1Data,
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 2
                    },
                    {
                        label: 'Scope 2',
                        data: scope2Data,
                        backgroundColor: 'rgba(255, 99, 132, 0.7)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 2
                    },
                    {
                        label: 'Scope 3',
                        data: scope3Data,
                        backgroundColor: 'rgba(75, 192, 192, 0.7)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Emissions (tCO₂e)' }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading YoY chart:', error);
    }
}

async function loadHotspotCharts() {
    try {
        const response1 = await fetch(`${API_BASE}/analytics/hotspots?scope=1&year=2024`);
        const data1 = await response1.json();
        createHotspotChart('hotspotChart', data1);
        
        const response2 = await fetch(`${API_BASE}/analytics/hotspots?scope=2&year=2024`);
        const data2 = await response2.json();
        createHotspotChart('hotspotChart2', data2);
        
        const response3 = await fetch(`${API_BASE}/analytics/hotspots?scope=3&year=2024`);
        const data3 = await response3.json();
        createHotspotChart('hotspotChart3', data3);
        
    } catch (error) {
        console.error('Error loading hotspot charts:', error);
    }
}

function createHotspotChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    if (canvasId === 'hotspotChart' && charts.hotspot1) {
        charts.hotspot1.destroy();
    } else if (canvasId === 'hotspotChart2' && charts.hotspot2) {
        charts.hotspot2.destroy();
    } else if (canvasId === 'hotspotChart3' && charts.hotspot3) {
        charts.hotspot3.destroy();
    }
    
    const topData = data.slice(0, 8);
    const labels = topData.map(d => d.material);
    const values = topData.map(d => d.emission);
    
    const colors = [
        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
        '#FF9F40', '#FF6384', '#C9CBCF'
    ];
    
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { font: { size: 10 } }
                }
            }
        }
    });
    
    if (canvasId === 'hotspotChart') {
        charts.hotspot1 = chart;
    } else if (canvasId === 'hotspotChart2') {
        charts.hotspot2 = chart;
    } else if (canvasId === 'hotspotChart3') {
        charts.hotspot3 = chart;
    }
}

async function loadTrendChart(view = 'quarterly') {
    try {
        const yearSelect = document.getElementById('trendYear');
        const year = yearSelect ? yearSelect.value : '2024';
        const response = await fetch(`${API_BASE}/analytics/monthly-trend?year=${year}`);
        const data = await response.json();
        
        const ctx = document.getElementById('trendChart').getContext('2d');
        
        if (charts.trend) charts.trend.destroy();
        
        let labels, emissions;
        const quarterNames = ['Q1', 'Q2', 'Q3', 'Q4'];
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        
        if (view === 'quarterly') {
            const qData = {1:0, 2:0, 3:0, 4:0};
            data.forEach(d => {
                const q = Math.ceil(d.month / 3);
                qData[q] += d.emission;
            });
            labels = quarterNames;
            emissions = Object.values(qData);
        } else {
            const monthMap = {};
            data.forEach(d => { monthMap[d.month] = d.emission; });
            labels = monthNames;
            emissions = monthNames.map((_, i) => monthMap[i+1] || 0);
        }
        
        charts.trend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: view === 'quarterly' ? 'Quarterly Emissions' : 'Monthly Emissions',
                    data: emissions,
                    borderColor: '#2b6cb0',
                    backgroundColor: 'rgba(43, 108, 176, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#2b6cb0',
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Emissions (tCO₂e)' }
                    }
                }
            }
        });
        
        document.querySelectorAll('.btn-small').forEach(b => b.classList.remove('active'));
        document.getElementById('trendQuarterly').classList.add('active');
    } catch (error) {
        console.error('Error loading trend chart:', error);
    }
}

async function loadMetricOptions() {
    try {
        const response = await fetch(`${API_BASE}/metrics/names`);
        const metrics = await response.json();
        
        if (metrics.length === 0) {
            const fallbackMetrics = [
                { name: 'Steel Production', unit: 'tonnes' },
                { name: 'Employees', unit: 'count' }
            ];
            populateMetricDropdowns(fallbackMetrics);
            return;
        }
        
        populateMetricDropdowns(metrics);
    } catch (error) {
        console.error('Error loading metric options:', error);
        const fallbackMetrics = [
            { name: 'Steel Production', unit: 'tonnes' },
            { name: 'Employees', unit: 'count' }
        ];
        populateMetricDropdowns(fallbackMetrics);
    }
}

function populateMetricDropdowns(metrics) {
    const dashSelect = document.getElementById('dashIntensityMetric');
    const currentDashValue = dashSelect.value;
    dashSelect.innerHTML = '';
    metrics.forEach(m => {
        const option = document.createElement('option');
        option.value = m.name;
        option.textContent = `${m.name} (${m.unit})`;
        dashSelect.appendChild(option);
    });
    if (metrics.some(m => m.name === currentDashValue)) {
        dashSelect.value = currentDashValue;
    }
    
    const analysisSelect = document.getElementById('intensityMetric');
    const currentAnalysisValue = analysisSelect.value;
    analysisSelect.innerHTML = '';
    metrics.forEach(m => {
        const option = document.createElement('option');
        option.value = m.name;
        option.textContent = `${m.name} (${m.unit})`;
        analysisSelect.appendChild(option);
    });
    if (metrics.some(m => m.name === currentAnalysisValue)) {
        analysisSelect.value = currentAnalysisValue;
    }
    
    if (document.getElementById('intensity').classList.contains('active')) {
        updateIntensityAnalysis();
    } else {
        loadDashboardIntensity();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('formDate').value = getToday();
    document.getElementById('metricDate').value = getToday();
    loadRecentEntries();
    loadMaterialFilter();
    loadMetricOptions();
    
    document.getElementById('formScope').addEventListener('change', function() {
        const scope3Fields = document.getElementById('scope3Fields');
        if (this.value === '3') {
            scope3Fields.style.display = 'block';
        } else {
            scope3Fields.style.display = 'none';
        }
    });
    
    setInterval(refreshDashboard, 30000);
});

document.getElementById('emissionForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const scope = parseInt(document.getElementById('formScope').value);
    const material = document.getElementById('formMaterial').value.trim();
    const section = document.getElementById('formSection').value.trim() || null;
    const quantity = parseFloat(document.getElementById('formQuantity').value);
    const activityDate = document.getElementById('formDate').value;
    const userId = document.getElementById('formUserId').value.trim();
    const position = document.getElementById('formPosition').value;
    
    if (!material || !quantity || !activityDate || !userId) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }
    
    const payload = {
        scope: scope,
        material: material,
        quantity: quantity,
        activity_date: activityDate,
        section: section,
        user_id: userId,
        position: position
    };
    
    if (scope === 3) {
        payload.category = document.getElementById('formCategory').value.trim() || null;
        payload.transportation_mode = document.getElementById('formTransport').value.trim() || null;
    }
    
    try {
        const response = await fetch(`${API_BASE}/emissions/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save emission');
        }
        
        const result = await response.json();
        showCalculationResult(result);
        
        document.getElementById('formMaterial').value = '';
        document.getElementById('formSection').value = '';
        document.getElementById('formQuantity').value = '';
        document.getElementById('formCategory').value = '';
        document.getElementById('formTransport').value = '';
        document.getElementById('formUserId').value = '';
        
        loadRecentEntries();
        showNotification('✅ Emission recorded successfully!', 'success');
        
    } catch (error) {
        showNotification(`❌ Error: ${error.message}`, 'error');
    }
});

function showCalculationResult(result) {
    const div = document.getElementById('calculationResult');
    const content = document.getElementById('resultContent');
    
    content.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
            <div><strong>Material:</strong> ${result.material}</div>
            <div><strong>Scope:</strong> ${result.scope}</div>
            <div><strong>Quantity:</strong> ${result.quantity} ${result.unit || ''}</div>
            <div><strong>Emission Factor:</strong> ${result.factor_value || 'N/A'}</div>
            <div style="grid-column: 1 / -1; text-align: center; padding: 10px; background: #48bb78; color: white; border-radius: 6px;">
                <strong style="font-size: 20px;">${formatNumber(result.calculated_emission)} tCO₂e</strong>
            </div>
            <div style="grid-column: 1 / -1; font-size: 12px; color: #718096; text-align: center;">
                Record ID: ${result.id} | Date: ${formatDate(result.activity_date)} | ${result.created_by || 'system'} (${result.position || 'N/A'})
            </div>
        </div>
    `;
    
    div.style.display = 'block';
}

async function loadRecentEntries() {
    try {
        const response = await fetch(`${API_BASE}/emissions/`);
        const records = await response.json();
        
        const container = document.getElementById('recentEntries');
        
        if (records.length === 0) {
            container.innerHTML = '<p class="text-muted">No entries yet. Submit your first emission record!</p>';
            return;
        }
        
        const recent = records.slice(-10).reverse();
        
        let html = '<div style="max-height: 500px; overflow-y: auto;">';
        recent.forEach(record => {
            html += `
                <div style="padding: 12px; border-bottom: 1px solid #edf2f7; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>${record.material}</strong>
                        <span style="color: #718096; font-size: 14px;">
                            ${record.quantity} ${record.unit || ''}
                        </span>
                        ${getScopeBadge(record.scope)}
                        ${getSourceBadge(record.is_excel_data)}
                        <span style="color: #a0aec0; font-size: 12px; margin-left: 10px;">
                            ${formatDate(record.activity_date)}
                        </span>
                        <span style="color: #a0aec0; font-size: 11px; margin-left: 10px;">
                            ${record.created_by || 'system'}
                        </span>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 600; color: #2d3748;">
                            ${formatNumber(record.calculated_emission)} tCO₂e
                        </div>
                        ${getStatusBadge(record.is_override)}
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading recent entries:', error);
        document.getElementById('recentEntries').innerHTML = '<p class="text-muted">Error loading entries</p>';
    }
}

document.getElementById('metricForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const payload = {
        metric_date: document.getElementById('metricDate').value,
        metric_name: document.getElementById('metricName').value.trim(),
        value: parseFloat(document.getElementById('metricValue').value),
        unit: document.getElementById('metricUnit').value.trim()
    };
    
    if (!payload.metric_name || !payload.value || !payload.unit) {
        showNotification('Please fill all fields', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/metrics/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error('Failed to save metric');
        
        showNotification('✅ Metric saved successfully!', 'success');
        document.getElementById('metricName').value = '';
        document.getElementById('metricValue').value = '';
        document.getElementById('metricUnit').value = '';
        await loadMetrics();
        updateIntensityAnalysis();
        
    } catch (error) {
        showNotification(`❌ Error: ${error.message}`, 'error');
    }
});

async function loadMetrics() {
    try {
        const response = await fetch(`${API_BASE}/metrics/`);
        const metrics = await response.json();
        
        const container = document.getElementById('metricsList');
        
        if (metrics.length === 0) {
            container.innerHTML = '<p class="text-muted">No metrics submitted yet</p>';
            return;
        }
        
        let html = '<div style="max-height: 400px; overflow-y: auto;"><table><thead><tr><th>Date</th><th>Metric</th><th>Value</th><th>Unit</th></tr></thead><tbody>';
        metrics.slice().reverse().forEach(m => {
            html += `<tr><td>${formatDate(m.metric_date)}</td><td>${m.metric_name}</td><td>${formatNumber(m.value)}</td><td>${m.unit}</td></tr>`;
        });
        html += '</tbody></table></div>';
        container.innerHTML = html;
        
        await loadMetricOptions();
        updateIntensityAnalysis();
        
    } catch (error) {
        console.error('Error loading metrics:', error);
        document.getElementById('metricsList').innerHTML = '<p class="text-muted">Error loading metrics</p>';
    }
}

async function loadSourceOptions() {
    const scope = document.getElementById('sourceScope').value;
    const response = await fetch(`${API_BASE}/emissions?scope=${scope}`);
    const records = await response.json();
    const sources = [...new Set(records.map(r => r.material))];
    const select = document.getElementById('sourceSelect');
    select.innerHTML = '<option value="">-- Select --</option>';
    sources.forEach(s => {
        select.innerHTML += `<option value="${s}">${s}</option>`;
    });
}

async function loadSourceDetails() {
    const scope = document.getElementById('sourceScope').value;
    const source = document.getElementById('sourceSelect').value;
    
    if (!source) {
        document.getElementById('sourceRecords').innerHTML = '<p class="text-muted">Select a source to view records</p>';
        document.getElementById('sourceTotal').style.display = 'none';
        return;
    }
    
    const response = await fetch(`${API_BASE}/emissions/?scope=${scope}&material=${source}`);
    const records = await response.json();
    
    const total = records.reduce((sum, r) => sum + r.calculated_emission, 0);
    document.getElementById('sourceTotalValue').textContent = total.toFixed(2);
    document.getElementById('sourceTotal').style.display = 'block';
    
    let html = `<h4>${records.length} records found</h4><div style="max-height: 400px; overflow-y: auto;">`;
    if (records.length === 0) {
        html += '<p class="text-muted">No records for this source</p>';
    }
    records.forEach(r => {
        const scopeLabel = r.scope === 1 ? '🔴 Scope 1' : r.scope === 2 ? '🟡 Scope 2' : '🟢 Scope 3';
        html += `
            <div style="padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between;">
                <div>
                    <strong>${r.material}</strong> 
                    ${r.quantity} ${r.unit} 
                    ${scopeLabel}
                    ${getSourceBadge(r.is_excel_data)}
                </div>
                <div>${formatNumber(r.calculated_emission)} tCO₂e | ${formatDate(r.activity_date)}</div>
            </div>
        `;
    });
    html += '</div>';
    document.getElementById('sourceRecords').innerHTML = html;
}

async function loadAllRecords() {
    try {
        const response = await fetch(`${API_BASE}/emissions`);
        const records = await response.json();
        
        allRecords = records;
        const tbody = document.getElementById('recordsBody');
        
        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align: center;">No records found</td></tr>';
            return;
        }
        
        let html = '';
        records.slice().reverse().forEach(record => {
            html += `
                <tr>
                    <td>#${record.id}</td>
                    <td>${formatDate(record.activity_date)}</td>
                    <td>${getScopeBadge(record.scope)}</td>
                    <td>${record.material}</td>
                    <td>${formatNumber(record.quantity)} ${record.unit || ''}</td>
                    <td><strong>${formatNumber(record.calculated_emission)}</strong></td>
                    <td>${getStatusBadge(record.is_override)}</td>
                    <td>${getSourceBadge(record.is_excel_data)}</td>
                    <td>${record.created_by || 'system'}</td>
                    <td>
                        <button class="btn-view" onclick="viewRecord(${record.id})">👁️</button>
                        <button class="btn-override" onclick="openOverrideModal(${record.id})">✏️ Override</button>
                    </td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading records:', error);
        document.getElementById('recordsBody').innerHTML = '<tr><td colspan="10" style="text-align: center;">Error loading records</td></tr>';
    }
}

async function loadMaterialFilter() {
    const scope = document.getElementById('filterScope').value;
    let url = `${API_BASE}/emissions`;
    if (scope) url += `?scope=${scope}`;
    const response = await fetch(url);
    const records = await response.json();
    const materials = [...new Set(records.map(r => r.material))];
    const select = document.getElementById('filterMaterial');
    select.innerHTML = '<option value="">All Materials</option>';
    materials.forEach(m => {
        select.innerHTML += `<option value="${m}">${m}</option>`;
    });
}

async function applyFilters() {
    const scope = document.getElementById('filterScope').value;
    const material = document.getElementById('filterMaterial').value;
    let url = `${API_BASE}/emissions`;
    const params = [];
    if (scope) params.push(`scope=${scope}`);
    if (material) params.push(`material=${material}`);
    if (params.length) url += '?' + params.join('&');
    const response = await fetch(url);
    const records = await response.json();
    
    const tbody = document.getElementById('recordsBody');
    if (records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align: center;">No records found</td></tr>';
        return;
    }
    let html = '';
    records.slice().reverse().forEach(record => {
        html += `
            <tr>
                <td>#${record.id}</td>
                <td>${formatDate(record.activity_date)}</td>
                <td>${getScopeBadge(record.scope)}</td>
                <td>${record.material}</td>
                <td>${formatNumber(record.quantity)} ${record.unit || ''}</td>
                <td><strong>${formatNumber(record.calculated_emission)}</strong></td>
                <td>${getStatusBadge(record.is_override)}</td>
                <td>${getSourceBadge(record.is_excel_data)}</td>
                <td>${record.created_by || 'system'}</td>
                <td>
                    <button class="btn-view" onclick="viewRecord(${record.id})">👁️</button>
                    <button class="btn-override" onclick="openOverrideModal(${record.id})">✏️ Override</button>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

async function viewRecord(recordId) {
    try {
        const response = await fetch(`${API_BASE}/emissions/${recordId}`);
        if (!response.ok) throw new Error('Failed to fetch record details');
        const record = await response.json();
        
        const sourceLabel = record.is_excel_data ? '📊 Excel Data' : '✏️ User Entry';
        const sourceColor = record.is_excel_data ? '#2b6cb0' : '#276749';
        
        const details = `
            <div style="padding: 10px;">
                <h4 style="margin-bottom: 5px;">Record #${record.id}</h4>
                <p style="margin-top: 0; color: ${sourceColor}; font-weight: 600;">${sourceLabel}</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Material</td><td style="padding: 4px 8px;">${record.material}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Scope</td><td style="padding: 4px 8px;">${record.scope}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Quantity</td><td style="padding: 4px 8px;">${record.quantity} ${record.unit}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Emissions</td><td style="padding: 4px 8px; font-weight: 600;">${formatNumber(record.calculated_emission)} tCO₂e</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Activity Date</td><td style="padding: 4px 8px;">${formatDate(record.activity_date)}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Created By</td><td style="padding: 4px 8px;">${record.created_by || 'system'}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Position</td><td style="padding: 4px 8px;">${record.user_position || 'N/A'}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Status</td><td style="padding: 4px 8px;">${record.is_override ? '⚠️ Override' : '✅ Original'}</td></tr>
                    ${record.override_reason ? `<tr><td style="padding: 4px 8px; font-weight: bold;">Override Reason</td><td style="padding: 4px 8px;">${record.override_reason}</td></tr>` : ''}
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Factor UUID</td><td style="padding: 4px 8px; font-family: monospace; font-size: 12px;">${record.factor_uuid || 'N/A'}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Factor Value</td><td style="padding: 4px 8px;">${record.factor_value || 'N/A'}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Factor Valid From</td><td style="padding: 4px 8px;">${record.factor_valid_from ? formatDate(record.factor_valid_from) : 'N/A'}</td></tr>
                    <tr><td style="padding: 4px 8px; font-weight: bold;">Factor Valid To</td><td style="padding: 4px 8px;">${record.factor_valid_to ? formatDate(record.factor_valid_to) : 'N/A'}</td></tr>
                </table>
            </div>
        `;

        const modalId = 'viewModal_' + recordId;
        const modal = document.createElement('div');
        modal.id = modalId;
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; align-items: center; justify-content: center;';
        modal.innerHTML = `
            <div style="background: white; padding: 30px; border-radius: 12px; max-width: 600px; width: 95%; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                ${details}
                <div style="margin-top: 20px; text-align: right;">
                    <button onclick="document.getElementById('${modalId}').remove()" style="padding: 10px 24px; background: #4a5568; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Close</button>
                </div>
            </div>
        `;
        modal.addEventListener('click', function(e) {
            if (e.target === modal) modal.remove();
        });
        document.body.appendChild(modal);
    } catch (error) {
        console.error('Error loading record details:', error);
        showNotification('❌ Failed to load record details', 'error');
    }
}

async function exportFilteredCSV() {
    const scope = document.getElementById('filterScope').value;
    const material = document.getElementById('filterMaterial').value;
    let url = `${API_BASE}/emissions/export/csv?`;
    if (scope) url += `scope=${scope}&`;
    if (material) url += `material=${material}&`;
    window.open(url, '_blank');
}

function openOverrideModal(recordId) {
    overrideRecordId = recordId;
    document.getElementById('overrideRecordId').textContent = recordId;
    document.getElementById('overrideQuantity').value = '';
    document.getElementById('overrideReason').value = '';
    document.getElementById('overrideUserId').value = '';
    document.getElementById('overridePosition').value = 'Employee';
    document.getElementById('overrideModal').style.display = 'flex';
}

function closeOverrideModal() {
    document.getElementById('overrideModal').style.display = 'none';
    overrideRecordId = null;
}

document.getElementById('overrideForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (!overrideRecordId) {
        showNotification('Error: No record selected', 'error');
        return;
    }
    
    const newQuantity = parseFloat(document.getElementById('overrideQuantity').value);
    const reason = document.getElementById('overrideReason').value.trim();
    const userId = document.getElementById('overrideUserId').value.trim();
    const position = document.getElementById('overridePosition').value;
    
    if (!newQuantity || !reason || !userId) {
        showNotification('Please fill in all fields', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/emissions/${overrideRecordId}/override`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                new_quantity: newQuantity,
                reason: reason,
                user_id: userId,
                position: position
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to override');
        }
        
        const result = await response.json();
        showNotification(`✅ Record #${overrideRecordId} overridden successfully!`, 'success');
        
        closeOverrideModal();
        loadRecentEntries();
        loadAllRecords();
        loadAuditLog();
        refreshDashboard();
        
    } catch (error) {
        showNotification(`❌ Error: ${error.message}`, 'error');
    }
});

document.getElementById('overrideModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeOverrideModal();
    }
});

async function loadAuditLog() {
    try {
        const response = await fetch(`${API_BASE}/emissions/`);
        const records = await response.json();
        
        const overrides = records.filter(r => r.is_override === true);
        const tbody = document.getElementById('auditBody');
        
        if (overrides.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">No manual overrides yet</td></tr>';
            return;
        }
        
        let html = '';
        overrides.slice().reverse().forEach(record => {
            html += `
                <tr>
                    <td>${formatDate(record.activity_date)}</td>
                    <td>#${record.id}</td>
                    <td>${getScopeBadge(record.scope)}</td>
                    <td><span class="status-badge status-override">OVERRIDE</span></td>
                    <td>${formatNumber(record.quantity)} ${record.unit || ''}</td>
                    <td>${formatNumber(record.calculated_emission)} tCO₂e</td>
                    <td>${record.created_by || 'system'}</td>
                    <td>${record.override_reason || 'Manual adjustment'}</td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading audit log:', error);
        document.getElementById('auditBody').innerHTML = '<tr><td colspan="8" style="text-align: center;">Error loading audit log</td></tr>';
    }
}

function showNotification(message, type = 'info') {
    const colors = {
        success: '#48bb78',
        error: '#fc8181',
        info: '#4299e1'
    };
    
    const div = document.createElement('div');
    div.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 15px 25px;
        background: ${colors[type] || colors.info};
        color: white;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 2000;
        animation: slideIn 0.3s ease-out;
        max-width: 400px;
    `;
    div.textContent = message;
    
    document.body.appendChild(div);
    
    setTimeout(() => {
        div.style.opacity = '0';
        div.style.transition = 'opacity 0.3s';
        setTimeout(() => div.remove(), 300);
    }, 5000);
}

function getPeriodDates(period) {
    const [year, q] = period.split('-');
    const map = {
        'Q1': [`${year}-01-01`, `${year}-03-31`],
        'Q2': [`${year}-04-01`, `${year}-06-30`],
        'Q3': [`${year}-07-01`, `${year}-09-30`],
        'Q4': [`${year}-10-01`, `${year}-12-31`],
        'FY': [`${year}-01-01`, `${year}-12-31`]
    };
    return map[q] || [`${year}-01-01`, `${year}-12-31`];
}

function getPeriodLabel(period) {
    const [year, q] = period.split('-');
    const labels = {
        'Q1': `Q1 ${year} (Jan-Mar)`,
        'Q2': `Q2 ${year} (Apr-Jun)`,
        'Q3': `Q3 ${year} (Jul-Sep)`,
        'Q4': `Q4 ${year} (Oct-Dec)`,
        'FY': `Full Year ${year}`
    };
    return labels[q] || period;
}

async function updateIntensityAnalysis() {
    const metric = document.getElementById('intensityMetric').value;
    const period = document.getElementById('intensityPeriod').value;
    const [start, end] = getPeriodDates(period);
    const periodLabel = getPeriodLabel(period);
    
    const selectedOption = document.getElementById('intensityMetric').selectedOptions[0];
    const unitDisplay = selectedOption ? selectedOption.textContent.split('(')[1]?.replace(')', '').trim() || 'unit' : 'unit';
    const unitLabel = `kgCO₂e/${unitDisplay}`;
    
    try {
        const response = await fetch(
            `${API_BASE}/analytics/intensity?start_date=${start}&end_date=${end}&metric_name=${encodeURIComponent(metric)}`
        );
        const data = await response.json();
        
        document.getElementById('intensityPeriodDisplay').textContent = periodLabel;
        document.getElementById('intensityMetricDisplay').textContent = metric;
        document.getElementById('intensityTotalEmissions').textContent = formatNumber(data.total_emissions) + ' tCO₂e';
        document.getElementById('intensityProduction').textContent = formatNumber(data.production) + ' ' + unitDisplay;
        document.getElementById('intensityResultValue').textContent = formatNumber(data.intensity || 0);
        document.getElementById('intensityResultUnit').textContent = unitLabel;
        
        document.getElementById('intensityResults').style.display = 'block';
        document.getElementById('intensityNoData').style.display = 'none';
    } catch (error) {
        console.error('Error updating intensity:', error);
        document.getElementById('intensityResults').style.display = 'none';
        document.getElementById('intensityNoData').style.display = 'block';
    }
}

const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .btn-small {
        padding: 4px 12px;
        background: #edf2f7;
        border: 2px solid #e2e8f0;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 600;
        color: #4a5568;
        transition: all 0.2s;
    }
    .btn-small:hover {
        background: #e2e8f0;
    }
    .btn-small.active {
        background: #2b6cb0;
        color: white;
        border-color: #2b6cb0;
    }
`;
document.head.appendChild(style);

setTimeout(() => {
    refreshDashboard();
}, 500);