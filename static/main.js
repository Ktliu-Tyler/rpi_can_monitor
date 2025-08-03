
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
        this.cellVoltageChart = null;
        this.cellTempChart = null;     
        
        // Initialize components
        this.initWebSocket();
        this.initCharts();
        this.startHeartbeatCheck();

        this.initPlaybackControls();
        this.loadAvailableFiles();
        this.loadCurrentMode();
        this.loadCanLoggingStatus();
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
            
            // Update battery information bar
            this.updateBatteryInfo(data.accumulator);
            
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
            
            // Update CAN logging status
            this.updateCanLoggingStatus(data.canlogging);
            
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

    updateBatteryInfo(accumulator) {
        if (!accumulator) return;
        
        // Update SOC (State of Charge)
        if (accumulator.soc !== null && accumulator.soc !== undefined) {
            const socPercent = Math.max(0, Math.min(100, accumulator.soc));
            const socBar = document.getElementById('battery-soc-bar');
            const socValue = document.getElementById('battery-soc-value');
            
            if (socBar) {
                socBar.style.width = `${socPercent}%`;
                // 根據電量變更顏色
                if (socPercent > 50) {
                    socBar.className = 'battery-bar bg-green-500 h-full rounded transition-all duration-300';
                } else if (socPercent > 20) {
                    socBar.className = 'battery-bar bg-yellow-500 h-full rounded transition-all duration-300';
                } else {
                    socBar.className = 'battery-bar bg-red-500 h-full rounded transition-all duration-300';
                }
            }
            if (socValue) socValue.textContent = `${socPercent}%`;
        }
        
        // Update Battery Temperature
        if (accumulator.temperature !== null && accumulator.temperature !== undefined) {
            const tempValue = document.getElementById('battery-temp-value');
            if (tempValue) {
                tempValue.textContent = `${accumulator.temperature.toFixed(1)}°C`;
                // 根據溫度變更顏色
                if (accumulator.temperature > 60) {
                    tempValue.className = 'text-red-400 font-bold';
                } else if (accumulator.temperature > 45) {
                    tempValue.className = 'text-yellow-400 font-bold';
                } else {
                    tempValue.className = 'text-green-400 font-bold';
                }
            }
        }
        
        // Calculate and update Total Voltage (sum of all cell voltages)
        if (accumulator.cell_voltages && Array.isArray(accumulator.cell_voltages)) {
            let totalVoltage = 0;
            let validCells = 0;
            
            accumulator.cell_voltages.forEach(voltage => {
                if (voltage !== null && voltage !== undefined && voltage !== -13 && voltage > 0) {
                    totalVoltage += voltage;
                    validCells++;
                }
            });
            
            const voltageValue = document.getElementById('battery-voltage-value');
            if (voltageValue) {
                voltageValue.textContent = `${totalVoltage.toFixed(1)}V`;
            }
            
            // Update valid cells count
            const cellCountValue = document.getElementById('battery-cells-count');
            if (cellCountValue) {
                cellCountValue.textContent = `${validCells} cells`;
            }
        }
        
        // Update Pack Voltage from direct reading
        if (accumulator.voltage !== null && accumulator.voltage !== undefined) {
            const packVoltageValue = document.getElementById('battery-pack-voltage');
            if (packVoltageValue) {
                packVoltageValue.textContent = `${accumulator.voltage.toFixed(1)}V`;
            }
        }
        
        // Update Current
        if (accumulator.current !== null && accumulator.current !== undefined) {
            const currentValue = document.getElementById('battery-current-value');
            if (currentValue) {
                currentValue.textContent = `${accumulator.current.toFixed(2)}A`;
                // 根據電流方向變更顏色 (正值充電，負值放電)
                if (accumulator.current > 0) {
                    currentValue.className = 'text-green-400 font-bold';
                } else {
                    currentValue.className = 'text-orange-400 font-bold';
                }
            }
        }
    }

    updateVCUData(vcu) {
        if (!vcu) return;
        
        // Update APPS bar and value
        if (vcu.accel !== null && vcu.accel !== undefined) {
            const appsPercent = vcu.accel;
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
                speed = avgRPM * 0.00709; // RPM to km/h conversion
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
            rpmValue.textContent = Math.round(speed / 0.00709); 
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
                    const speed = rpm * 0.00709; // RPM轉換為km/h
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
                
                // Update status with visual indicators
                const statusContainer = card.querySelector('.inv-status-container');
                if (statusContainer && data.status !== null) {
                    const statusInfo = this.formatInverterStatus(data.status);
                    statusContainer.innerHTML = this.generateStatusHTML(statusInfo);
                }
                
                // Update other fields
                this.updateInverterField(card, '.inv-torque', data.torque !== null ? `${data.torque.toFixed(2)} Nm` : 'N/A');
                this.updateInverterField(card, '.inv-dc-voltage', data.dc_voltage !== null ? `${data.dc_voltage.toFixed(1)} V` : 'N/A');
                this.updateInverterField(card, '.inv-dc-current', data.dc_current !== null ? `${data.dc_current.toFixed(1)} A` : 'N/A');
                this.updateInverterField(card, '.inv-mos-temp', data.mos_temp !== null ? `${data.mos_temp.toFixed(1)}°C` : 'N/A');
                this.updateInverterField(card, '.inv-motor-temp', data.motor_temp !== null ? `${data.motor_temp.toFixed(1)}°C` : 'N/A');
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

    generateStatusHTML(statusInfo) {
        if (typeof statusInfo === 'string') {
            return statusInfo;
        }
        
        const readyLight = statusInfo.ready ? 'status-light-green' : 'status-light-red';
        const enabledLight = statusInfo.enabled ? 'status-light-green' : 'status-light-red';
        const faultLight = statusInfo.fault ? 'status-light-red' : 'status-light-green';
        const hvLight = statusInfo.hv ? 'status-light-green' : 'status-light-red';
        
        const errorClass = statusInfo.errorCode === 0x0000 ? 'error-none' : 'error-active';
        
        return `
            <div class="status-indicators">
                <div class="status-row">
                    <span class="status-label">Ready:</span>
                    <span class="status-light ${readyLight}"></span>
                </div>
                <div class="status-row">
                    <span class="status-label">Enable:</span>
                    <span class="status-light ${enabledLight}"></span>
                </div>
                <div class="status-row">
                    <span class="status-label">Fault:</span>
                    <span class="status-light ${faultLight}"></span>
                </div>
                <div class="status-row">
                    <span class="status-label">HV:</span>
                    <span class="status-light ${hvLight}"></span>
                </div>
                <div class="error-info ${errorClass}">
                    <div class="error-text">${statusInfo.errorText}</div>
                    <div class="error-code">(0x${statusInfo.errorCode.toString(16).padStart(4, '0').toUpperCase()})</div>
                </div>
            </div>
        `;
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

        // Initialize Cell Voltage Chart
        const cellVoltageCtx = document.getElementById('cell-voltage-chart');
        if (cellVoltageCtx) {
            this.cellVoltageChart = new Chart(cellVoltageCtx, {
                type: 'bar',
                data: {
                    labels: ['Group 1', 'Group 2', 'Group 3', 'Group 4', 'Group 5', 'Group 6', 'Group 7'],
                    datasets: [{
                        label: 'Voltage Sum (V)',
                        data: [0, 0, 0, 0, 0, 0, 0],
                        backgroundColor: 'rgba(234, 179, 8, 0.6)',
                        borderColor: '#eab308',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#e2e8f0' } }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        },
                        y: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' },
                            title: {
                                display: true,
                                text: 'Voltage (V)',
                                color: '#e2e8f0'
                            }
                        }
                    },
                    animation: { duration: 0 }
                }
            });
        }

        // Initialize Cell Temperature Chart
        const cellTempCtx = document.getElementById('cell-temperature-chart');
        if (cellTempCtx) {
            this.cellTempChart = new Chart(cellTempCtx, {
                type: 'bar',
                data: {
                    labels: ['Group 1', 'Group 2', 'Group 3', 'Group 4', 'Group 5', 'Group 6', 'Group 7'],
                    datasets: [{
                        label: 'Temperature Avg (°C)',
                        data: [0, 0, 0, 0, 0, 0, 0],
                        backgroundColor: 'rgba(249, 115, 22, 0.6)',
                        borderColor: '#f97316',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#e2e8f0' } }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        },
                        y: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' },
                            title: {
                                display: true,
                                text: 'Temperature (°C)',
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
        const currentTime = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        
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
        // Update Cell Voltage Chart
        if (this.cellVoltageChart && data.accumulator && data.accumulator.cell_voltages) {
            const voltageGroups = this.processCellVoltages(data.accumulator.cell_voltages);
            this.cellVoltageChart.data.datasets[0].data = voltageGroups;
            this.cellVoltageChart.update('none');
        }

        // Update Cell Temperature Chart
        if (this.cellTempChart && data.accumulator && data.accumulator.cell_temperatures) {
            const tempGroups = this.processCellTemperatures(data.accumulator.cell_temperatures);
            this.cellTempChart.data.datasets[0].data = tempGroups;
            this.cellTempChart.update('none');
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
                
        const modeToggleBtn = document.getElementById('mode-toggle-btn');
        if (modeToggleBtn) {
            modeToggleBtn.addEventListener('click', () => {
                this.toggleMode();
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
        
        // CAN Logging 控制按鈕
        const startLoggingBtn = document.getElementById('start-logging-btn');
        if (startLoggingBtn) {
            startLoggingBtn.addEventListener('click', () => {
                this.startCanLogging();
            });
        }
        
        const stopLoggingBtn = document.getElementById('stop-logging-btn');
        if (stopLoggingBtn) {
            stopLoggingBtn.addEventListener('click', () => {
                this.stopCanLogging();
            });
        }
    }

    async toggleMode() {
        try {
            // 先獲取當前模式
            const modeResponse = await fetch('/api/control/mode');
            const currentMode = await modeResponse.json();
            
            const newMode = !currentMode.use_csv; // 切換到相反模式
            
            const response = await fetch('/api/control/switch-mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ use_csv: newMode })
            });
            
            const result = await response.json();
            
            if (result.status) {
                console.log('Mode switch result:', result);
                // 更新按鈕顯示
                this.updateModeButton(newMode);
                
                // 如果切換到 CSV 模式，刷新檔案選擇器
                if (newMode) {
                    await this.refreshFileSelector();
                }
            } else {
                console.error('Failed to switch mode:', result.error);
                await this.refreshFileSelector();
            }
        } catch (error) {
            console.error('Failed to toggle mode:', error);
            await this.refreshFileSelector();
        }
    }

    async loadCurrentMode() {
        try {
            const response = await fetch('/api/control/mode');
            const mode = await response.json();
            
            if (!mode.error) {
                this.updateModeButton(mode.use_csv);
                
                // 如果是 CAN 模式但 CAN 不可用，顯示警告
                if (!mode.use_csv && !mode.can_available) {
                    console.warn('CAN mode selected but CAN interface not available');
                }
            }
        } catch (error) {
            console.error('Failed to load current mode:', error);
        }
    }

    updateCanLoggingStatus(canloggingData) {
        if (!canloggingData) return;
        
        // 更新記錄狀態指示器
        const statusIndicator = document.getElementById('canlogging-status');
        const statusText = document.getElementById('canlogging-status-text');
        const startTimeText = document.getElementById('canlogging-start-time');
        
        if (statusIndicator && statusText) {
            if (canloggingData.is_recording) {
                statusIndicator.className = 'status-indicator recording';
                statusText.textContent = 'RECORDING';
            } else {
                statusIndicator.className = 'status-indicator idle';
                statusText.textContent = 'IDLE';
            }
        }
        
        // 更新開始時間
        if (startTimeText) {
            if (canloggingData.start_time) {
                startTimeText.textContent = `Started: ${canloggingData.start_time}`;
            } else {
                startTimeText.textContent = 'No active recording';
            }
        }
    }

    async startCanLogging() {
        try {
            const response = await fetch('/api/canlogging/start', {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.status === 'success') {
                console.log('CAN logging started:', result.message);
                // 可以添加成功提示
            } else {
                console.error('Failed to start CAN logging:', result.message);
                // 可以添加錯誤提示
            }
        } catch (error) {
            console.error('Error starting CAN logging:', error);
        }
    }

    async stopCanLogging() {
        try {
            const response = await fetch('/api/canlogging/stop', {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.status === 'success') {
                console.log('CAN logging stopped:', result.message);
                // 可以添加成功提示
            } else {
                console.error('Failed to stop CAN logging:', result.message);
                // 可以添加錯誤提示
            }
        } catch (error) {
            console.error('Error stopping CAN logging:', error);
        }
    }

    async loadCanLoggingStatus() {
        try {
            const response = await fetch('/api/canlogging/status');
            const status = await response.json();
            
            if (!status.error) {
                // 手動調用 updateCanLoggingStatus 來初始化顯示
                const mockData = {
                    is_recording: status.is_recording,
                    start_time: status.start_time,
                    start_timestamp: status.start_timestamp
                };
                this.updateCanLoggingStatus(mockData);
            }
        } catch (error) {
            console.error('Failed to load CAN logging status:', error);
        }
    }

    updateModeButton(useCsv) {
        const modeToggleBtn = document.getElementById('mode-toggle-btn');
        if (modeToggleBtn) {
            if (useCsv) {
                modeToggleBtn.textContent = '📁 CSV Mode';
                modeToggleBtn.className = 'control-btn secondary';
                modeToggleBtn.title = 'Click to switch to CAN mode';
            } else {
                modeToggleBtn.textContent = '🔌 CAN Mode';
                modeToggleBtn.className = 'control-btn primary';
                modeToggleBtn.title = 'Click to switch to CSV mode';
            }
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

    async refreshFileSelector() {
        try {
            // 先刷新後端的檔案列表
            const refreshResponse = await fetch('/api/control/refresh-files', {
                method: 'POST'
            });
            const refreshResult = await refreshResponse.json();
            
            if (refreshResult.status) {
                console.log(`Files refreshed: ${refreshResult.count} files found`);
                
                // 然後更新前端的選擇器
                const fileSelect = document.getElementById('file-select');
                if (fileSelect && refreshResult.files) {
                    fileSelect.innerHTML = '';
                    refreshResult.files.forEach(file => {
                        const option = document.createElement('option');
                        option.value = file;
                        option.textContent = file;
                        fileSelect.appendChild(option);
                    });
                }
            } else {
                console.error('Failed to refresh files:', refreshResult.error);
            }
        } catch (error) {
            console.error('Failed to refresh file selector:', error);
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
            
            const playPauseBtn = document.getElementById('play-pause-btn');
            if (playPauseBtn) {
            const isPaused = !status.is_paused;
                playPauseBtn.textContent = isPaused ? '▶️ PLAY' : '⏸️ STOP';
                playPauseBtn.className = isPaused ?
                    'px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white font-medium transition-colors' :
                    'px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors';
            }
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

    processCellVoltages(voltages) {
        const groups = [];
        for (let i = 0; i < 7; i++) {
            let sum = 0;
            let count = 0;
            const startIndex = i * 15;
            const endIndex = Math.min(startIndex + 15, voltages.length);
            
            for (let j = startIndex; j < endIndex; j++) {
                if (voltages[j] !== null && voltages[j] !== undefined && voltages[j] !== -13) {
                    sum += voltages[j];
                    count++;
                }
            }
            groups.push(count > 0 ? sum : 0);
        }
        return groups;
    }

    processCellTemperatures(temperatures) {
        const groups = [];
        for (let i = 0; i < 7; i++) {
            let sum = 0;
            let count = 0;
            const startIndex = i * 32;
            const endIndex = Math.min(startIndex + 32, temperatures.length);
            
            for (let j = startIndex; j < endIndex; j++) {
                if (temperatures[j] !== null && temperatures[j] !== undefined && temperatures[j] !== -13) {
                    sum += temperatures[j];
                    count++;
                }
            }
            groups.push(count > 0 ? sum / count : 0);
        }
        return groups;
    }

    formatInverterStatus(status) {
        if (status === null || status === undefined) {
            return '<span class="status-unknown">N/A</span>';
        }
        
        let INVready = false;
        let INVenabled = false;
        let INVfault = false;
        let HV = false;
        
        for (let i = 0; i < 8; i++) {
            if ((status[0] >> i) & 0x01) {
                switch (i) {
                    case 1:
                        INVready = true;
                        break;
                    case 2:
                        INVenabled = true;
                        break;
                    case 3:
                        INVfault = true;
                        break;
                    case 4:
                        HV = true;
                        break;
                }
            }
        }
        
        let statusText3 = '';
        let ERRORstatus = status[1];
        
        switch (ERRORstatus) {
            case 0x0000:
                statusText3 = 'ERROR_NONE';
                break;
            case 0x0001:
                statusText3 = 'ERROR_INSTANT_OC';
                break;
            case 0x0002:
                statusText3 = 'ERROR_RMS_OC';
                break;
            case 0x0003:
                statusText3 = 'ERROR_INV_OT';
                break;
            case 0x0004:
                statusText3 = 'ERROR_MOT_OT';
                break;
            case 0x0005:
                statusText3 = 'ERROR_ENC';
                break;
            case 0x0006:
                statusText3 = 'ERROR_CAN_OT';
                break;
            case 0x0007:
                statusText3 = 'ERROR_GATE';
                break;
            case 0x0008:
                statusText3 = 'ERROR_HW_OC';
                break;
            default:
                statusText3 = 'Unknown Error';
                break;
        }
        
        return {
            ready: INVready,
            enabled: INVenabled,
            fault: INVfault,
            hv: HV,
            errorText: statusText3,
            errorCode: ERRORstatus
        };
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
        if (this.cellVoltageChart) {
            this.cellVoltageChart.destroy();
        }
        if (this.cellTempChart) {
            this.cellTempChart.destroy();
        }
    }

    // CAN Logging Methods
    updateCanLoggingStatus(canlogging) {
        if (!canlogging) return;
        
        const statusElement = document.getElementById('canlogging-status');
        const statusTextElement = document.getElementById('canlogging-status-text');
        const startTimeElement = document.getElementById('canlogging-start-time');
        
        if (statusElement && statusTextElement) {
            if (canlogging.is_recording) {
                statusElement.className = 'status-indicator recording';
                statusTextElement.textContent = 'RECORDING';
                statusTextElement.className = 'text-lg font-bold text-red-400';
            } else {
                statusElement.className = 'status-indicator idle';
                statusTextElement.textContent = 'IDLE';
                statusTextElement.className = 'text-lg font-bold text-slate-300';
            }
        }
        
        if (startTimeElement) {
            if (canlogging.start_time) {
                const startTime = new Date(canlogging.start_time + 'Z'); // 確保時區正確
                startTimeElement.textContent = `Recording started: ${startTime.toLocaleString()}`;
                startTimeElement.className = 'text-sm text-green-400';
            } else {
                startTimeElement.textContent = 'No active recording';
                startTimeElement.className = 'text-sm text-slate-400';
            }
        }
    }

    async startCanLogging() {
        try {
            const response = await fetch('/api/canlogging/start', {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.status === 'success') {
                console.log('CAN logging started:', result.message);
                // 可以添加成功提示
            } else {
                console.error('Failed to start CAN logging:', result.message);
                // 可以添加錯誤提示
            }
        } catch (error) {
            console.error('Error starting CAN logging:', error);
        }
    }

    async stopCanLogging() {
        try {
            const response = await fetch('/api/canlogging/stop', {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.status === 'success') {
                console.log('CAN logging stopped:', result.message);
                // 可以添加成功提示
            } else {
                console.error('Failed to stop CAN logging:', result.message);
                // 可以添加錯誤提示
            }
        } catch (error) {
            console.error('Error stopping CAN logging:', error);
        }
    }

    async loadCanLoggingStatus() {
        try {
            const response = await fetch('/api/data');
            const data = await response.json();
            
            if (!data.error && data.canlogging) {
                this.updateCanLoggingStatus(data.canlogging);
            }
        } catch (error) {
            console.error('Failed to load CAN logging status:', error);
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