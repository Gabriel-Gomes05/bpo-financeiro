function atualizarSelecaoLote() {
  const itens = [...document.querySelectorAll('.selecao-lote:not(:disabled)')];
  const total = itens.filter(c => c.checked).length;
  document.getElementById('total-selecionados').textContent = `${total} selecionado(s)`;
  const todos = document.getElementById('selecionar-todos');
  todos.checked = itens.length > 0 && total === itens.length;
  todos.indeterminate = total > 0 && total < itens.length;
}
function confirmarLote(event) {
  const total = document.querySelectorAll('.selecao-lote:not(:disabled):checked').length;
  if (!total) { alert('Selecione ao menos um registro.'); return false; }
  const excluir = event.submitter?.value === 'excluir' || event.target.action.endsWith('/excluir');
  return confirm(`${excluir ? 'Excluir' : 'Alterar'} ${total} registro(s) selecionado(s)? ${excluir ? 'Esta ação não pode ser desfeita.' : 'Confira os campos escolhidos antes de autorizar.'}`);
}
