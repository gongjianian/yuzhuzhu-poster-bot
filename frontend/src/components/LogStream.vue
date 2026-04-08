<template>
  <div class="log-stream-container">
    <div class="log-toolbar">
      <div class="status-indicator" :class="connectionStatus">
        <span class="dot"></span>
        <span class="text">{{ statusText }}</span>
      </div>
      <div class="actions">
        <el-button
          :type="isPaused ? 'primary' : 'warning'"
          size="small"
          :icon="isPaused ? 'VideoPlay' : 'VideoPause'"
          @click="togglePause"
        >
          {{ isPaused ? '恢复滚动' : '暂停滚动' }}
        </el-button>
        <el-button size="small" icon="Delete" @click="clearLogs">清空</el-button>
      </div>
    </div>
    <div class="log-window" ref="logContainer">
      <div v-if="logs.length === 0" class="empty-state">等待日志输出...</div>
      <div
        v-for="(log, index) in logs"
        :key="index"
        class="log-line"
        :class="getLogClass(log)"
      >
        <span class="timestamp">[{{ log.timestamp }}]</span>
        <span class="level" :class="log.level.toLowerCase()">[{{ log.level }}]</span>
        <span class="message">{{ log.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'

const MAX_LINES = 500

interface LogEntry {
  timestamp: string
  level: string
  message: string
}

const authStore = useAuthStore()
const logs = ref<LogEntry[]>([])
const logContainer = ref<HTMLElement | null>(null)
const ws = ref<WebSocket | null>(null)
const isPaused = ref(false)
const connectionStatus = ref<'connecting' | 'connected' | 'disconnected'>('disconnected')

// Reconnect state - track timer and disposal flag to prevent leaks
let reconnectTimer: number | null = null
let isDisposed = false
let reconnectAttempts = 0
const MAX_RECONNECT_DELAY = 30000  // 30s cap

const statusText = computed(() => {
  const map = {
    connecting: '连接中...',
    connected: '已连接 (实时)',
    disconnected: '已断开连接'
  }
  return map[connectionStatus.value]
})

const scheduleReconnect = () => {
  if (isDisposed) return  // Component unmounted - stop reconnecting
  if (reconnectTimer !== null) return  // Already scheduled

  // Exponential backoff: 3s, 6s, 12s, 24s, capped at 30s
  const delay = Math.min(3000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY)
  reconnectAttempts++

  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    if (!isDisposed) {
      connectWebSocket()
    }
  }, delay)
}

const connectWebSocket = () => {
  if (isDisposed) return  // Don't reconnect if component is unmounted

  if (ws.value) {
    ws.value.onclose = null  // Prevent old socket from triggering reconnect
    ws.value.close()
  }

  connectionStatus.value = 'connecting'

  // Construct WebSocket URL
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const wsUrl = `${protocol}//${host}/api/logs/stream?token=${authStore.token}`

  ws.value = new WebSocket(wsUrl)

  ws.value.onopen = () => {
    connectionStatus.value = 'connected'
    reconnectAttempts = 0  // Reset backoff on successful connection
  }

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      appendLog(data)
    } catch (e) {
      // Fallback for plain text parsing
      appendLog({
        timestamp: new Date().toISOString(),
        level: 'INFO',
        message: event.data
      })
    }
  }

  ws.value.onclose = () => {
    connectionStatus.value = 'disconnected'
    scheduleReconnect()
  }

  ws.value.onerror = () => {
    connectionStatus.value = 'disconnected'
    // onclose will fire after onerror, no need to schedule here
  }
}

const appendLog = (log: LogEntry) => {
  logs.value.push(log)
  if (logs.value.length > MAX_LINES) {
    logs.value.shift() // Remove oldest log to maintain limit
  }
  
  if (!isPaused.value) {
    scrollToBottom()
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

const togglePause = () => {
  isPaused.value = !isPaused.value
  if (!isPaused.value) {
    scrollToBottom()
  }
}

const clearLogs = () => {
  logs.value = []
}

const getLogClass = (log: LogEntry) => {
  return `log-${log.level.toLowerCase()}`
}

onMounted(() => {
  isDisposed = false
  reconnectAttempts = 0
  connectWebSocket()
})

onUnmounted(() => {
  // Mark as disposed first so any in-flight callbacks become no-ops
  isDisposed = true

  // Clear pending reconnect timer
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  // Close socket without triggering onclose reconnect
  if (ws.value) {
    ws.value.onclose = null
    ws.value.onerror = null
    ws.value.close()
    ws.value = null
  }
})
</script>

<style scoped>
.log-stream-container {
  display: flex;
  flex-direction: column;
  height: 500px;
  background-color: #1e1e1e;
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid #434343;
}

.log-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: #2d2d2d;
  border-bottom: 1px solid #434343;
}

.status-indicator {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #cccccc;
}

.status-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  background-color: #cccccc;
}

.status-indicator.connected .dot {
  background-color: #67C23A;
  box-shadow: 0 0 5px #67C23A;
}

.status-indicator.disconnected .dot {
  background-color: #F56C6C;
}

.status-indicator.connecting .dot {
  background-color: #E6A23C;
  animation: blink 1s infinite alternate;
}

@keyframes blink {
  from { opacity: 0.5; }
  to { opacity: 1; }
}

.log-window {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #cccccc;
}

.empty-state {
  text-align: center;
  color: #666666;
  margin-top: 20px;
}

.log-line {
  margin-bottom: 4px;
  word-break: break-all;
}

.timestamp {
  color: #888888;
  margin-right: 8px;
}

.level {
  font-weight: bold;
  margin-right: 8px;
  width: 80px;
  display: inline-block;
}

.level.info { color: #67C23A; }
.level.warning, .level.warn { color: #E6A23C; }
.level.error { color: #F56C6C; }
.level.debug { color: #909399; }

.log-error .message { color: #F56C6C; }
.log-warning .message { color: #E6A23C; }

/* Custom Scrollbar for log window */
.log-window::-webkit-scrollbar {
  width: 10px;
}
.log-window::-webkit-scrollbar-track {
  background: #1e1e1e;
}
.log-window::-webkit-scrollbar-thumb {
  background: #434343;
  border-radius: 5px;
}
.log-window::-webkit-scrollbar-thumb:hover {
  background: #555555;
}
</style>
