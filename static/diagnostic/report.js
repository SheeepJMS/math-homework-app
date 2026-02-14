/**
 * 诊断报告页 Chart.js 初始化
 * 使用 Design Tokens 颜色：brand #2563eb, success #16a34a
 * 轴线/网格用 border 色，Tooltip 深色半透明
 */
(function () {
  'use strict';

  var tokens = {
    brand: '#2563eb',
    brandRgba: 'rgba(37, 99, 235, 0.6)',
    brandFill: 'rgba(37, 99, 235, 0.12)',
    success: '#16a34a',
    successRgba: 'rgba(22, 163, 74, 0.8)',
    danger: '#ef4444',
    border: '#e6e8f0',
    muted: '#6b7280',
  };

  function safeArray(val) {
    return Array.isArray(val) ? val : [];
  }

  function initRadarChart(canvasId, labels, values) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    labels = safeArray(labels);
    values = safeArray(values);
    if (labels.length === 0) labels = ['暂无'];
    if (values.length === 0) values = [0];
    new Chart(ctx, {
      type: 'radar',
      data: {
        labels: labels,
        datasets: [{
          label: '掌握度',
          data: values,
          fill: true,
          backgroundColor: tokens.brandFill,
          borderColor: tokens.brand,
          pointBackgroundColor: tokens.brand,
          tension: 0.3,
        }],
      },
      options: {
        scales: {
          r: {
            min: 0,
            max: 100,
            grid: { color: tokens.border },
            angleLines: { color: tokens.border },
          },
        },
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { backgroundColor: 'rgba(17,24,39,0.9)', titleColor: '#fff', bodyColor: '#fff' },
        },
      },
    });
  }

  function initLineChart(canvasId, labels, values, hasCustomScoreScheme) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    labels = safeArray(labels);
    values = safeArray(values);
    if (labels.length === 0 || values.length === 0) return;
    var rateLabel = hasCustomScoreScheme ? '得分率' : '正确率';
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: '每题平均' + rateLabel + '(%)',
          data: values,
          borderColor: tokens.success,
          backgroundColor: 'rgba(22, 163, 74, 0.1)',
          fill: true,
          tension: 0.3,
          pointBackgroundColor: tokens.success,
        }],
      },
      options: {
        scales: {
          y: { min: 0, max: 100, grid: { color: tokens.border }, ticks: { color: tokens.muted } },
          x: { grid: { display: false }, ticks: { color: tokens.muted } },
        },
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(17,24,39,0.9)',
            titleColor: '#fff',
            bodyColor: '#fff',
            callbacks: {
              label: function (ctx) {
                return '第' + ctx.label + '题 平均' + rateLabel + ': ' + ctx.parsed.y + '%';
              },
            },
          },
        },
      },
    });
  }

  function initBarTimeChart(canvasId, labels, values) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    labels = safeArray(labels);
    values = safeArray(values);
    if (labels.length === 0 || values.length === 0) return;
    var n = labels.length;
    var wrap = ctx.closest('.chart-scroll-wrap');
    if (wrap) {
      var minW = Math.max(200, n * 20);
      wrap.querySelector('.chart-container-time').style.minWidth = minW + 'px';
    }
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: '耗时(秒)',
          data: values,
          backgroundColor: tokens.brandRgba,
          borderRadius: 4,
          barThickness: n > 20 ? 'flex' : undefined,
          maxBarThickness: n <= 10 ? 32 : 20,
          categoryPercentage: n > 15 ? 0.7 : 0.8,
          barPercentage: 0.8,
        }],
      },
      options: {
        maintainAspectRatio: false,
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
            grid: { color: tokens.border },
            ticks: { color: tokens.muted },
            grace: '5%',
          },
          x: {
            grid: { display: false },
            ticks: { color: tokens.muted, maxRotation: 45, minRotation: 0 },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(17,24,39,0.9)',
            titleColor: '#fff',
            bodyColor: '#fff',
            callbacks: {
              label: function (ctx) {
                return '第' + ctx.label + '题: ' + ctx.parsed.y + ' 秒';
              },
            },
          },
        },
      },
    });
  }

  function initBarCorrectChart(canvasId, labels, correctData) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    labels = safeArray(labels);
    correctData = safeArray(correctData);
    if (labels.length === 0 || correctData.length === 0) return;
    var bgColors = correctData.map(function (v) {
      return v ? tokens.successRgba : tokens.danger;
    });
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: '正确/错误',
          data: correctData,
          backgroundColor: bgColors,
          borderRadius: 6,
        }],
      },
      options: {
        maintainAspectRatio: false,
        scales: {
          y: { min: 0, max: 1, ticks: { stepSize: 1, color: tokens.muted }, grid: { color: tokens.border } },
          x: { grid: { display: false }, ticks: { color: tokens.muted } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  function initBarWeakChart(canvasId, labels, values, nQuestions) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    labels = safeArray(labels);
    values = safeArray(values);
    if (labels.length === 0 || values.length === 0) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: '错题数',
          data: values,
          backgroundColor: tokens.brandRgba,
          borderRadius: 6,
        }],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        scales: {
          x: { beginAtZero: true, grid: { color: tokens.border }, ticks: { color: tokens.muted } },
          y: { grid: { display: false }, ticks: { color: tokens.muted } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(17,24,39,0.9)',
            titleColor: '#fff',
            bodyColor: '#fff',
            callbacks: {
              afterLabel: function () {
                var idx = this.dataIndex;
                var n = (nQuestions && nQuestions[idx]) ? nQuestions[idx] : '';
                return n ? '样本量 n=' + n : '';
              },
            },
          },
        },
      },
    });
  }

  window.initDiagnosticReportCharts = function (data) {
      data = data || {};
      initRadarChart('radarChart', data.chart_radar_labels, data.chart_radar_values);
      initLineChart('lineChart', data.chart_line_x, data.chart_line_y, data.has_custom_score_scheme);
      initBarTimeChart('barTimeChart', data.chart_bar_labels, data.chart_bar_time);
      if (data && data.kp_weak_top) {
        var weakLabels = data.kp_weak_top.map(function (x) { return x.kp_name; });
        var weakValues = data.kp_weak_top.map(function (x) { return x.wrong_count; });
        var weakN = data.kp_weak_top.map(function (x) { return x.n_questions; });
        initBarWeakChart('barWeakChart', weakLabels, weakValues, weakN);
      }
    };
})();
