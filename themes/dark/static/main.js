/* SakuNav 主题交互脚本：客户端即时搜索过滤（无依赖、零请求） */
(function () {
  'use strict';

  var input = document.getElementById('nav-search-input');
  if (!input) return;

  input.addEventListener('input', function () {
    var q = input.value.trim().toLowerCase();
    var anyVisible = false;

    document.querySelectorAll('.link-card').forEach(function (card) {
      var hit = !q || (card.getAttribute('data-search') || '').indexOf(q) !== -1;
      card.style.display = hit ? '' : 'none';
      if (hit) anyVisible = true;
    });

    document.querySelectorAll('.category').forEach(function (sec) {
      var visible = false;
      sec.querySelectorAll('.link-card').forEach(function (c) {
        if (c.style.display !== 'none') visible = true;
      });
      sec.style.display = visible ? '' : 'none';
    });

    var noResult = document.getElementById('no-result');
    if (noResult) noResult.hidden = !(q && !anyVisible);
  });
})();
