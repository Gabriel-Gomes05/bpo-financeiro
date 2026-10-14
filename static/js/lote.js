// Seleção em lote: por checkbox (itens exibidos) ou "todos do filtro", em que o servidor
// reaplica os filtros da tela e exclui tudo de uma vez, sem enviar a lista de IDs.
let loteTodosDoFiltro = false;

function totalDoFiltro() {
  return Number(document.getElementById('form-lote')?.dataset.totalFiltro || 0);
}
function atualizarSelecaoLote() {
  const itens = [...document.querySelectorAll('.selecao-lote:not(:disabled)')];
  const total = itens.filter(c => c.checked).length;
  const todosMarcados = itens.length > 0 && total === itens.length;
  const totalFiltro = totalDoFiltro();
  if (!todosMarcados) loteTodosDoFiltro = false;
  // Quando a tela já mostra tudo o que o filtro abrange, marcar todos equivale a "todos do filtro".
  if (todosMarcados && totalFiltro === itens.length) loteTodosDoFiltro = true;

  const todos = document.getElementById('selecionar-todos');
  todos.checked = todosMarcados;
  todos.indeterminate = total > 0 && !todosMarcados;
  document.getElementById('total-selecionados').textContent =
    `${(loteTodosDoFiltro ? totalFiltro : total).toLocaleString('pt-BR')} selecionado(s)`;

  const faixa = document.getElementById('lote-todos');
  if (!faixa) return;
  faixa.hidden = !todosMarcados;
  if (!todosMarcados) return;
  const n = totalFiltro.toLocaleString('pt-BR');
  if (loteTodosDoFiltro && totalFiltro > itens.length) {
    faixa.innerHTML = `Todos os <strong>${n}</strong> registros do filtro estão selecionados. <button type="button" class="font-semibold underline" onclick="selecionarTodosDoFiltro(false)">Selecionar só os ${itens.length} exibidos</button>`;
  } else if (loteTodosDoFiltro) {
    faixa.innerHTML = `Todos os <strong>${n}</strong> registros do filtro estão selecionados.`;
  } else {
    faixa.innerHTML = `Os ${itens.length} itens exibidos estão selecionados. <button type="button" class="font-semibold underline" onclick="selecionarTodosDoFiltro(true)">Selecionar todos os ${n} registros do filtro</button>`;
  }
}
function selecionarTodosDoFiltro(ativo) {
  loteTodosDoFiltro = ativo;
  atualizarSelecaoLote();
}
function campoOculto(form, nome, valor) {
  let input = form.querySelector(`input[type="hidden"][name="${nome}"]`);
  if (!input) {
    input = document.createElement('input');
    input.type = 'hidden';
    input.name = nome;
    form.appendChild(input);
  }
  input.value = valor;
}
function confirmarLote(event) {
  const form = event.target;
  const marcados = [...document.querySelectorAll('.selecao-lote:not(:disabled):checked')];
  if (!marcados.length) { alert('Selecione ao menos um registro.'); return false; }
  const quantidade = (loteTodosDoFiltro ? totalDoFiltro() : marcados.length).toLocaleString('pt-BR');
  const alvo = loteTodosDoFiltro ? `TODOS os ${quantidade} registro(s) do filtro atual` : `${quantidade} registro(s) selecionado(s)`;
  const excluir = event.submitter?.value === 'excluir' || form.action.endsWith('/excluir');
  const aviso = 'Registros com conciliação ou pagamento serão desconciliados antes (o extrato é preservado; lotes de cartão serão reabertos).';
  const pergunta = excluir
    ? `Excluir ${alvo}? ${aviso} Esta ação não pode ser desfeita.`
    : `Alterar ${alvo}? ${aviso} Confira os campos escolhidos antes de autorizar.`;
  if (!confirm(pergunta)) return false;
  // Nunca envia um campo por item: seleções grandes estouram o limite de campos do formulário.
  marcados.forEach(c => c.removeAttribute('name'));
  campoOculto(form, 'modo', loteTodosDoFiltro ? 'filtro' : 'ids');
  campoOculto(form, 'ids', loteTodosDoFiltro ? '' : marcados.map(c => c.value).join(','));
  campoOculto(form, 'confirmar_conciliacao', 'true');
  return true;
}
// Ao voltar pelo histórico, restaura os checkboxes para um novo envio.
window.addEventListener('pageshow', () => {
  document.querySelectorAll('.selecao-lote').forEach(c => c.setAttribute('name', 'ids'));
  document.querySelectorAll('#form-lote input[type="hidden"][name="ids"]').forEach(i => i.remove());
  if (document.getElementById('selecionar-todos')) atualizarSelecaoLote();
});
