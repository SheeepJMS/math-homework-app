/**
 * 诊断 Dashboard Chart.js 初始化
 */
(function () {
  'use strict';

  var tokens = {
    brand: '#2563eb',
    brandFill: 'rgba(37, 99, 235, 0.1)',
    success: '#16a34a',
    danger: '#ef4444',
    warning: '#f59e0b',
    border: '#e6e8f0',
    muted: '#6b7280',
  };

  function safeArray(val) {
    return Array.isArray(val) ? val : [];
  }

  function initTrendChart(canvasId, labels, values) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    labels = safeArray(labels);
    values = safeArray(values);
    if (labels.length === 0 || values.length === 0) return;
    if (typeof Chart === 'undefined') return;
    var lastVal = values[values.length - 1];
    var bgColors = values.map(function (_, i) {
      return i === values.length - 1 ? tokens.brand : tokens.brandFill;
    });
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: '正确率(%)',
          data: values,
          borderColor: tokens.brand,
          backgroundColor: tokens.brandFill,
          fill: true,
          tension: 0.3,
          pointBackgroundColor: values.map(function (v, i) {
            return i === values.length - 1 ? tokens.brand : tokens.brand;
          }),
          pointRadius: values.map(function (v, i) {
            return i === values.length - 1 ? 5 : 3;
          }),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { min: 0, max: 100, grid: { color: tokens.border }, ticks: { color: tokens.muted } },
          x: { grid: { display: false }, ticks: { color: tokens.muted } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(17,24,39,0.9)',
            titleColor: '#fff',
            bodyColor: '#fff',
            callbacks: {
              label: function (ctx) {
                return '正确率: ' + ctx.parsed.y + '%';
              },
            },
          },
          annotation: false,
        },
      },
      plugins: [{
        id: 'lastPointLabel',
        afterDatasetsDraw: function (chart) {
          if (values.length === 0) return;
          var meta = chart.getDatasetMeta(0);
          var lastPoint = meta.data[meta.data.length - 1];
          if (!lastPoint) return;
          var ctx = chart.ctx;
          ctx.save();
          ctx.font = '12px ' + (chart.options.font?.family || 'sans-serif');
          ctx.fillStyle = tokens.brand;
          ctx.textAlign = 'left';
          ctx.fillText(lastVal + '%', lastPoint.x + 6, lastPoint.y);
          ctx.restore();
        },
      }],
    });
  }

  function gaugeColorByDays(daysActive) {
    var d = Math.min(7, Math.max(0, parseInt(daysActive, 10) || 0));
    if (d === 0) return '#dc2626';
    if (d === 1) return '#ca8a04';
    if (d === 2) return '#84cc16';
    if (d === 3) return '#22c55e';
    return '#16a34a';
  }

  function initParticipationGauge(canvasId, wp) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    wp = wp || {};
    var pct = Math.min(100, Math.max(0, Number(wp.percentage) || 0));
    var daysActive = wp.days_active || 0;
    var fillColor = gaugeColorByDays(daysActive);
    if (typeof Chart === 'undefined') return;
    new Chart(ctx, {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [pct, 100 - pct],
          backgroundColor: [fillColor, '#e5e7eb'],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        circumference: 180,
        rotation: 270,
        cutout: '75%',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                if (ctx.dataIndex === 0) {
                  return (wp.days_active || 0) + '/' + (wp.total_days || 7) + ' 天有完成测验';
                }
                return null;
              },
            },
          },
        },
      },
    });
  }

  function initSixPanelRadarChart(canvasId, sixPanelRadar) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    sixPanelRadar = safeArray(sixPanelRadar);
    if (typeof Chart === 'undefined') return;
    var labels = sixPanelRadar.length ? sixPanelRadar.map(function (r) { return r.label || ''; }) : ['Number Theory', 'Algebra', 'Geometry', 'Counting', 'Word Problems', 'Sequences'];
    var values = sixPanelRadar.length ? sixPanelRadar.map(function (r) { return Math.min(100, Math.max(0, Number(r.value_0to100) || 0)); }) : [0, 0, 0, 0, 0, 0];
    new Chart(ctx, {
      type: 'radar',
      data: {
        labels: labels,
        datasets: [{
          label: '掌握度',
          data: values,
          borderColor: tokens.brand,
          backgroundColor: tokens.brandFill,
          borderWidth: 1.5,
          pointBackgroundColor: values.map(function (v) { return v > 0 ? tokens.brand : tokens.muted; }),
          pointRadius: 3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        scales: {
          r: {
            min: 0,
            max: 100,
            ticks: { stepSize: 25, color: tokens.muted },
            pointLabels: { font: { size: 11 }, color: tokens.muted },
            grid: { color: tokens.border },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return (ctx.dataset.label || '') + ': ' + ctx.raw + '%';
              },
            },
          },
        },
      },
    });
  }

  window.initDiagnosticDashboardCharts = function (data) {
    data = data || {};
    initTrendChart('trendChart', data.chart_trend_labels, data.chart_trend_values);
    initParticipationGauge('participationGauge', data.weekly_participation);
    initSixPanelRadarChart('sixPanelRadarChart', data.six_panel_radar || []);
  };
})();
