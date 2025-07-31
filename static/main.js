
class NTURTDashboard {
    constructor() {
        this.websocket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        
        // Data storage
        this.lastData = null;
        this.torqueHistory = [];
        this.rpmHistory = [];
        this.maxHistoryPoints = 100;
        
        // Chart instances
        this.torqueChart = null;
        this.rpmChart = null;
        
        // Initialize components
        this.initWebSocket();
        this.initCharts();
        this.startHeartbeatCheck();

        this.initPlaybackControls();
        this.loadAvailableFiles();
        
        console.log('NTURT Dashboard initialized');
    }

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
                console.log('WebSocket connected');
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.lastData = data;
                    this.updateDashboard(data);
                } catch (error) {
                    console.error('Error parsing WebSocket data:', error);
                }
            };
            
            this.websocket.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus(false);
                console.log('WebSocket disconnected');
                this.scheduleReconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.isConnected = false;
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateConnectionStatus(false);
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => {
                this.initWebSocket();
            }, this.reconnectDelay);
        } else {
            console.log('Max reconnection attempts reached');
            document.getElementById('connection-text').textContent = 'Connection failed';
        }
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        const textElement = document.getElementById('connection-text');
        
        if (connected) {
            statusElement.className = 'connection-indicator connected';
            textElement.textContent = 'Connected';
        } else {
            statusElement.className = 'connection-indicator disconnected';
            textElement.textContent = 'Disconnected';
        }
    }

    updateDashboard(data) {
        try {
            // Update message count and timestamp
            this.updateMessageCount(data.message_count);
            this.updateLastUpdate(data.update_time);
            
            // Update VCU data (APPS and Brake bars)
            this.updateVCUData(data.vcu);
            
            // Update speed gauge with RPM conversion
            this.updateSpeedGauge(data.velocity, data.inverters);
            
            // Update RPM gauges for individual motors
            this.updateRPMGauges(data.inverters);
            
            // Update inverter status
            this.updateInverterStatus(data.inverters);
            
            // Update charts with new data
            this.updateCharts(data);
            
            // Update playback controls if available
            this.updatePlaybackControls(data);

        } catch (error) {
            console.error('Error updating dashboard:', error);
        }
    }

    updateMessageCount(count) {
        const element = document.getElementById('message-count');
        if (element && count !== undefined) {
            element.textContent = count.toLocaleString();
        }
    }

    updateLastUpdate(timestamp) {
        const element = document.getElementById('last-update');
        if (element && timestamp) {
            const date = new Date(timestamp);
            element.textContent = `Last update: ${date.toLocaleTimeString()}`;
        }
    }

    updateVCUData(vcu) {
        if (!vcu) return;
        
        // Update APPS bar and value
        if (vcu.apps1 !== null && vcu.apps1 !== undefined) {
            const appsPercent = Math.max(0, Math.min(100, vcu.apps1));
            const appsFill = document.getElementById('apps-fill');
            const appsValue = document.getElementById('apps-value');
            
            if (appsFill) appsFill.style.height = `${appsPercent}%`;
            if (appsValue) appsValue.textContent = `${appsPercent}%`;
        }
        
        // Update Brake bar and value
        if (vcu.brake !== null && vcu.brake !== undefined) {
            const brakePercent = Math.max(0, Math.min(100, vcu.brake));
            const brakeFill = document.getElementById('brake-fill');
            const brakeValue = document.getElementById('brake-value');
            
            if (brakeFill) brakeFill.style.height = `${brakePercent}%`;
            if (brakeValue) brakeValue.textContent = `${brakePercent}%`;
        }
    }

    updateSpeedGauge(velocity, inverters) {
        let speed = 0;
        let totalRPM = 0;
        let motorCount = 0;
        
        // Calculate average RPM from all motors and convert to km/h
        if (inverters) {
            Object.values(inverters).forEach(motor => {
                if (motor.speed !== null && motor.speed !== undefined) {
                    totalRPM += Math.abs(motor.speed);
                    motorCount++;
                }
            });
            
            if (motorCount > 0) {
                const avgRPM = totalRPM / motorCount;
                speed = avgRPM * 0.00703; // RPM to km/h conversion
            }
        }
        
        // Fallback to velocity data if available
        if (speed === 0 && velocity && velocity.speed_kmh !== null) {
            speed = Math.abs(velocity.speed_kmh);
        }
        
        // Update speed display
        const speedValue = document.getElementById('speed-value');
        const rpmValue = document.getElementById('rpm-value');
        const speedGauge = document.getElementById('speed-gauge');
        
        if (speedValue) {
            speedValue.textContent = Math.round(speed);
        }
        
        if (rpmValue && motorCount > 0) {
            rpmValue.textContent = Math.round(speed / 0.00703); 
        }
        
        // Update gauge visual (0-200 km/h range)
        if (speedGauge) {
            const maxSpeed = 200;
            const angle = Math.min(360, (speed / maxSpeed) * 360);
            speedGauge.style.setProperty('--gauge-angle', `${angle}deg`);
        }
    }

    updateRPMGauges(inverters) {
        if (!inverters) return;
        
        const motorIds = ['fl', 'fr', 'rl', 'rr'];
        const motorMap = {
            'fl': 1, 'fr': 2, 'rl': 3, 'rr': 4
        };
        
        motorIds.forEach(motorId => {
            const motorNum = motorMap[motorId];
            const motor = inverters[motorNum];
            
            const valueElement = document.getElementById(`rpm-${motorId}-value`);
            const gaugeElement = document.getElementById(`rpm-${motorId}-gauge`);
            const speedElement = document.getElementById(`speed-${motorId}-value`);
            if (motor && motor.speed !== null && motor.speed !== undefined) {
                const rpm = Math.abs(motor.speed);
                
                if (valueElement) {
                    valueElement.textContent = Math.round(rpm);
                }
                const speedElement = document.getElementById(`speed-${motorId}-value`);
                if (speedElement) {
                    const speed = rpm * 0.00703; // RPM轉換為km/h
                    speedElement.textContent = `${speed.toFixed(1)} km/h`;
                }
                
                if (gaugeElement) {
                    const maxRPM = 8000;
                    const angle = Math.min(360, (rpm / maxRPM) * 360);
                    gaugeElement.style.setProperty('--gauge-angle', `${angle}deg`);
                }
            } else {
                if (valueElement) valueElement.textContent = '0';
                if (speedElement) speedElement.textContent = '0 km/h'; // 新增
                if (gaugeElement) gaugeElement.style.setProperty('--gauge-angle', '0deg');
            }
        });
    }

    updateInverterStatus(inverters) {
        if (!inverters) return;
        
        Object.entries(inverters).forEach(([invNum, data]) => {
            const invCards = document.querySelectorAll('.bg-slate-800');
            const invIndex = parseInt(invNum) - 1;
            
            if (invIndex >= 0 && invIndex < invCards.length) {
                const card = invCards[invIndex];
                
                // Update heartbeat indicator
                const heartbeatIndicator = card.querySelector('.heartbeat-indicator');
                if (heartbeatIndicator && data.heartbeat !== null) {
                    heartbeatIndicator.className = `heartbeat-indicator ${data.heartbeat ? 'heartbeat-ok' : 'heartbeat-fail'}`;
                }
                
                // Update status values
                this.updateInverterField(card, '.inv-status', this.getInverterStatus(data.status));
                this.updateInverterField(card, '.inv-torque', data.torque !== null ? `${data.torque.toFixed(2)} Nm` : 'N/A');
                this.updateInverterField(card, '.inv-dc-voltage', data.dc_voltage !== null ? `${data.dc_voltage.toFixed(1)} V` : 'N/A');
                this.updateInverterField(card, '.inv-dc-current', data.dc_current !== null ? `${data.dc_current.toFixed(1)} A` : 'N/A');
                this.updateInverterField(card, '.inv-mos-temp', data.mos_temp !== null ? `${data.mos_temp.toFixed(1)}°C` : 'N/A');
                this.updateInverterField(card, '.inv-mcu-temp', data.mcu_temp !== null ? `${data.mcu_temp.toFixed(1)}°C` : 'N/A');
            }
        });
    }

    updateInverterField(card, selector, value) {
        const element = card.querySelector(selector);
        if (element) {
            element.textContent = value;
            
            // Add status styling for status field
            if (selector === '.inv-status') {
                element.className = element.className.replace(/status-\w+/g, '');
                if (value === 'OK' || value === 'Ready') {
                    element.classList.add('status-ok');
                } else if (value === 'N/A' || value === 'Unknown') {
                    element.classList.add('status-unknown');
                } else {
                    element.classList.add('status-bad');
                }
            }
        }
    }

    getInverterStatus(status) {
        if (!status || status === null) return 'N/A';
        
        // Simple status interpretation - you may need to adjust based on your specific status codes
        if (Array.isArray(status)) {
            const [status1, status2] = status;
            if (status1 === 0 && status2 === 0) return 'OK';
            return `0x${status1.toString(16).padStart(2, '0')}${status2.toString(16).padStart(2, '0')}`;
        }
        
        return status.toString();
    }

    initCharts() {
        // Initialize Torque Chart
        const torqueCtx = document.getElementById('torque-chart');
        if (torqueCtx) {
            this.torqueChart = new Chart(torqueCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'RL Motor',
                            data: [],
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            tension: 0.4,
                            pointRadius: 0
                        },
                        {
                            label: 'RR Motor',
                            data: [],
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            tension: 0.4,
                            pointRadius: 0
                        },
                        {
                            label: 'RL Motor(FB)',
                            data: [],
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            tension: 0.4,
                            pointRadius: 0
                        },
                        {
                            label: 'RR Motor(FB)',
                            data: [],
                            borderColor: '#ef4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            tension: 0.4,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: { color: '#e2e8f0' }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        },
                        y: {
                            min: -20,
                            max: 20,
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' },
                            title: {
                                display: true,
                                text: 'Torque (Nm)',
                                color: '#e2e8f0'
                            }
                        }
                    },
                    animation: { duration: 0 }
                }
            });
        }

        // Initialize RPM Chart
        const rpmCtx = document.getElementById('rpm-chart');
        if (rpmCtx) {
            this.rpmChart = new Chart(rpmCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'FL Motor',
                            data: [],
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            tension: 0.4,
                            pointRadius: 0,
                            borderWidth: 1
                        },
                        {
                            label: 'FR Motor',
                            data: [],
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            tension: 0.4,
                            pointRadius: 0,
                            borderWidth: 1
                        },
                        {
                            label: 'RL Motor',
                            data: [],
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            tension: 0.4,
                            pointRadius: 0,
                            borderWidth: 2
  
                        },
                        {
                            label: 'RR Motor',
                            data: [],
                            borderColor: '#ef4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            tension: 0.4,
                            pointRadius: 0,
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: { color: '#e2e8f0' }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        },
                        y: {
                            min: 0,
                            max: 8000,
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' },
                            title: {
                                display: true,
                                text: 'RPM',
                                color: '#e2e8f0'
                            }
                        }
                    },
                    animation: { duration: 0 }
                }
            });
        }
    }

    updateCharts(data) {
        const currentTime = new Date().toLocaleTimeString();
        
        // Update Torque Chart
        if (this.torqueChart && data.inverters) {
            const torqueData = [
                data.inverters[3]?.target_torque || 0,
                data.inverters[4]?.target_torque || 0,
                data.inverters[3]?.torque || 0,
                data.inverters[4]?.torque || 0
            ];
            
            // Add new data point
            this.torqueChart.data.labels.push(currentTime);
            this.torqueChart.data.datasets.forEach((dataset, index) => {
                dataset.data.push(torqueData[index]);
            });
            
            // Limit data points
            if (this.torqueChart.data.labels.length > this.maxHistoryPoints) {
                this.torqueChart.data.labels.shift();
                this.torqueChart.data.datasets.forEach(dataset => {
                    dataset.data.shift();
                });
            }
            
            this.torqueChart.update('none');
        }
        
        // Update RPM Chart
        if (this.rpmChart && data.inverters) {
            const rpmData = [
                Math.abs(data.inverters[1]?.speed || 0),
                Math.abs(data.inverters[2]?.speed || 0),
                Math.abs(data.inverters[3]?.speed || 0),
                Math.abs(data.inverters[4]?.speed || 0)
            ];
            
            // Add new data point
            this.rpmChart.data.labels.push(currentTime);
            this.rpmChart.data.datasets.forEach((dataset, index) => {
                dataset.data.push(rpmData[index]);
            });
            
            // Limit data points
            if (this.rpmChart.data.labels.length > this.maxHistoryPoints) {
                this.rpmChart.data.labels.shift();
                this.rpmChart.data.datasets.forEach(dataset => {
                    dataset.data.shift();
                });
            }
            
            this.rpmChart.update('none');
        }
    }

    startHeartbeatCheck() {
        // Send periodic heartbeat to maintain WebSocket connection
        setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({ type: 'heartbeat' }));
            }
        }, 30000); // Send heartbeat every 30 seconds
    }
    initPlaybackControls() {
        // 檢查是否在 CSV 模式下顯示控制面板
        const controlsPanel = document.getElementById('floating-controls');
        const showControlsBtn = document.getElementById('show-controls-btn');
        
        if (controlsPanel && showControlsBtn) {
            // 顯示懸浮控制面板
            controlsPanel.style.display = 'block';
            showControlsBtn.style.display = 'block';
            
            // 初始化拖拽功能
            this.initDragFunction();
            
            // 初始化控制面板事件
            this.initControlEvents();
        }
    }

    initDragFunction() {
        const panel = document.getElementById('floating-controls');
        const header = document.querySelector('.floating-header');
        
        if (!panel || !header) return;
        
        let isDragging = false;
        let currentX = 0;
        let currentY = 0;
        let initialX = 0;
        let initialY = 0;
        let xOffset = 0;
        let yOffset = 0;
        
        // 獲取面板當前位置
        const rect = panel.getBoundingClientRect();
        xOffset = rect.left;
        yOffset = rect.top;
        
        header.addEventListener('mousedown', dragStart);
        document.addEventListener('mousemove', drag);
        document.addEventListener('mouseup', dragEnd);
        
        // 觸控支援
        header.addEventListener('touchstart', dragStart);
        document.addEventListener('touchmove', drag);
        document.addEventListener('touchend', dragEnd);
        
        function dragStart(e) {
            if (e.type === "touchstart") {
                initialX = e.touches[0].clientX - xOffset;
                initialY = e.touches[0].clientY - yOffset;
            } else {
                initialX = e.clientX - xOffset;
                initialY = e.clientY - yOffset;
            }
            
            if (e.target === header || header.contains(e.target)) {
                isDragging = true;
                panel.classList.add('dragging');
            }
        }
        
        function drag(e) {
            if (isDragging) {
                e.preventDefault();
                
                if (e.type === "touchmove") {
                    currentX = e.touches[0].clientX - initialX;
                    currentY = e.touches[0].clientY - initialY;
                } else {
                    currentX = e.clientX - initialX;
                    currentY = e.clientY - initialY;
                }
                
                xOffset = currentX;
                yOffset = currentY;
                
                // 限制在視窗範圍內
                const maxX = window.innerWidth - panel.offsetWidth;
                const maxY = window.innerHeight - panel.offsetHeight;
                
                xOffset = Math.max(0, Math.min(maxX, xOffset));
                yOffset = Math.max(0, Math.min(maxY, yOffset));
                
                panel.style.left = xOffset + 'px';
                panel.style.top = yOffset + 'px';
                panel.style.right = 'auto';
            }
        }
        
        function dragEnd() {
            initialX = currentX;
            initialY = currentY;
            isDragging = false;
            panel.classList.remove('dragging');
        }
    }

    initControlEvents() {
        // 最小化按鈕
        const minimizeBtn = document.getElementById('minimize-btn');
        const controlContent = document.getElementById('control-content');
        const panel = document.getElementById('floating-controls');
        
        if (minimizeBtn && controlContent) {
            minimizeBtn.addEventListener('click', () => {
                panel.classList.toggle('minimized');
                minimizeBtn.textContent = panel.classList.contains('minimized') ? '➕' : '➖';
            });
        }
        
        // 關閉按鈕
        const closeBtn = document.getElementById('close-btn');
        const showControlsBtn = document.getElementById('show-controls-btn');
        
        if (closeBtn && showControlsBtn) {
            closeBtn.addEventListener('click', () => {
                panel.classList.add('hide');
                setTimeout(() => {
                    panel.style.display = 'none';
                    showControlsBtn.style.display = 'block';
                }, 300);
            });
        }
        
        // 顯示控制面板按鈕
        if (showControlsBtn) {
            showControlsBtn.addEventListener('click', () => {
                panel.style.display = 'block';
                panel.classList.remove('hide');
                panel.classList.add('show');
                showControlsBtn.style.display = 'none';
            });
        }
        
        // 原有的控制按鈕事件
        const playPauseBtn = document.getElementById('play-pause-btn');
        if (playPauseBtn) {
            playPauseBtn.addEventListener('click', () => {
                this.togglePlayPause();
            });
        }
        
        const backwardBtn = document.getElementById('backward-btn');
        if (backwardBtn) {
            backwardBtn.addEventListener('click', () => {
                this.jumpTime(-10);
            });
        }
        
        const forwardBtn = document.getElementById('forward-btn');
        if (forwardBtn) {
            forwardBtn.addEventListener('click', () => {
                this.jumpTime(10);
            });
        }
        
        const speedSelect = document.getElementById('speed-select');
        if (speedSelect) {
            speedSelect.addEventListener('change', (e) => {
                this.setPlaybackSpeed(parseFloat(e.target.value));
            });
        }
        
        const fileSelect = document.getElementById('file-select');
        if (fileSelect) {
            fileSelect.addEventListener('change', (e) => {
                if (e.target.value) {
                    this.switchFile(e.target.value);
                }
            });
        }
        
        const progressBar = document.getElementById('progress-bar');
        if (progressBar) {
            progressBar.addEventListener('input', (e) => {
                this.jumpToPercentage(parseFloat(e.target.value));
            });
        }
    }

    async loadAvailableFiles() {
        try {
            const response = await fetch('/api/control/files');
            const data = await response.json();
            
            if (data.files) {
                const fileSelect = document.getElementById('file-select');
                if (fileSelect) {
                    fileSelect.innerHTML = '';
                    data.files.forEach(file => {
                        const option = document.createElement('option');
                        option.value = file;
                        option.textContent = file;
                        fileSelect.appendChild(option);
                    });
                }
            }
        } catch (error) {
            console.error('Failed to load available files:', error);
        }
    }

    async togglePlayPause() {
        try {
            // 先獲取當前狀態
            const statusResponse = await fetch('/api/control/status');
            const status = await statusResponse.json();
            
            const endpoint = status.is_paused ? '/api/control/resume' : '/api/control/pause';
            const response = await fetch(endpoint, { method: 'POST' });
            const result = await response.json();
            
            console.log('Play/Pause result:', result);
        } catch (error) {
            console.error('Failed to toggle play/pause:', error);
        }
    }

    async setPlaybackSpeed(speed) {
        try {
            const response = await fetch('/api/control/speed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ speed: speed })
            });
            const result = await response.json();
            console.log('Speed change result:', result);
        } catch (error) {
            console.error('Failed to set playback speed:', error);
        }
    }

    async jumpTime(seconds) {
        try {
            const response = await fetch('/api/control/jump', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seconds: seconds })
            });
            const result = await response.json();
            console.log('Jump result:', result);
        } catch (error) {
            console.error('Failed to jump time:', error);
        }
    }

    async jumpToPercentage(percentage) {
        try {
            const response = await fetch('/api/control/jump', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ percentage: percentage })
            });
            const result = await response.json();
            console.log('Jump to percentage result:', result);
        } catch (error) {
            console.error('Failed to jump to percentage:', error);
        }
    }

    async switchFile(filename) {
        try {
            const response = await fetch('/api/control/switch-file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            });
            const result = await response.json();
            console.log('File switch result:', result);
        } catch (error) {
            console.error('Failed to switch file:', error);
        }
    }

    updatePlaybackControls(data) {
        if (!data.playback_control) return;
        
        const control = data.playback_control;
        
        // 更新播放/暫停按鈕
        const playPauseBtn = document.getElementById('play-pause-btn');
        if (playPauseBtn) {
            playPauseBtn.textContent = control.is_paused ? '▶️ PLAY' : '⏸️ STOP';
            playPauseBtn.className = control.is_paused ? 
                'px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white font-medium transition-colors' :
                'px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors';
        }
        
        // 更新進度條
        const progressBar = document.getElementById('progress-bar');
        if (progressBar) {
            progressBar.value = control.progress;
        }
        
        // 更新時間顯示
        const currentTime = document.getElementById('current-time');
        const totalTime = document.getElementById('total-time');
        if (currentTime) currentTime.textContent = control.current_time;
        if (totalTime) totalTime.textContent = control.total_time;
        
        // 更新速度選擇
        const speedSelect = document.getElementById('speed-select');
        if (speedSelect) {
            speedSelect.value = control.speed;
        }
        
        // 更新檔案選擇
        const fileSelect = document.getElementById('file-select');
        if (fileSelect && control.current_file) {
            fileSelect.value = control.current_file;
        }
    }
    // Clean up resources
    destroy() {
        if (this.websocket) {
            this.websocket.close();
        }
        if (this.torqueChart) {
            this.torqueChart.destroy();
        }
        if (this.rpmChart) {
            this.rpmChart.destroy();
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new NTURTDashboard();
    
    // Handle page unload
    window.addEventListener('beforeunload', () => {
        if (window.dashboard) {
            window.dashboard.destroy();
        }
    });
});

// Export for potential external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NTURTDashboard;
}