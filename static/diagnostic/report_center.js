/**
 * 报告中心交互：同卷历史展开、竞赛/试卷联动、日期范围按钮
 */
(function () {
  'use strict';

  document.querySelectorAll('.rc-same-exam-toggle').forEach(function (lnk) {
    lnk.addEventListener('click', function (e) {
      e.preventDefault();
      var panel = document.getElementById('panel-' + this.getAttribute('data-card-id'));
      if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
      }
    });
  });

  document.querySelectorAll('.rc-range-btns button[data-range]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var r = this.getAttribute('data-range');
      var inp = document.getElementById('filterRange');
      if (inp) inp.value = r;
      document.querySelectorAll('.rc-range-btns button').forEach(function (b) { b.classList.remove('active'); });
      this.classList.add('active');
      var form = this.closest('form');
      if (form) form.submit();
    });
  });

  var compSel = document.getElementById('filterCompetition');
  var examSel = document.getElementById('filterExam');
  if (compSel && examSel) {
    compSel.addEventListener('change', function () {
      var cid = this.value;
      Array.prototype.forEach.call(examSel.querySelectorAll('option'), function (opt) {
        if (opt.value === '') { opt.style.display = ''; return; }
        opt.style.display = (!cid || opt.getAttribute('data-comp') === cid) ? '' : 'none';
        if (opt.style.display === 'none' && opt.selected) opt.selected = false;
      });
    });
  }
})();
