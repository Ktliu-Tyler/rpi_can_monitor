// 全域變數
let map, marker;
let speedChart, voltageChart, tempChart;
let startTime = Date.now();

// 地圖初始化
function updateMap(lat, lon) {
    if (!map) {
        map = L.map('map').setView([lat, lon], 18);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }).addTo(map);
        
        // 創建脈衝效果的標記
        const pulsingIcon = L.divIcon({
            html: '<div class="pulsing-dot"></div>',
            className: 'pulsing-marker',
            iconSize: [20, 20]
        });
        
        marker = L.marker([lat, lon], { icon: pulsingIcon }).addTo(map);
        
        // 添加脈衝效果 CSS
        const style = document.createElement('style');
        style.textContent = `
            .pulsing-marker {
                background: none;
                border: none;
            }
            .pulsing-dot {
                width: 20px;
                height: 20px;
                background: #00eaff;
                border-radius: 50%;
                position: relative;
                animation: pulse-dot 2s infinite;
                box-shadow: 0 0 10px #00eaff;
            }
            .pulsing-dot::before {
                content: '';
                position: absolute;
                top: -10px;
                left: -10px;
                width: 40px;
                height: 40px;
                background: rgba(0,234,255,0.3);
                border-radius: 50%;
                animation: pulse-ring 2s infinite;
            }
            @keyframes pulse-dot {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.2); }
            }
            @keyframes pulse-ring {
                0% { transform: scale(0.5); opacity: 1; }
                100% { transform: scale(2); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    } else {
        marker.setLatLng([lat, lon]);
        map.setView([lat, lon]);
    }
}

// 圖表初始化
function initCharts() {
    // 等待元素載入
    const speedCanvas = document.getElementById('speedChart');
    const voltageCanvas = document.getElementById('voltageChart');
    const tempCanvas = document.getElementById('tempChart');
    
    if (!speedCanvas || !voltageCanvas || !tempCanvas) {
        console.log('等待圖表元素載入...');
        setTimeout(initCharts, 100);
        return;
    }

    // 速度折線圖
    const speedCtx = speedCanvas.getContext('2d');
    speedChart = new Chart(speedCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '速度 (km/h)',
                data: [],
                borderColor: '#00eaff',
                backgroundColor: 'rgba(0,234,255,0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 0,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#00eaff', font: { size: 14 } }
                }
            },
            scales: {
                x: { 
                    ticks: { color: '#fff', maxTicksLimit: 8, font: { size: 12 } },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                },
                y: { 
                    ticks: { color: '#fff', font: { size: 12 } },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                }
            },
            animation: {
                duration: 750,
                easing: 'easeInOutQuart'
            }
        }
    });

    // 電壓柱狀圖
    const voltageCtx = voltageCanvas.getContext('2d');
    voltageChart = new Chart(voltageCtx, {
        type: 'bar',
        data: {
            labels: ['Cell 1', 'Cell 2', 'Cell 3', 'Cell 4', 'Cell 5', 'Cell 6'],
            datasets: [{
                label: '電壓 (V)',
                data: [],
                backgroundColor: 'rgba(0,255,153,0.7)',
                borderColor: '#00ff99',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#00ff99', font: { size: 14 } }
                }
            },
            scales: {
                x: { 
                    ticks: { color: '#fff', font: { size: 11 } },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                },
                y: { 
                    ticks: { color: '#fff', font: { size: 12 } },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    min: 0,
                    max: 5
                }
            },
            animation: {
                duration: 1000,
                easing: 'easeInOutBounce'
            }
        }
    });

    // 溫度折線圖
    const tempCtx = tempCanvas.getContext('2d');
    tempChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            labels: ['Cell 1', 'Cell 2', 'Cell 3', 'Cell 4', 'Cell 5', 'Cell 6'],
            datasets: [{
                label: '溫度 (°C)',
                data: [],
                borderColor: '#ffa500',
                backgroundColor: 'rgba(255,165,0,0.1)',
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#ffa500',
                pointBorderColor: '#fff',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#ffa500', font: { size: 14 } }
                }
            },
            scales: {
                x: { 
                    ticks: { color: '#fff', font: { size: 11 } },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                },
                y: { 
                    ticks: { color: '#fff', font: { size: 12 } },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    min: 0,
                    max: 100
                }
            },
            animation: {
                duration: 800,
                easing: 'easeInOutCubic'
            }
        }
    });
    
    console.log('所有圖表初始化完成');
}

// 進度條更新
function updateProgressBar(elementId, value, max = 100) {
    const progressBar = document.getElementById(elementId);
    if (progressBar) {
        const percentage = Math.min((value / max) * 100, 100);
        progressBar.style.width = percentage + '%';
        
        // 根據數值改變顏色
        if (percentage > 80) {
            progressBar.style.background = 'linear-gradient(90deg, #ff3c3c, #ff6b6b)';
        } else if (percentage > 60) {
            progressBar.style.background = 'linear-gradient(90deg, #ffa500, #ffb347)';
        } else {
            progressBar.style.background = 'linear-gradient(90deg, #00eaff, #00ff99)';
        }
    }
}

// 圓形進度條更新
function updateCircularProgress(elementId, value, max = 100) {
    const circle = document.getElementById(elementId);
    if (circle) {
        const percentage = Math.min((value / max) * 100, 100);
        const circumference = 2 * Math.PI * 50; // radius = 50
        const offset = circumference - (percentage / 100) * circumference;
        circle.style.strokeDashoffset = offset;
        
        // 根據速度改變顏色
        if (percentage > 80) {
            circle.style.stroke = '#ff3c3c';
        } else if (percentage > 60) {
            circle.style.stroke = '#ffa500';
        } else {
            circle.style.stroke = '#00eaff';
        }
    }
}

// 系統運行時間更新
function updateUptime() {
    const uptimeElement = document.getElementById('system-uptime');
    if (uptimeElement) {
        const elapsed = Date.now() - startTime;
        const hours = Math.floor(elapsed / 3600000);
        const minutes = Math.floor((elapsed % 3600000) / 60000);
        const seconds = Math.floor((elapsed % 60000) / 1000);
        
        uptimeElement.textContent = 
            `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
}

// WebSocket 連接與數據處理
const ws = new WebSocket(`ws://${location.host}/ws`);

ws.onopen = () => {
    console.log('WebSocket 連接成功');
    const canStatus = document.getElementById('can-status');
    if (canStatus) {
        canStatus.textContent = '已連線';
        canStatus.className = 'status-ok';
    }
};

ws.onclose = () => {
    console.log('WebSocket 連接關閉');
    const canStatus = document.getElementById('can-status');
    if (canStatus) {
        canStatus.textContent = '斷線';
        canStatus.className = 'status-bad';
    }
};

ws.onerror = (error) => {
    console.error('WebSocket 錯誤:', error);
    const canStatus = document.getElementById('can-status');
    if (canStatus) {
        canStatus.textContent = '錯誤';
        canStatus.className = 'status-bad';
    }
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // 電池溫度
    const temp = data.accumulator.temperature !== null ? data.accumulator.temperature : null;
    if (temp !== null) {
        document.getElementById('battery-temp').textContent = temp.toFixed(1) + '°C';
        updateProgressBar('temp-progress', temp, 80);
        document.getElementById('battery-status').textContent = temp < 50 ? '正常' : '過熱';
        document.getElementById('battery-status').className = temp < 50 ? 'status-ok' : 'status-bad';
    }
    
    // 車輛速度（圓形進度條） - 新版本在 velocity.speed_kmh
    const speed = data.velocity.speed_kmh !== null ? data.velocity.speed_kmh : 0;
    document.getElementById('car-speed').textContent = speed.toFixed(1);
    updateCircularProgress('speed-circle', speed, 100);
    
    // 速度向量 - 新版本是 linear_x/y/z
    document.getElementById('vx').textContent = data.velocity.linear_x !== null ? data.velocity.linear_x.toFixed(2) : '--';
    document.getElementById('vy').textContent = data.velocity.linear_y !== null ? data.velocity.linear_y.toFixed(2) : '--';
    document.getElementById('vz').textContent = data.velocity.linear_z !== null ? data.velocity.linear_z.toFixed(2) : '--';
    document.getElementById('vmag').textContent = data.velocity.magnitude !== null ? data.velocity.magnitude.toFixed(2) : '--';
    
    // 電力系統
    const voltage = data.accumulator.voltage !== null ? data.accumulator.voltage : null;
    if (voltage !== null) {
        document.getElementById('battery-voltage').textContent = voltage.toFixed(2) + 'V';
    }
    document.getElementById('battery-current').textContent = (data.accumulator.current !== null ? data.accumulator.current.toFixed(2) : '--') + 'A';
    
    const soc = data.accumulator.soc !== null ? data.accumulator.soc : 0;
    document.getElementById('battery-soc').textContent = soc + '%';
    updateProgressBar('soc-progress', soc, 100);
    
    document.getElementById('battery-capacity').textContent = (data.accumulator.capacity !== null ? data.accumulator.capacity.toFixed(2) : '--') + 'Ah';
    document.getElementById('battery-status2').textContent = data.accumulator.status !== null ? (data.accumulator.status ? 'OK' : 'BAD') : '--';
    
    // GPS
    if (data.gps.lat && data.gps.lon) {
        updateMap(data.gps.lat, data.gps.lon);
        document.getElementById('gps-spinner').style.display = 'none';
    } else {
        document.getElementById('gps-spinner').style.display = 'inline-block';
    }
    
    document.getElementById('gps-lat').textContent = data.gps.lat !== null ? data.gps.lat.toFixed(6) + '°' : '--';
    document.getElementById('gps-lon').textContent = data.gps.lon !== null ? data.gps.lon.toFixed(6) + '°' : '--';
    document.getElementById('gps-alt').textContent = data.gps.alt !== null ? data.gps.alt.toFixed(1) + 'm' : '--';
    document.getElementById('gps-speed').textContent = data.velocity.speed_kmh !== null ? data.velocity.speed_kmh.toFixed(2) + 'km/h' : '--';
    document.getElementById('gps-status').textContent = data.gps.status !== null ? data.gps.status : '--';
    document.getElementById('gps-mode').textContent = '--'; // GPS mode not available in new version
    
    // GPS 訊號狀態
    const gpsSignal = document.getElementById('gps-signal');
    const gpsSignalStatus = document.getElementById('gps-signal-status');
    if (data.gps.lat && data.gps.lon) {
        if (gpsSignal) {
            gpsSignal.textContent = '已定位';
            gpsSignal.className = 'status-ok';
        }
        if (gpsSignalStatus) {
            gpsSignalStatus.textContent = '已定位';
            gpsSignalStatus.className = 'status-ok';
        }
    } else {
        if (gpsSignal) {
            gpsSignal.textContent = '搜尋中';
            gpsSignal.className = 'status-bad';
        }
        if (gpsSignalStatus) {
            gpsSignalStatus.textContent = '搜尋中';
            gpsSignalStatus.className = 'status-bad';
        }
    }
    
    // Inverter 狀態 - 新版本是 inverters
    const inverterGrid = document.getElementById('inverter-grid');
    inverterGrid.innerHTML = '';
    
    // 多語言標籤
    const inverterLabels = {
        zh: ['前左(FL)', '前右(FR)', '後左(RL)', '後右(RR)'],
        en: ['Front Left (FL)', 'Front Right (FR)', 'Rear Left (RL)', 'Rear Right (RR)']
    };
    
    const fieldLabels = {
        speed: { zh: '轉速', en: 'Speed' },
        torque: { zh: '扭矩', en: 'Torque' },
        voltage: { zh: '電壓', en: 'Voltage' },
        current: { zh: '電流', en: 'Current' }
    };
    
    for (let i = 1; i <= 4; i++) {
        const inv = data.inverters[i] || {};
        const heartbeat = inv.heartbeat ? '💚' : '💔';
        const heartbeatClass = inv.heartbeat ? 'inverter-heartbeat' : 'inverter-heartbeat bad';
        
        inverterGrid.innerHTML += `
            <div class="inverter-card">
                <div class="inverter-title">${inverterLabels[currentLanguage][i-1]}</div>
                <div style="font-size:0.85rem;">
                ${fieldLabels.speed[currentLanguage]}: <span style="color:#00eaff;">${inv.speed !== undefined ? inv.speed : '--'}</span> RPM<br>
                ${fieldLabels.torque[currentLanguage]}: <span style="color:#00ff99;">${inv.torque !== undefined ? inv.torque.toFixed(2) : '--'}</span> Nm<br>
                ${fieldLabels.voltage[currentLanguage]}: <span style="color:#ffa500;">${inv.dc_voltage !== undefined ? inv.dc_voltage.toFixed(1) : '--'}</span> V<br>
                ${fieldLabels.current[currentLanguage]}: <span style="color:#ff69b4;">${inv.dc_current !== undefined ? inv.dc_current.toFixed(1) : '--'}</span> A<br>
                MOS: ${inv.mos_temp !== undefined ? inv.mos_temp.toFixed(1) : '--'}°C | 
                MCU: ${inv.mcu_temp !== undefined ? inv.mcu_temp.toFixed(1) : '--'}°C<br>
                Motor: ${inv.motor_temp !== undefined ? inv.motor_temp.toFixed(1) : '--'}°C
                </div>
                <div style="margin-top:6px;">
                    <span class="${heartbeatClass}">${heartbeat}</span>
                    <span style="float:right; font-size:0.8em; color:#00eaff;">0x${(0x190+i).toString(16)}</span>
                </div>
            </div>
        `;
    }
    
    // 速度方向詳細 - 新版本是 linear_x/y/z
    document.getElementById('vx2').textContent = data.velocity.linear_x !== null ? data.velocity.linear_x.toFixed(3) : '--';
    document.getElementById('vy2').textContent = data.velocity.linear_y !== null ? data.velocity.linear_y.toFixed(3) : '--';
    document.getElementById('vz2').textContent = data.velocity.linear_z !== null ? data.velocity.linear_z.toFixed(3) : '--';
    document.getElementById('vmag2').textContent = data.velocity.magnitude !== null ? data.velocity.magnitude.toFixed(3) : '--';
    
    // 更新圖表
    updateCharts(data);
    
    // 電池健康狀態
    const batteryHealth = document.getElementById('battery-health');
    if (temp !== null && voltage !== null && soc !== null) {
        if (temp < 45 && voltage > 3.0 && soc > 20) {
            batteryHealth.textContent = '良好';
            batteryHealth.className = 'status-ok';
        } else {
            batteryHealth.textContent = '警告';
            batteryHealth.className = 'status-bad';
        }
    }
};

// 圖表數據更新
function updateCharts(data) {
    const now = new Date();
    const timeLabel = now.getHours().toString().padStart(2,'0') + ":" + 
                     now.getMinutes().toString().padStart(2,'0') + ":" + 
                     now.getSeconds().toString().padStart(2,'0');
    
    // 速度圖表 - 新版本使用 velocity.speed_kmh
    if (data.velocity.speed_kmh !== null) {
        if (speedChart.data.labels.length > 20) {
            speedChart.data.labels.shift();
            speedChart.data.datasets[0].data.shift();
        }
        speedChart.data.labels.push(timeLabel);
        speedChart.data.datasets[0].data.push(data.velocity.speed_kmh);
        speedChart.update('none');
    }
    
    // 電壓圖表 - 新版本 cell_voltages 是 dict，需要展開
    if (data.accumulator.cell_voltages && Object.keys(data.accumulator.cell_voltages).length > 0) {
        const allVoltages = [];
        // 展開 dict 中的所有電壓值
        Object.keys(data.accumulator.cell_voltages).forEach(index => {
            allVoltages.push(...data.accumulator.cell_voltages[index]);
        });
        voltageChart.data.datasets[0].data = allVoltages.slice(0, 6);
        voltageChart.update('none');
    }
    
    // 溫度圖表 - 新版本 cell_temperatures 是 dict，需要展開
    if (data.accumulator.cell_temperatures && Object.keys(data.accumulator.cell_temperatures).length > 0) {
        const allTemperatures = [];
        // 展開 dict 中的所有溫度值
        Object.keys(data.accumulator.cell_temperatures).forEach(index => {
            allTemperatures.push(...data.accumulator.cell_temperatures[index]);
        });
        tempChart.data.datasets[0].data = allTemperatures.slice(0, 6);
        tempChart.update('none');
    }
}

// 語言切換功能
let currentLanguage = 'zh'; // 預設中文

function toggleLanguage() {
    currentLanguage = currentLanguage === 'zh' ? 'en' : 'zh';
    updateLanguageDisplay();
    localStorage.setItem('language', currentLanguage);
}

function updateLanguageDisplay() {
    const elements = document.querySelectorAll('[data-zh][data-en]');
    elements.forEach(element => {
        if (currentLanguage === 'zh') {
            element.textContent = element.getAttribute('data-zh');
        } else {
            element.textContent = element.getAttribute('data-en');
        }
    });
    
    // 更新圖表標籤
    updateChartLabels();
    
    // 更新狀態文字
    updateStatusTexts();
}

function updateChartLabels() {
    if (speedChart) {
        speedChart.data.datasets[0].label = currentLanguage === 'zh' ? '速度 (km/h)' : 'Speed (km/h)';
        speedChart.update('none');
    }
    
    if (voltageChart) {
        voltageChart.data.datasets[0].label = currentLanguage === 'zh' ? '電壓 (V)' : 'Voltage (V)';
        voltageChart.update('none');
    }
    
    if (tempChart) {
        tempChart.data.datasets[0].label = currentLanguage === 'zh' ? '溫度 (°C)' : 'Temperature (°C)';
        tempChart.update('none');
    }
}

function updateStatusTexts() {
    const statusMappings = {
        '正常': currentLanguage === 'zh' ? '正常' : 'Normal',
        '異常': currentLanguage === 'zh' ? '異常' : 'Error',
        'OK': 'OK',
        'BAD': currentLanguage === 'zh' ? '異常' : 'BAD'
    };
    
    // 更新狀態顯示
    const statusElements = document.querySelectorAll('#can-status span, #gps-signal span, #gps-signal-status span, #battery-health span');
    statusElements.forEach(element => {
        const currentText = element.textContent.trim();
        if (statusMappings[currentText]) {
            element.textContent = statusMappings[currentText];
        }
    });
}

function initLanguage() {
    // 從本地存儲讀取語言設定
    const savedLanguage = localStorage.getItem('language');
    if (savedLanguage) {
        currentLanguage = savedLanguage;
    }
    updateLanguageDisplay();
    
    // 綁定語言切換按鈕
    const languageToggle = document.getElementById('language-toggle');
    if (languageToggle) {
        languageToggle.addEventListener('click', toggleLanguage);
    }
}

// 頁面載入後初始化
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    initLanguage(); // 初始化語言設定
    
    // 每秒更新系統運行時間
    setInterval(updateUptime, 1000);
    
    // 添加卡片懸浮效果
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-8px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });
});