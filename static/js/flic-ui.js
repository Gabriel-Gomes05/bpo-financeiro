/* FLIC — comportamento da interface (tema, menu, toasts, carregamento, tabelas).
   Não altera regras de negócio: só apresentação. */
(function () {
  'use strict';
  var root = document.documentElement;

  function guardar(chave, valor) { try { localStorage.setItem(chave, valor); } catch (_) {} }
  function ler(chave) { try { return localStorage.getItem(chave); } catch (_) { return null; } }
  function icones(escopo) {
    if (window.lucide && window.lucide.createIcons) {
      window.lucide.createIcons({ attrs: { 'stroke-width': 1.8 }, nameAttr: "data-lucide" });
    }
  }

  /* ---------------------------------------------------------------- tema */
  function aplicarTema(escuro, animar) {
    if (animar) {
      root.classList.add('theme-transition');
      setTimeout(function () { root.classList.remove('theme-transition'); }, 320);
    }
    root.classList.toggle('dark', escuro);
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(escuro));
      btn.setAttribute('data-tip', escuro ? 'Modo claro' : 'Modo escuro');
      btn.setAttribute('aria-label', escuro ? 'Ativar modo claro' : 'Ativar modo escuro');
    });
    document.dispatchEvent(new CustomEvent('flic:tema', { detail: { escuro: escuro } }));
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-theme-toggle]');
    if (!btn) return;
    var escuro = !root.classList.contains('dark');
    guardar('flic-tema', escuro ? 'escuro' : 'claro');
    aplicarTema(escuro, true);
  });
  // Segue o sistema enquanto o usuário não escolher um tema.
  var preferencia = window.matchMedia ? matchMedia('(prefers-color-scheme: dark)') : null;
  if (preferencia && preferencia.addEventListener) {
    preferencia.addEventListener('change', function (e) { if (!ler('flic-tema')) aplicarTema(e.matches, true); });
  }

  /* ---------------------------------------------------------------- menu lateral */
  function iniciarMenu() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    var recolher = document.getElementById('fx-collapse-toggle');
    var abrir = document.getElementById('fx-mobile-toggle');
    var overlay = document.getElementById('fx-overlay');
    var mobile = matchMedia('(max-width: 767px)');

    if (recolher) {
      recolher.addEventListener('click', function () {
        var recolhido = root.dataset.sidebar !== 'collapsed';
        if (recolhido) root.dataset.sidebar = 'collapsed'; else delete root.dataset.sidebar;
        guardar('flic-sidebar', recolhido ? 'recolhida' : 'aberta');
        recolher.setAttribute('aria-expanded', String(!recolhido));
        recolher.setAttribute('data-tip', recolhido ? 'Expandir menu' : 'Recolher menu');
      });
    }

    function setAberto(aberto) {
      var mostrar = aberto && mobile.matches;
      sidebar.dataset.open = String(mostrar);
      sidebar.inert = mobile.matches && !mostrar;
      if (abrir) abrir.setAttribute('aria-expanded', String(mostrar));
      if (overlay) overlay.hidden = !mostrar;
      document.body.style.overflow = mostrar ? 'hidden' : '';
      if (mostrar) { var link = sidebar.querySelector('a'); if (link) link.focus(); }
    }
    if (abrir) abrir.addEventListener('click', function () { setAberto(sidebar.dataset.open !== 'true'); });
    if (overlay) overlay.addEventListener('click', function () { setAberto(false); if (abrir) abrir.focus(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sidebar.dataset.open === 'true') { setAberto(false); if (abrir) abrir.focus(); }
    });
    mobile.addEventListener('change', function () { setAberto(false); });
    setAberto(false);

    // mantém o item ativo visível quando o menu é longo
    var ativo = sidebar.querySelector('[aria-current="page"]');
    if (ativo && ativo.scrollIntoView) ativo.scrollIntoView({ block: 'nearest' });
  }

  /* ---------------------------------------------------------------- tooltips */
  var dica;
  function mostrarDica(alvo) {
    var texto = alvo.getAttribute('data-tip');
    if (!texto) return;
    // No menu lateral a dica só faz sentido quando ele está recolhido (os rótulos estão ocultos).
    if (alvo.closest('#sidebar') && !(root.dataset.sidebar === 'collapsed' && matchMedia('(min-width: 768px)').matches)) return;
    if (!dica) { dica = document.createElement('div'); dica.className = 'fx-tooltip'; dica.setAttribute('role', 'tooltip'); document.body.appendChild(dica); }
    dica.textContent = texto;
    dica.classList.remove('is-visible');
    var r = alvo.getBoundingClientRect();
    var embaixo = alvo.getAttribute('data-tip-pos') === 'bottom';
    dica.style.left = '0px'; dica.style.top = '0px';
    var w = dica.offsetWidth, h = dica.offsetHeight;
    var x = embaixo ? r.left + r.width / 2 - w / 2 : r.right + 10;
    var y = embaixo ? r.bottom + 8 : r.top + r.height / 2 - h / 2;
    x = Math.max(8, Math.min(x, innerWidth - w - 8));
    y = Math.max(8, Math.min(y, innerHeight - h - 8));
    dica.style.left = x + 'px'; dica.style.top = y + 'px';
    requestAnimationFrame(function () { dica.classList.add('is-visible'); });
  }
  function esconderDica() { if (dica) dica.classList.remove('is-visible'); }
  document.addEventListener('mouseover', function (e) {
    var alvo = e.target.closest && e.target.closest('[data-tip]');
    if (alvo) mostrarDica(alvo); else esconderDica();
  });
  document.addEventListener('focusin', function (e) { var alvo = e.target.closest && e.target.closest('[data-tip]'); if (alvo) mostrarDica(alvo); });
  document.addEventListener('focusout', esconderDica);
  window.addEventListener('scroll', esconderDica, true);

  /* ---------------------------------------------------------------- toasts */
  var ICONES_TOAST = { sucesso: 'check-circle-2', erro: 'alert-octagon', aviso: 'alert-triangle', info: 'info' };
  var TITULOS_TOAST = { sucesso: 'Tudo certo', erro: 'Não foi possível concluir', aviso: 'Atenção', info: 'Aviso' };
  function toast(mensagem, tipo, opcoes) {
    tipo = tipo || 'info';
    opcoes = opcoes || {};
    var area = document.getElementById('fx-toasts');
    if (!area) {
      area = document.createElement('div');
      area.id = 'fx-toasts';
      area.className = 'fx-toasts';
      area.setAttribute('aria-live', 'polite');
      document.body.appendChild(area);
    }
    var el = document.createElement('div');
    el.className = 'fx-toast';
    el.dataset.tipo = tipo;
    el.setAttribute('role', tipo === 'erro' ? 'alert' : 'status');
    var icone = document.createElement('span');
    icone.className = 'fx-toast-icon';
    icone.innerHTML = '<i data-lucide="' + (ICONES_TOAST[tipo] || 'info') + '"></i>';
    var corpo = document.createElement('div');
    corpo.style.minWidth = '0';
    var titulo = document.createElement('p');
    titulo.className = 'fx-toast-title';
    titulo.textContent = opcoes.titulo || TITULOS_TOAST[tipo] || '';
    var texto = document.createElement('p');
    texto.className = 'fx-toast-msg';
    texto.textContent = mensagem;
    corpo.appendChild(titulo);
    corpo.appendChild(texto);
    var fechar = document.createElement('button');
    fechar.type = 'button';
    fechar.className = 'fx-toast-close';
    fechar.setAttribute('aria-label', 'Fechar aviso');
    fechar.innerHTML = '<i data-lucide="x"></i>';
    el.appendChild(icone); el.appendChild(corpo); el.appendChild(fechar);
    area.appendChild(el);
    icones(el);
    var timer;
    function sair() {
      clearTimeout(timer);
      el.classList.add('is-leaving');
      setTimeout(function () { el.remove(); }, 220);
    }
    function agendar() { timer = setTimeout(sair, opcoes.duracao || (tipo === 'erro' ? 9000 : 5500)); }
    fechar.addEventListener('click', sair);
    el.addEventListener('mouseenter', function () { clearTimeout(timer); });
    el.addEventListener('mouseleave', agendar);
    agendar();
    return el;
  }

  /* ---------------------------------------------------------------- carregamento */
  var progresso;
  function iniciarProgresso() {
    if (!progresso) {
      progresso = document.createElement('div');
      progresso.id = 'fx-nav-progress';
      document.body.appendChild(progresso);
    }
    progresso.classList.remove('is-active');
    void progresso.offsetWidth;
    progresso.classList.add('is-active');
  }
  function pararCarregamento() {
    if (progresso) progresso.classList.remove('is-active');
    document.querySelectorAll('.is-loading').forEach(function (b) { b.classList.remove('is-loading'); });
  }
  // Ao enviar um formulário: barra no topo + spinner no botão (sem desabilitar: o valor do botão segue no envio).
  document.addEventListener('submit', function (e) {
    if (e.defaultPrevented) return;
    var form = e.target;
    if (form.target && form.target !== '_self') return;
    var botao = e.submitter;
    if (botao && botao.matches('button') && !botao.hasAttribute('data-sem-carregamento') && botao.offsetWidth > 40) {
      botao.classList.add('is-loading');
    }
    iniciarProgresso();
    setTimeout(pararCarregamento, 15000); // downloads (exportações) não trocam de página
  });
  document.addEventListener('click', function (e) {
    var link = e.target.closest('a[href]');
    if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
    var href = link.getAttribute('href');
    if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0 || link.target === '_blank' || link.hasAttribute('download')) return;
    if (link.origin && link.origin !== location.origin) return;
    if (/\.(xlsx|csv|pdf|zip)(\?|$)/i.test(href) || /exportar|download|modelo/i.test(href)) return;
    iniciarProgresso();
  });
  window.addEventListener('pageshow', pararCarregamento);

  /* ---------------------------------------------------------------- tabelas: busca + paginação */
  var PAGINA_PADRAO = 25;
  function textoBusca(linha) { return (linha.innerText || linha.textContent || '').toLowerCase(); }
  function linhaVazia(linha, tabela) {
    var celulas = linha.children || [];
    if (celulas.length !== 1) return false;
    var colunas = tabela.querySelectorAll('thead th').length;
    var texto = (celulas[0].innerText || celulas[0].textContent || '').trim().toLowerCase();
    return celulas[0].colSpan >= Math.max(colunas, 1) && /nenhum|nenhuma|sem registro|sem resultado/.test(texto);
  }
  function melhorarTabela(tabela) {
    if (tabela.dataset.tableEnhanced === '1' || tabela.dataset.noTableTools === '1') return;
    var corpo = tabela.tBodies && tabela.tBodies[0];
    if (!corpo) return;
    var linhas = Array.prototype.filter.call(corpo.querySelectorAll('tr'), function (l) { return !linhaVazia(l, tabela); });
    if (!linhas.length) return;
    tabela.dataset.tableEnhanced = '1';
    linhas.forEach(function (l) { l.dataset.searchText = textoBusca(l); });
    var estado = { busca: '', pagina: 1, tamanho: PAGINA_PADRAO };
    var ancora = tabela.parentElement && tabela.parentElement.classList.contains('overflow-x-auto') ? tabela.parentElement : tabela;

    var ferramentas = document.createElement('div');
    ferramentas.className = 'table-tools';
    ferramentas.innerHTML =
      '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">' +
      '<label class="table-search"><i data-lucide="search"></i><input type="search" aria-label="Pesquisar na tabela" placeholder="Pesquisar na tabela..."></label>' +
      '<select aria-label="Registros por página"><option value="10">10 por página</option><option value="25" selected>25 por página</option>' +
      '<option value="50">50 por página</option><option value="100">100 por página</option><option value="0">Todos</option></select></div>' +
      '<span class="table-count"></span>';
    var paginador = document.createElement('div');
    paginador.className = 'table-pager';
    paginador.innerHTML =
      '<span class="table-page-info"></span><div style="display:flex;align-items:center;gap:6px;">' +
      '<button type="button" data-page-action="first" aria-label="Primeira página"><i data-lucide="chevrons-left"></i></button>' +
      '<button type="button" data-page-action="prev"><i data-lucide="chevron-left"></i> Anterior</button>' +
      '<span class="table-page-num"></span>' +
      '<button type="button" data-page-action="next">Próxima <i data-lucide="chevron-right"></i></button>' +
      '<button type="button" data-page-action="last" aria-label="Última página"><i data-lucide="chevrons-right"></i></button></div>';
    ancora.parentNode.insertBefore(ferramentas, ancora);
    ancora.parentNode.insertBefore(paginador, ancora.nextSibling);
    icones(ferramentas); icones(paginador);

    var vazia = document.createElement('tr');
    vazia.className = 'table-empty-filter';
    var celula = document.createElement('td');
    celula.colSpan = Math.max(1, tabela.querySelectorAll('thead th').length);
    celula.className = 'px-4 py-8 text-center text-gray-400';
    celula.textContent = 'Nenhum resultado encontrado.';
    vazia.appendChild(celula);
    corpo.appendChild(vazia);

    var campo = ferramentas.querySelector('input');
    var seletor = ferramentas.querySelector('select');
    var contador = ferramentas.querySelector('.table-count');
    var info = paginador.querySelector('.table-page-info');
    var numero = paginador.querySelector('.table-page-num');
    var botoes = paginador.querySelectorAll('button[data-page-action]');

    function filtradas() {
      return estado.busca ? linhas.filter(function (l) { return l.dataset.searchText.indexOf(estado.busca) !== -1; }) : linhas;
    }
    function desenhar() {
      var lista = filtradas();
      var total = lista.length;
      var tamanho = estado.tamanho || Math.max(total, 1);
      var paginas = Math.max(1, Math.ceil(total / tamanho));
      estado.pagina = Math.min(Math.max(estado.pagina, 1), paginas);
      var inicio = estado.tamanho ? (estado.pagina - 1) * tamanho : 0;
      var fim = estado.tamanho ? inicio + tamanho : total;
      var visiveis = new Set(lista.slice(inicio, fim));
      linhas.forEach(function (l) { l.style.display = visiveis.has(l) ? '' : 'none'; });
      vazia.style.display = total === 0 ? '' : 'none';
      contador.textContent = total + ' registro(s)';
      info.textContent = total ? 'Mostrando ' + (inicio + 1) + '–' + (estado.tamanho ? Math.min(fim, total) : total) + ' de ' + total : 'Nenhum registro';
      numero.textContent = estado.pagina + ' / ' + paginas;
      botoes.forEach(function (b) {
        var acao = b.dataset.pageAction;
        b.disabled = total === 0 || !estado.tamanho ||
          ((acao === 'first' || acao === 'prev') && estado.pagina <= 1) ||
          ((acao === 'next' || acao === 'last') && estado.pagina >= paginas);
      });
      paginador.style.display = total > (estado.tamanho || total) ? '' : 'none';
    }
    campo.addEventListener('input', function () { estado.busca = campo.value.trim().toLowerCase(); estado.pagina = 1; desenhar(); });
    seletor.addEventListener('change', function () { estado.tamanho = parseInt(seletor.value, 10) || 0; estado.pagina = 1; desenhar(); });
    botoes.forEach(function (b) {
      b.addEventListener('click', function () {
        var tamanho = estado.tamanho || Math.max(filtradas().length, 1);
        var paginas = Math.max(1, Math.ceil(filtradas().length / tamanho));
        var acao = b.dataset.pageAction;
        if (acao === 'first') estado.pagina = 1;
        if (acao === 'prev') estado.pagina -= 1;
        if (acao === 'next') estado.pagina += 1;
        if (acao === 'last') estado.pagina = paginas;
        desenhar();
      });
    });
    desenhar();
  }
  function melhorarTabelas(escopo) { (escopo || document).querySelectorAll('table').forEach(melhorarTabela); }

  /* ---------------------------------------------------------------- formatação animada de números */
  function animarNumeros(escopo) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    (escopo || document).querySelectorAll('[data-count-up]').forEach(function (el) {
      var alvo = parseFloat(el.dataset.countUp);
      if (!isFinite(alvo)) return;
      var moeda = el.dataset.countFormat === 'brl';
      var fmt = moeda
        ? new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        : new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
      var final = el.textContent;
      var t0 = performance.now();
      var dur = 700;
      function passo(t) {
        var p = Math.min(1, (t - t0) / dur);
        var e = 1 - Math.pow(1 - p, 3);
        el.textContent = (el.dataset.countPrefix || '') + fmt.format(alvo * e);
        if (p < 1) requestAnimationFrame(passo); else el.textContent = final;
      }
      requestAnimationFrame(passo);
    });
  }

  /* ---------------------------------------------------------------- inicialização */
  function iniciar() {
    aplicarTema(root.classList.contains('dark'), false);
    iniciarMenu();
    icones();
    melhorarTabelas();
    animarNumeros();
    document.querySelectorAll('[data-flash]').forEach(function (el) {
      toast(el.dataset.flash, el.dataset.flashTipo || 'info');
      el.remove();
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar); else iniciar();
  document.addEventListener('htmx:afterSwap', function (e) { icones(e.target); melhorarTabelas(e.target); });

  window.FLIC = { toast: toast, icones: icones, aplicarTema: aplicarTema };
})();
