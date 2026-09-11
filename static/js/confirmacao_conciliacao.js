// A confirmação só é enviada depois da decisão explícita do usuário.
document.addEventListener('DOMContentLoaded', () => {
  const dialog = document.createElement('dialog');
  dialog.className = 'confirmacao-banco';
  dialog.setAttribute('aria-labelledby', 'confirmacao-banco-titulo');
  dialog.setAttribute('aria-describedby', 'confirmacao-banco-descricao');
  dialog.innerHTML = `
    <div class="confirmacao-banco-conteudo">
      <div class="confirmacao-banco-icone" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10a9 9 0 1 1 2.6 8.4M3 4v6h6"/><path d="M12 8v4l3 2"/></svg>
      </div>
      <p class="confirmacao-banco-etiqueta">CONCILIAÇÃO BANCÁRIA</p>
      <h2 id="confirmacao-banco-titulo">Desconciliar este movimento?</h2>
      <p id="confirmacao-banco-descricao">O vínculo com o lançamento será desfeito e os saldos serão atualizados.</p>
      <div class="confirmacao-banco-nota">O movimento permanece no extrato e poderá ser conciliado novamente.</div>
    </div>
    <div class="confirmacao-banco-acoes">
      <button type="button" class="confirmacao-banco-cancelar" autofocus>Manter conciliado</button>
      <button type="button" class="confirmacao-banco-confirmar">Sim, desconciliar</button>
    </div>`;
  document.body.appendChild(dialog);
  let pending = null;
  const approved = new WeakSet();
  dialog.querySelector('.confirmacao-banco-cancelar').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => { pending = null; });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  dialog.querySelector('.confirmacao-banco-confirmar').addEventListener('click', () => {
    if (!pending) return;
    const { form, submitter } = pending;
    pending = null;
    approved.add(form);
    dialog.close();
    try {
      if (submitter) form.requestSubmit(submitter);
      else form.requestSubmit();
    } finally {
      approved.delete(form);
    }
  });
  document.querySelectorAll('form[method="post"]').forEach(form => {
    const path = new URL(form.action, location.href).pathname;
    if (path.startsWith('/conciliacao/banco/') && path.endsWith('/desvincular')) {
      form.onsubmit = event => {
        if (approved.has(form)) return true;
        event.preventDefault();
        pending = { form, submitter: event.submitter };
        dialog.showModal();
        return false;
      };
      return;
    }
    if (path.startsWith('/conciliacao/') && /\/(desvincular|cancelar|desfazer)$/.test(path)) {
      const previous = form.onsubmit;
      if (!previous) form.onsubmit = () => window.confirm('Tem certeza que deseja desfazer esta conciliação? Os vínculos e saldos serão atualizados.');
      return;
    }
    if (!/^\/(lancamentos|contas-pagar)\/\d+\/(editar|excluir|desconciliar)$/.test(path)
        && path !== '/lancamentos/lote/excluir' && path !== '/contas-pagar/lote/aplicar') return;
    const previous = form.onsubmit;
    form.onsubmit = event => {
      if (previous && previous.call(form, event) === false) return false;
      const message = 'Tem certeza? Se houver conciliação ou pagamento, eles serão desfeitos antes desta ação. Os registros mantidos voltarão a ficar pendentes. O extrato será preservado para nova conciliação. Para recebimentos de cartão, o lote será reaberto e precisará ser fechado e conciliado novamente. Deseja continuar?';
      if (!window.confirm(message)) return false;
      let input = form.querySelector('[name="confirmar_conciliacao"]');
      if (!input) {
        input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'confirmar_conciliacao';
        form.appendChild(input);
      }
      input.value = 'true';
      return true;
    };
  });
});
