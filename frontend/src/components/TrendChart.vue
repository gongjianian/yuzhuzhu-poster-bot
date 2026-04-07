<template>
  <v-chart class="chart" :option="option" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const props = defineProps<{
  dates: string[]
  successData: number[]
  failedData: number[]
}>()

const option = computed(() => ({
  title: {
    text: '近 7 天海报生成趋势',
    left: 'center',
    textStyle: {
      color: '#303133',
      fontSize: 16
    }
  },
  tooltip: {
    trigger: 'axis'
  },
  legend: {
    data: ['成功', '失败'],
    bottom: '0'
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '15%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.dates,
    axisLine: {
      lineStyle: {
        color: '#909399'
      }
    }
  },
  yAxis: {
    type: 'value',
    axisLine: {
      lineStyle: {
        color: '#909399'
      }
    },
    splitLine: {
      lineStyle: {
        color: '#EBEEF5'
      }
    }
  },
  series: [
    {
      name: '成功',
      type: 'line',
      data: props.successData,
      itemStyle: {
        color: '#67C23A'
      },
      lineStyle: {
        width: 3
      },
      smooth: true
    },
    {
      name: '失败',
      type: 'line',
      data: props.failedData,
      itemStyle: {
        color: '#F56C6C'
      },
      lineStyle: {
        width: 3
      },
      smooth: true
    }
  ]
}))
</script>

<style scoped>
.chart {
  height: 350px;
  width: 100%;
}
</style>
