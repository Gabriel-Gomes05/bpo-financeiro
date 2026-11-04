"""Catálogo de códigos de erro do FLIC.

Todo erro mostrado ao usuário carrega um código no formato FLIC-<ÁREA>-<NNN>.
O catálogo abaixo é a fonte única: a página /ajuda/erros e o documento
docs/CODIGOS_DE_ERRO.md são gerados a partir dele (scripts/gerar_catalogo_erros.py).

Como usar:
    raise erro("FLIC-PAG-010")                     # página/JSON de erro com o código
    raise erro("FLIC-REC-001", "Valor inválido.")  # mensagem específica, mesmo código
    mensagem = com_codigo("FLIC-TAR-005", "...")   # texto para flash/avisos: "[FLIC-TAR-005] ..."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException


@dataclass(frozen=True)
class DefinicaoErro:
    codigo: str
    status: int
    titulo: str
    mensagem: str
    causa: str
    solucao: str
    slug: Optional[str] = None  # valor de ?erro=<slug> usado por telas de cadastro


AREAS = {
    "GER": "Geral",
    "AUT": "Acesso e autenticação",
    "REC": "Contas a receber",
    "PAG": "Contas a pagar",
    "CON": "Conciliação e contas bancárias",
    "IMP": "Importações",
    "TAR": "Tarefas",
    "FEC": "Fechamento de período",
    "CAD": "Cadastros",
}


def _e(codigo, status, titulo, mensagem, causa, solucao, slug=None) -> DefinicaoErro:
    return DefinicaoErro(codigo, status, titulo, mensagem, causa, solucao, slug)


_DEFINICOES = [
    # ---------------------------------------------------------------- Geral
    _e("FLIC-GER-001", 400, "Seleção inválida", "Seleção inválida.",
       "Os itens enviados na seleção em lote não são identificadores válidos.",
       "Recarregue a página e selecione os itens novamente."),
    _e("FLIC-GER-002", 400, "Filtro inválido", "Filtro inválido.",
       "Os filtros enviados com a ação em lote estão corrompidos ou incompletos.",
       "Recarregue a listagem, aplique os filtros de novo e repita a ação."),
    _e("FLIC-GER-400", 400, "Requisição inválida", "A requisição não pôde ser processada.",
       "A tela enviou dados que o sistema não aceita.",
       "Recarregue a página e tente novamente. Se repetir, informe o código e o identificador ao suporte."),
    _e("FLIC-GER-403", 403, "Acesso negado", "Você não tem permissão para esta ação.",
       "O perfil do usuário não permite a operação solicitada.",
       "Peça a um coordenador para revisar o seu perfil de acesso."),
    _e("FLIC-GER-404", 404, "Página ou registro não encontrado", "O endereço ou registro solicitado não existe.",
       "O link está errado, o registro foi excluído ou pertence a outra empresa.",
       "Volte ao início e navegue pelo menu. Confira se a empresa selecionada é a correta."),
    _e("FLIC-GER-409", 409, "Conflito", "A ação conflita com o estado atual do registro.",
       "O registro foi alterado por outra ação ou está bloqueado.",
       "Recarregue a página para ver o estado atual e repita a ação se ainda fizer sentido."),
    _e("FLIC-GER-422", 422, "Dados do formulário inválidos", "Confira os dados informados e tente novamente.",
       "Algum campo obrigatório ficou vazio ou foi enviado em formato inválido (data, número etc.).",
       "Revise os campos do formulário. Datas no formato DD/MM/AAAA e valores numéricos."),
    _e("FLIC-GER-429", 429, "Muitas requisições", "Muitas requisições em pouco tempo.",
       "O limite de requisições por minuto foi atingido.",
       "Aguarde alguns instantes e tente novamente."),
    _e("FLIC-GER-500", 500, "Erro interno", "Não foi possível concluir a solicitação.",
       "Falha inesperada no servidor. O erro foi registrado no log com o identificador da requisição.",
       "Tente novamente. Se repetir, envie o código e o identificador ao suporte."),
    _e("FLIC-GER-503", 503, "Serviço indisponível", "O serviço está temporariamente indisponível.",
       "Banco de dados, Redis ou outro serviço interno não respondeu.",
       "Aguarde alguns minutos. Se persistir, o suporte deve verificar os containers (docker compose ps)."),

    # ---------------------------------------------------------------- Acesso
    _e("FLIC-AUT-001", 403, "Perfil sem acesso", "Acesso não permitido para este perfil.",
       "O perfil do usuário não tem permissão para a área acessada.",
       "Use um usuário com o perfil adequado ou peça a liberação a um coordenador."),
    _e("FLIC-AUT-002", 403, "Perfil somente leitura", "Perfil somente leitura.",
       "O perfil Médico pode consultar, mas não incluir, editar ou excluir registros.",
       "Peça a um usuário operacional para fazer a alteração."),
    _e("FLIC-AUT-003", 503, "Autenticação indisponível", "Autenticação temporariamente indisponível.",
       "O Redis, usado para sessões e limite de tentativas de login, não respondeu.",
       "Aguarde e tente de novo. Suporte: verificar o container redis."),
    _e("FLIC-AUT-004", 404, "Empresa indisponível", "Cliente indisponível.",
       "A empresa não existe, está inativa ou não está atribuída ao usuário.",
       "Volte ao Painel geral e entre em uma empresa à qual você tem acesso."),
    _e("FLIC-AUT-005", 400, "Nenhuma empresa selecionada", "Selecione uma empresa no painel geral.",
       "A tela depende de uma empresa ativa e nenhuma está selecionada.",
       "Vá ao Painel geral, escolha a empresa e repita a ação."),
    _e("FLIC-AUT-006", 403, "Sem acesso ao registro", "Você não tem acesso a este registro.",
       "O registro pertence a uma empresa ou usuário fora do seu acesso.",
       "Confira a empresa selecionada ou peça acesso a um coordenador.", slug="sem_acesso"),
    _e("FLIC-AUT-007", 400, "Login não autorizado", "Não foi possível entrar com as credenciais informadas.",
       "E-mail ou senha incorretos, usuário inativo ou limite de tentativas de login excedido. "
       "Por segurança, a tela não informa qual dos casos ocorreu.",
       "Confira e-mail e senha. Após várias tentativas, aguarde alguns minutos antes de tentar de novo."),
    _e("FLIC-AUT-008", 403, "Área não liberada para secretária", "Esta área não está liberada para o perfil Secretária.",
       "O perfil Secretária acessa somente Contas a Receber e Lançamentos do cliente vinculado. "
       "A tentativa foi registrada no histórico de alterações.",
       "Use o menu lateral. Se precisar de outra área, peça a um administrador ou editor."),
    _e("FLIC-AUT-009", 403, "Exclusão não permitida", "O perfil Secretária não pode excluir registros.",
       "Secretárias podem incluir e editar lançamentos, mas nunca excluir. A tentativa foi registrada no histórico.",
       "Peça a um administrador ou editor para fazer a exclusão."),
    _e("FLIC-AUT-010", 403, "Secretária sem cliente vinculado", "Seu usuário não está vinculado a um cliente ativo.",
       "Toda secretária precisa de um cliente vinculado. O vínculo está vazio ou o cliente foi inativado.",
       "Peça a um administrador ou editor para vincular seu usuário a um cliente em Cadastros → Secretárias."),

    # ---------------------------------------------------------------- Contas a receber
    _e("FLIC-REC-001", 400, "Campo do lançamento inválido", "Campo inválido.",
       "Data ou valor do lançamento em formato inválido.",
       "Informe datas válidas e valores numéricos com até duas casas decimais."),
    _e("FLIC-REC-002", 400, "Forma de pagamento inválida", "Forma de pagamento inválida.",
       "A forma de pagamento enviada não existe no sistema.",
       "Escolha uma das formas da lista."),
    _e("FLIC-REC-003", 400, "Pagador do Pix obrigatório", "Informe o nome do pagador do Pix.",
       "Recebimentos em Pix exigem o nome do pagador para a conciliação bancária.",
       "Preencha o campo Nome do pagador do Pix."),
    _e("FLIC-REC-004", 400, "Condição de pagamento inválida", "Condição de pagamento inválida.",
       "A condição de pagamento enviada não existe no sistema.",
       "Escolha uma das condições da lista."),
    _e("FLIC-REC-005", 400, "Parcela inválida", "Informe uma parcela entre 1 e o total de parcelas (até 48).",
       "Número da parcela maior que o total, ou total acima de 48.",
       "Corrija a parcela e o total de parcelas."),
    _e("FLIC-REC-006", 400, "Centro de custo inválido", "Centro de custo inválido.",
       "O centro de custo não existe ou pertence a outra empresa.",
       "Escolha um centro de custo ativo da empresa atual."),
    _e("FLIC-REC-007", 400, "Plano de receita inválido", "Plano de receita inválido para este cliente.",
       "O plano de contas escolhido não é de receita ou não está disponível para a empresa.",
       "Escolha um plano de receita ativo da lista."),
    _e("FLIC-REC-008", 400, "Centro do rateio inválido", "Centro de custo do rateio inválido.",
       "Um dos centros de custo do rateio não pertence à empresa.",
       "Revise os centros de custo do rateio."),
    _e("FLIC-REC-009", 400, "Percentual do rateio inválido", "O percentual do rateio deve ser maior que zero.",
       "Uma linha do rateio foi enviada com percentual zero ou negativo.",
       "Informe percentuais maiores que zero ou remova a linha."),
    _e("FLIC-REC-010", 400, "Rateio não fecha 100%", "Rateio inválido: use centros diferentes e feche 100%.",
       "Os percentuais não somam 100% ou o mesmo centro foi usado duas vezes.",
       "Ajuste os percentuais para somarem exatamente 100% com centros diferentes."),
    _e("FLIC-REC-011", 400, "Nenhum lançamento selecionado", "Selecione ao menos um lançamento.",
       "A ação em lote foi enviada sem itens selecionados.",
       "Marque os lançamentos desejados e repita a ação."),
    _e("FLIC-REC-012", 404, "Seleção indisponível", "Seleção contém lançamentos indisponíveis.",
       "Algum lançamento selecionado foi excluído ou não pertence às suas empresas.",
       "Recarregue a listagem e selecione novamente."),
    _e("FLIC-REC-013", 404, "Lançamento indisponível", "Lançamento indisponível.",
       "O lançamento foi excluído ou pertence a uma empresa fora do seu acesso.",
       "Volte à listagem de lançamentos e recarregue a página."),
    _e("FLIC-REC-014", 409, "Lista mudou durante a ação", "A lista mudou desde a seleção. Confira e selecione novamente.",
       "Entre a seleção \"todos do filtro\" e a confirmação, lançamentos foram incluídos ou removidos.",
       "Recarregue a listagem, confira a quantidade e repita a ação."),
    _e("FLIC-REC-015", 403, "Lançamento conciliado", "Lançamentos já conciliados não podem ser editados pela secretária.",
       "Editar um lançamento conciliado desfaz a conciliação bancária, o que é restrito à equipe do BPO.",
       "Peça a um administrador ou editor para fazer a alteração."),

    # ---------------------------------------------------------------- Contas a pagar
    _e("FLIC-PAG-001", 400, "Opção de edição inválida", "Opção de edição inválida.",
       "O escopo da edição (só este / este e os próximos) é inválido.",
       "Recarregue a tela de edição e escolha uma opção da lista."),
    _e("FLIC-PAG-002", 400, "Valor inválido", "Informe um valor válido com até duas casas decimais.",
       "Valor negativo, vazio, muito alto ou com mais de duas casas decimais.",
       "Informe o valor em reais, com até duas casas decimais."),
    _e("FLIC-PAG-003", 400, "Rateio inválido", "Rateio inválido: use centros diferentes e feche 100%.",
       "Os percentuais do rateio não somam 100% ou repetem o mesmo centro de custo.",
       "Ajuste o rateio para fechar exatamente 100% com centros diferentes."),
    _e("FLIC-PAG-004", 409, "Recorrência inconsistente", "Recorrência inconsistente entre clientes.",
       "Uma série recorrente aponta para contas de outra empresa (dado inconsistente no banco).",
       "Não repita a ação. Envie o código ao suporte para correção dos dados."),
    _e("FLIC-PAG-005", 400, "Opção de exclusão inválida", "Opção de exclusão inválida.",
       "O escopo da exclusão (só esta / série inteira) é inválido.",
       "Recarregue a listagem e use os botões de exclusão."),
    _e("FLIC-PAG-006", 400, "Intervalo de recorrência inválido", "Intervalo de recorrência inválido.",
       "A frequência enviada não é semanal, quinzenal, mensal ou personalizada.",
       "Escolha uma frequência da lista."),
    _e("FLIC-PAG-007", 400, "Recorrência mal configurada", "Revise a quantidade e os dias da recorrência.",
       "Quantidade fora de 1 a 60, ou intervalo personalizado sem dias válidos.",
       "Informe a quantidade de ocorrências e, se personalizada, a cada quantos dias."),
    _e("FLIC-PAG-008", 400, "Ação em lote inválida", "Seleção ou ação inválida.",
       "Ação em lote desconhecida ou sem contas selecionadas.",
       "Selecione as contas e escolha Editar ou Excluir."),
    _e("FLIC-PAG-009", 404, "Seleção indisponível", "Seleção contém contas indisponíveis.",
       "Alguma conta selecionada foi excluída ou pertence a uma empresa fora do seu acesso.",
       "Recarregue a listagem e selecione novamente."),
    _e("FLIC-PAG-010", 404, "Conta a pagar indisponível", "Conta indisponível.",
       "A conta foi excluída ou pertence a uma empresa fora do seu acesso.",
       "Volte à listagem de contas a pagar e recarregue a página."),
    _e("FLIC-PAG-011", 404, "Documento não encontrado", "Documento anexo não encontrado.",
       "A conta não tem anexo ou o arquivo não está mais no servidor.",
       "Anexe o documento novamente pela edição da conta."),
    _e("FLIC-PAG-012", 409, "Conta paga ou conciliada", "Lançamento com pagamento ou conciliação não pode ser excluído.",
       "Contas pagas, com pagamento parcial ou conciliadas são protegidas contra exclusão.",
       "Desfaça a conciliação/pagamento antes de excluir, se for realmente necessário."),
    _e("FLIC-PAG-013", 409, "Mudança de status não permitida", "Transição de status não permitida.",
       "O status atual não pode ir para o status escolhido (ex.: de pago para pendente sem desconciliar).",
       "Siga o fluxo: pendente → aguardando aprovação → agendado → pago."),
    _e("FLIC-PAG-014", 409, "Lista mudou durante a ação", "A lista mudou desde a seleção. Confira e selecione novamente.",
       "Entre a seleção \"todos do filtro\" e a confirmação, contas foram incluídas ou removidas.",
       "Recarregue a listagem, confira a quantidade e repita a ação."),
    _e("FLIC-PAG-015", 400, "Nenhum campo para editar", "Escolha ao menos um campo para editar.",
       "A edição em lote foi enviada sem plano de contas, centro de custo ou status.",
       "Preencha ao menos um campo da edição em lote."),

    _e("FLIC-PAG-016", 400, "Plano de contas inválido no lote", "Categoria inválida para um dos clientes selecionados.",
       "O plano de contas escolhido na edição em lote não está disponível para todas as empresas das contas selecionadas.",
       "Selecione contas de uma empresa por vez ou use um plano de contas comum a todas."),
    _e("FLIC-PAG-018", 400, "Conta bancária inválida", "Escolha uma conta bancária ativa do cliente.",
       "A conta escolhida não existe, foi desativada ou é de outro cliente.",
       "Selecione uma das contas listadas para o cliente ou deixe \"Não informada\"."),
    _e("FLIC-PAG-017", 400, "Centro de custo inválido no lote", "Centro de custo inválido para um dos clientes selecionados.",
       "O centro de custo pertence a uma empresa diferente da de alguma conta selecionada.",
       "Selecione contas de uma empresa só ao aplicar centro de custo em lote."),

    # ---------------------------------------------------------------- Conciliação / bancos
    _e("FLIC-CON-001", 400, "Regra bancária incompleta", "Informe o tipo, nome e texto da regra.",
       "Regra automática sem tipo, nome ou texto de busca no extrato.",
       "Preencha todos os campos da regra."),
    _e("FLIC-CON-002", 400, "Contas de origem e destino iguais", "Informe contas de origem e destino diferentes.",
       "Transferência ou regra com a mesma conta na origem e no destino.",
       "Escolha contas diferentes para origem e destino."),
    _e("FLIC-CON-003", 400, "Plano de contas incompatível", "Selecione um plano de contas compatível.",
       "O plano escolhido não combina com o tipo de regra (receita × despesa) ou não está ativo.",
       "Escolha um plano de contas ativo do tipo correto."),
    _e("FLIC-CON-004", 400, "Conta bancária incompleta", "Preencha os campos obrigatórios da conta.",
       "Conta Corrente exige banco, agência e número; Investimentos exige banco, nome e descrição; "
       "Cartão de Crédito exige só o nome do cartão.",
       "Preencha os campos obrigatórios do tipo de conta escolhido."),
    _e("FLIC-CON-018", 500, "Falha ao aplicar regra", "A regra foi salva, mas não foi possível aplicá-la aos lançamentos existentes.",
       "Ocorreu um erro durante a aplicação retroativa. O que já tinha sido conciliado em lotes anteriores foi mantido; "
       "nenhum lançamento ficou pela metade.",
       "Tente aplicar de novo (a execução é segura para repetir). Se persistir, informe o código e o horário ao suporte.",
       slug="regra_retroativa_falhou"),
    _e("FLIC-CON-019", 404, "Regra indisponível", "Regra não encontrada ou inativa para este cliente.",
       "A regra foi removida ou pertence a outra empresa.",
       "Recarregue a conciliação bancária e escolha uma regra da lista."),
    _e("FLIC-CON-020", 400, "Conciliação agrupada recusada", "A soma dos itens selecionados não bate com o valor do extrato.",
       "Para conciliar vários lançamentos com um único movimento do extrato, a soma precisa ser exatamente igual ao valor "
       "do movimento, e nenhum item pode estar conciliado.",
       "Marque os lançamentos até o contador mostrar \"valor confere\" e concilie novamente.", slug="agrupado_soma"),
    _e("FLIC-CON-017", 400, "Tipo de conta inválido", "Escolha o tipo da conta: Conta Corrente, Investimentos ou Cartão de Crédito.",
       "O cadastro foi enviado sem tipo de conta ou com um tipo desconhecido.",
       "Selecione um dos três tipos e preencha os campos que aparecerem."),
    _e("FLIC-CON-005", 400, "Saldo inválido", "Saldo inválido.",
       "O saldo informado não é um número válido.",
       "Informe o saldo em reais, por exemplo 1.234,56."),
    _e("FLIC-CON-006", 409, "Conta bancária duplicada", "Esta conta já está cadastrada para o cliente.",
       "Já existe uma conta com o mesmo banco e número para a empresa.",
       "Use a conta existente ou corrija os dados."),
    _e("FLIC-CON-007", 404, "Conta bancária indisponível", "Conta bancária indisponível para este cliente.",
       "A conta foi removida ou pertence a outra empresa.",
       "Recarregue a tela e escolha uma conta da empresa atual."),
    _e("FLIC-CON-008", 400, "Valor da transferência inválido", "Informe um valor positivo com até duas casas decimais.",
       "Valor da transferência zerado, negativo ou com mais de duas casas.",
       "Informe um valor positivo em reais."),
    _e("FLIC-CON-009", 400, "Transferência não identificada", "Identificação da transferência inválida.",
       "O identificador da transferência enviado pela tela é inválido.",
       "Recarregue a tela de conciliação e repita a ação."),
    _e("FLIC-CON-010", 409, "Confirmação necessária", "Tem certeza? Confirme a ação para desfazer a conciliação.",
       "A ação desfaz uma conciliação ou pagamento e exige confirmação explícita.",
       "Confirme na janela de aviso para prosseguir."),
    _e("FLIC-CON-011", 409, "Vínculo financeiro inconsistente", "Vínculo financeiro inconsistente entre clientes.",
       "O lançamento está ligado a movimentação de outra empresa (dado inconsistente no banco).",
       "Não repita a ação. Envie o código ao suporte para correção dos dados."),
    _e("FLIC-CON-012", 400, "Conta bancária não informada", "Selecione uma conta bancária ou informe banco e número da nova conta.",
       "A baixa foi enviada sem conta bancária de destino.",
       "Escolha uma conta existente ou cadastre uma nova."),
    _e("FLIC-CON-013", 400, "Pagamento parcial inválido", "O pagamento parcial deve ser maior que zero e não pode ultrapassar o saldo da despesa.",
       "Valor do pagamento parcial zerado ou acima do saldo em aberto.",
       "Informe um valor entre R$ 0,01 e o saldo da despesa."),
    _e("FLIC-CON-014", 400, "Rateio inválido", "Rateio inválido: use centros diferentes e feche exatamente 100%.",
       "Os percentuais do rateio não somam 100% ou repetem o mesmo centro.",
       "Ajuste o rateio para fechar exatamente 100%."),

    _e("FLIC-CON-015", 400, "Nenhuma venda para fechar o lote", "Nenhuma venda conciliada nesta data de pagamento para fechar o lote.",
       "O lote só agrupa vendas de cartão já conciliadas com um lançamento e ainda não agrupadas, na data (e bandeira) escolhida.",
       "Concilie as vendas da maquininha com os lançamentos antes de fechar o lote, e confira a data de pagamento e a bandeira."),
    _e("FLIC-CON-016", 500, "Falha ao fechar o lote", "Não foi possível fechar o lote de cartão.",
       "Erro inesperado ao agrupar as vendas do dia. Detalhes no log do servidor.",
       "Tente novamente. Se repetir, envie o código e o identificador ao suporte."),

    # ---------------------------------------------------------------- Importações (arquivo)
    _e("FLIC-IMP-001", 400, "Aba RECEITA ausente", "A planilha não contém a aba RECEITA esperada.",
       "O arquivo enviado na Planilha BPO não tem uma aba chamada RECEITA.",
       "Use o modelo da Planilha BPO e mantenha a aba RECEITA com o cabeçalho na linha 6."),
    _e("FLIC-IMP-002", 400, "Aba Visão Contas a Receber ausente", "A planilha não contém a aba Visão Contas a Receber esperada.",
       "O relatório enviado não tem a aba \"Visão Contas a Receber\".",
       "Exporte o relatório novamente da Conta Azul sem renomear a aba."),
    _e("FLIC-IMP-003", 400, "Relatório ilegível", "Não foi possível ler o relatório Excel enviado.",
       "O arquivo está corrompido, protegido por senha ou não é um Excel válido.",
       "Abra o arquivo no Excel, salve como .xlsx e envie de novo."),
    _e("FLIC-IMP-004", 400, "Relatório vazio", "O relatório está vazio.",
       "A aba do relatório não tem cabeçalho nem linhas.",
       "Confira se exportou o período correto."),
    _e("FLIC-IMP-005", 400, "Colunas de competência e valor ausentes", "O relatório não contém as colunas de competência e valor esperadas.",
       "Faltam as colunas \"Data de competência\" e/ou \"Valor original da parcela (R$)\".",
       "Exporte o relatório completo da Conta Azul ou use o modelo do sistema."),
    _e("FLIC-IMP-006", 400, "Colunas de data e valor ausentes", "Arquivo não contém colunas de data e valor reconhecíveis.",
       "A planilha não tem colunas de data e de valor com nomes reconhecidos.",
       "Use o modelo de importação e não renomeie os cabeçalhos."),
    _e("FLIC-IMP-007", 400, "Planilha de contas a pagar com linha inválida", "Nenhuma conta importada.",
       "Uma das linhas da planilha de contas a pagar tem dado inválido; nada é importado.",
       "Corrija a linha indicada na mensagem e envie o arquivo de novo."),
    _e("FLIC-IMP-008", 400, "Conta bancária não selecionada", "Selecione a conta bancária antes de importar CSV ou XLSX.",
       "Extratos em CSV/Excel não informam a conta; o sistema precisa saber em qual conta lançar.",
       "Escolha a conta bancária no seletor da conciliação bancária e importe de novo. Arquivos OFX não precisam."),
    _e("FLIC-IMP-009", 400, "OFX de outra conta", "O OFX pertence a outra conta cadastrada.",
       "O banco/número da conta dentro do OFX corresponde a outra conta já cadastrada para a empresa.",
       "Selecione a conta correta antes de importar, ou confira se baixou o extrato da conta certa."),
    _e("FLIC-IMP-010", 400, "Conta do OFX diferente da selecionada", "O número da conta do OFX difere da conta selecionada.",
       "O número da conta informado no arquivo OFX não é o da conta selecionada na tela.",
       "Selecione a conta correspondente ao extrato ou baixe o OFX da conta selecionada."),
    _e("FLIC-IMP-011", 400, "OFX sem transações", "Nenhuma transação encontrada no arquivo OFX.",
       "O arquivo OFX está vazio ou o período exportado não tem movimentações.",
       "Exporte o extrato de novo, conferindo o período."),
    # Avisos linha a linha da importação de contas a receber
    _e("FLIC-IMP-101", 400, "Linha ignorada: data", "Linha ignorada por data vazia ou inválida.",
       "A data do atendimento/competência está vazia ou não é uma data (use DD/MM/AAAA).",
       "Corrija a data na planilha e importe apenas essa linha novamente."),
    _e("FLIC-IMP-102", 400, "Linha ignorada: valor", "Linha ignorada por valor inválido.",
       "O valor está vazio ou não é número (ex.: texto, símbolo desconhecido).",
       "Informe o valor como 350,00 ou 1.234,56 e importe a linha novamente."),
    _e("FLIC-IMP-103", 400, "Linha ignorada: valor zero ou negativo", "Linha ignorada por valor zero ou negativo.",
       "Receitas precisam ter valor maior que zero.",
       "Corrija o valor. Estornos devem ser tratados fora da importação."),
    _e("FLIC-IMP-104", 400, "Forma de pagamento não reconhecida", "Forma de pagamento não reconhecida; ficou em branco.",
       "O texto da forma de pagamento não corresponde a nenhuma forma do sistema.",
       "Edite o lançamento e escolha a forma. Formas aceitas: pix, transferência, cartão de crédito/débito, dinheiro, boleto, cheque, débito automático."),
    _e("FLIC-IMP-105", 400, "Plano de contas não encontrado", "Plano de contas não encontrado; ficou sem plano.",
       "O código ou nome do plano não existe entre os planos de receita ativos da empresa.",
       "Edite o lançamento e escolha o plano, ou cadastre o plano antes de importar."),
    _e("FLIC-IMP-106", 400, "Campo opcional inválido", "Campo opcional inválido; ficou em branco.",
       "Data prevista, data do crédito, taxa, parcela ou valor líquido em formato inválido.",
       "Edite o lançamento e preencha o campo indicado."),
    _e("FLIC-IMP-107", 400, "Linhas já importadas ignoradas", "Linhas já importadas anteriormente foram ignoradas para não duplicar.",
       "O arquivo traz linhas iguais a registros que já estão no sistema (mesma data, valor e descrição/paciente), "
       "normalmente porque o mesmo arquivo foi importado de novo.",
       "Nada a fazer se o arquivo já tinha sido importado. Se for um registro novo idêntico a um antigo, inclua-o manualmente."),
    # Falhas inesperadas por tipo de importação (detalhes no log do servidor)
    _e("FLIC-IMP-901", 500, "Falha na importação de lançamentos", "Não foi possível processar o arquivo de lançamentos.",
       "Erro inesperado ao processar a planilha de lançamentos em lote.",
       "Confira se o arquivo segue o modelo. Se repetir, envie o código e o arquivo ao suporte."),
    _e("FLIC-IMP-902", 500, "Falha na importação da Planilha BPO", "Não foi possível processar a Planilha BPO.",
       "Erro inesperado ao processar a aba RECEITA.",
       "Confira se o arquivo segue o modelo. Se repetir, envie o código e o arquivo ao suporte."),
    _e("FLIC-IMP-903", 500, "Falha na importação da Visão Contas a Receber", "Não foi possível processar o relatório Visão Contas a Receber.",
       "Erro inesperado ao processar o relatório.",
       "Exporte o relatório de novo. Se repetir, envie o código e o arquivo ao suporte."),
    _e("FLIC-IMP-904", 500, "Falha na importação de contas a pagar", "Não foi possível processar a planilha de contas a pagar.",
       "Erro inesperado ao processar a planilha de contas a pagar.",
       "Confira se o arquivo segue o modelo. Se repetir, envie o código e o arquivo ao suporte."),
    _e("FLIC-IMP-905", 500, "Falha na importação do extrato da maquininha", "Não foi possível processar o extrato da maquininha.",
       "Erro inesperado ao ler o extrato de vendas em cartão.",
       "Confira se o arquivo segue o modelo de extrato da maquininha."),
    _e("FLIC-IMP-906", 500, "Falha na importação de lançamentos (conciliação cartão)", "Não foi possível processar o arquivo de lançamentos.",
       "Erro inesperado ao importar lançamentos pela conciliação de cartão.",
       "Confira se o arquivo segue o modelo de lançamentos."),
    _e("FLIC-IMP-907", 500, "Falha na importação de lançamentos (conciliação banco)", "Não foi possível processar o arquivo de lançamentos.",
       "Erro inesperado ao importar lançamentos pela conciliação bancária.",
       "Confira se o arquivo segue o modelo de lançamentos."),
    _e("FLIC-IMP-908", 500, "Falha na importação do extrato bancário", "Não foi possível processar o extrato bancário.",
       "Erro inesperado ao ler o extrato (OFX, CSV ou Excel).",
       "Exporte o extrato novamente do banco, de preferência em OFX."),
    _e("FLIC-IMP-909", 500, "Falha na importação da conta corrente", "Não foi possível processar o extrato da conta corrente.",
       "Erro inesperado ao ler o extrato da conta corrente.",
       "Confira se o arquivo segue o modelo de conta corrente."),
    _e("FLIC-IMP-910", 500, "Falha na importação do cartão (contas a pagar)", "Não foi possível processar o extrato do cartão.",
       "Erro inesperado ao ler o extrato de cartão para contas a pagar.",
       "Confira se o arquivo segue o modelo de extrato de cartão."),
    _e("FLIC-IMP-911", 500, "Falha na importação do banco (contas a pagar)", "Não foi possível processar o extrato bancário de contas a pagar.",
       "Erro inesperado ao ler o extrato bancário para contas a pagar.",
       "Confira se o arquivo segue o modelo de banco contas a pagar."),

    # ---------------------------------------------------------------- Tarefas
    _e("FLIC-TAR-001", 404, "Tarefa não encontrada", "Tarefa não encontrada.",
       "A tarefa foi excluída ou não está visível para o seu usuário.",
       "Volte à lista de tarefas e recarregue a página."),
    _e("FLIC-TAR-002", 403, "Sem permissão para editar", "Apenas quem criou a tarefa ou o admin pode editá-la.",
       "Só o criador da tarefa ou um admin (coordenador/editor) pode editar.",
       "Peça a quem criou a tarefa ou a um admin para fazer a alteração."),
    _e("FLIC-TAR-003", 403, "Sem permissão para concluir", "Apenas o responsável ou o admin pode concluir a tarefa.",
       "Só o responsável pela tarefa ou um admin pode concluir/reabrir.",
       "Peça ao responsável ou a um admin."),
    _e("FLIC-TAR-004", 403, "Sem permissão para excluir", "Apenas quem criou a tarefa ou o admin pode excluí-la.",
       "Só o criador da tarefa ou um admin pode excluir.",
       "Peça a quem criou a tarefa ou a um admin."),
    _e("FLIC-TAR-005", 400, "Título inválido", "Informe um título com até 200 caracteres.",
       "O título ficou vazio ou passou de 200 caracteres.",
       "Preencha um título curto e use a descrição para os detalhes."),
    _e("FLIC-TAR-006", 400, "Responsável inválido", "Responsável inválido.",
       "O usuário escolhido como responsável não existe ou está inativo.",
       "Escolha um responsável ativo da lista."),
    _e("FLIC-TAR-007", 400, "Cliente inválido para a tarefa", "Cliente inválido.",
       "A empresa escolhida está inativa ou não está atribuída a você.",
       "Escolha uma empresa da lista."),
    _e("FLIC-TAR-008", 400, "Módulo inválido", "Módulo inválido para esta tarefa.",
       "Módulo escolhido sem empresa vinculada, ou módulo inexistente.",
       "Vincule a tarefa a uma empresa antes de escolher o módulo."),
    _e("FLIC-TAR-009", 400, "Link inválido", "Link inválido. Use um endereço http(s) ou um caminho do sistema iniciado por /.",
       "O link não começa com http://, https:// ou /, ou passou de 500 caracteres.",
       "Cole o endereço completo (https://...) ou um caminho interno como /contas-pagar."),
    _e("FLIC-TAR-010", 403, "Sem acesso ao cliente da tarefa", "Você não tem acesso ao cliente desta tarefa.",
       "A tarefa é de uma empresa que não está atribuída a você.",
       "Peça a um coordenador para atribuir a empresa ou reatribuir a tarefa."),

    # ---------------------------------------------------------------- Fechamento de período
    _e("FLIC-FEC-001", 400, "Extrato bancário obrigatório", "Anexe o extrato bancário em PDF para fechar o período.",
       "O período só pode ser fechado com ao menos um extrato bancário em PDF anexado.",
       "Clique em \"Extrato bancário (PDF)\", escolha o arquivo e feche o período novamente.", slug="extrato_obrigatorio"),
    _e("FLIC-FEC-002", 400, "Extrato inválido", "O extrato precisa ser um PDF válido de até 10 MB.",
       "O arquivo enviado não é PDF, está vazio, passa de 10 MB ou o envio total passou de 12 MB.",
       "Exporte o extrato em PDF pelo banco. Se forem vários arquivos grandes, feche com um e anexe os demais depois.",
       slug="extrato_invalido"),
    _e("FLIC-FEC-003", 409, "Período já fechado", "Já existe um fechamento que cobre parte deste período.",
       "Os períodos fechados de um cliente não podem se sobrepor.",
       "Confira a lista de períodos fechados e escolha datas fora deles.", slug="periodo_ja_fechado"),
    _e("FLIC-FEC-004", 400, "Período inválido", "Informe um período válido para fechar.",
       "A data final é anterior à inicial ou as datas não foram informadas.",
       "Escolha as datas de início e fim e gere o fechamento antes de fechar.", slug="periodo_invalido"),
    _e("FLIC-FEC-005", 404, "Extrato indisponível", "Extrato não encontrado.",
       "O arquivo não existe mais, pertence a um cliente fora do seu acesso ou o perfil não pode consultá-lo.",
       "Consulte os extratos em Auditoria → Extratos de fechamento com um usuário administrador ou editor."),

    # ---------------------------------------------------------------- Cadastros
    _e("FLIC-CAD-001", 400, "Dados inválidos", "Não foi possível salvar. Revise os campos informados.",
       "Algum campo obrigatório ficou vazio ou foi preenchido em formato inválido.",
       "Revise os campos destacados e salve novamente.", slug="dados_invalidos"),
    _e("FLIC-CAD-002", 404, "Cliente não encontrado", "Cliente não encontrado.",
       "O cliente foi excluído ou não está disponível para o seu usuário.",
       "Recarregue a lista de clientes.", slug="cliente_nao_encontrado"),
    _e("FLIC-CAD-003", 404, "Usuário não encontrado", "Usuário não encontrado.",
       "O usuário foi excluído ou o link está desatualizado.",
       "Recarregue a lista de funcionários.", slug="usuario_nao_encontrado"),
    _e("FLIC-CAD-004", 400, "Nenhum cliente selecionado", "Selecione ao menos um cliente.",
       "A opção \"clientes selecionados\" foi escolhida sem marcar clientes.",
       "Marque os clientes ou escolha \"todos\".", slug="selecione_clientes"),
    _e("FLIC-CAD-005", 400, "Plano de contas inválido", "Selecione um plano de contas permitido.",
       "O plano escolhido não está ativo ou não é do tipo esperado.",
       "Escolha um plano de contas da lista.", slug="plano_invalido"),
    _e("FLIC-CAD-006", 400, "Nome obrigatório", "Informe o nome.",
       "O cadastro foi enviado sem nome.",
       "Preencha o nome e salve novamente.", slug="nome_obrigatorio"),
    _e("FLIC-CAD-007", 409, "E-mail já cadastrado", "Este e-mail já está cadastrado.",
       "Já existe um usuário com este e-mail.",
       "Use outro e-mail ou edite o usuário existente.", slug="email_duplicado"),
    _e("FLIC-CAD-008", 400, "Campos obrigatórios", "Preencha os campos obrigatórios.",
       "Campos marcados com * ficaram vazios.",
       "Preencha todos os campos obrigatórios.", slug="campos_obrigatorios"),
    _e("FLIC-CAD-009", 400, "Senha fora do padrão", "A nova senha deve ter pelo menos 6 caracteres e no máximo 72 bytes.",
       "Senha curta demais ou longa demais.",
       "Use uma senha com 6 caracteres ou mais.", slug="senha_curta"),
    _e("FLIC-CAD-010", 403, "Perfil próprio protegido", "Você não pode retirar o perfil de coordenador da própria conta.",
       "Um coordenador tentou rebaixar o próprio perfil, o que poderia deixar o sistema sem coordenador.",
       "Peça a outro coordenador para alterar o seu perfil.", slug="perfil_proprio"),
    _e("FLIC-CAD-011", 409, "Exclusão bloqueada", "Não é possível excluir: existem registros vinculados.",
       "O cadastro tem lançamentos, contas ou outros registros ligados a ele.",
       "Inative o cadastro em vez de excluir, ou remova os vínculos antes.", slug="exclusao_restrita"),
    _e("FLIC-CAD-012", 403, "Exclusão da própria conta", "Você não pode excluir a própria conta.",
       "O usuário tentou excluir a si mesmo.",
       "Peça a outro coordenador para excluir a conta.", slug="excluir_proprio"),
    _e("FLIC-CAD-013", 400, "Centro de custo inválido", "Centro de custo inválido.",
       "O centro de custo não existe ou pertence a outra empresa.",
       "Escolha um centro de custo da empresa.", slug="centro_custo_inv"),
    _e("FLIC-CAD-014", 403, "Conta padrão protegida", "Contas padrão protegidas.",
       "Contas do plano padrão (globais) não podem ser excluídas por esta tela.",
       "Para remover uma conta padrão, entre em Cadastros → Serviços → Contas padrão."),
    _e("FLIC-CAD-015", 403, "Acesso negado ao cadastro", "Acesso negado.",
       "O perfil do usuário não pode alterar este cadastro.",
       "Peça a um coordenador para fazer a alteração.", slug="acesso_negado"),
    _e("FLIC-CAD-016", 400, "Cliente obrigatório", "Selecione o cliente vinculado à secretária.",
       "Toda secretária precisa estar vinculada a um único cliente ativo.",
       "Escolha o cliente na lista e salve novamente.", slug="cliente_obrigatorio"),
    _e("FLIC-CAD-017", 400, "Use o cadastro de secretárias", "Secretárias são cadastradas na tela Secretárias.",
       "O perfil Secretária exige cliente vinculado, que só é informado na tela própria.",
       "Entre em Cadastros → Secretárias para criar ou vincular a secretária.", slug="usar_tela_secretarias"),
]

CATALOGO: dict[str, DefinicaoErro] = {d.codigo: d for d in _DEFINICOES}
POR_SLUG: dict[str, DefinicaoErro] = {d.slug: d for d in _DEFINICOES if d.slug}

# Código genérico por status HTTP, para erros que ainda não têm código próprio.
CODIGO_POR_STATUS = {
    400: "FLIC-GER-400", 401: "FLIC-GER-403", 403: "FLIC-GER-403", 404: "FLIC-GER-404",
    405: "FLIC-GER-404", 409: "FLIC-GER-409", 413: "FLIC-GER-400", 422: "FLIC-GER-422",
    429: "FLIC-GER-429", 500: "FLIC-GER-500", 503: "FLIC-GER-503",
}

# Código de falha inesperada por tipo de importação (nome da operação no log).
CODIGO_POR_IMPORTACAO = {
    "importar_planilha_lancamentos": "FLIC-IMP-901",
    "importar_planilha_bpo_atualizado": "FLIC-IMP-902",
    "importar_visao_contas_a_receber": "FLIC-IMP-903",
    "importar_contas_pagar": "FLIC-IMP-904",
    "importar_extrato_maquininha": "FLIC-IMP-905",
    "importar_lancamentos_conciliacao": "FLIC-IMP-906",
    "importar_lancamentos_banco": "FLIC-IMP-907",
    "importar_extrato_banco": "FLIC-IMP-908",
    "importar_conta_corrente": "FLIC-IMP-909",
    "importar_cartao_contas_pagar": "FLIC-IMP-910",
    "importar_banco_contas_pagar": "FLIC-IMP-911",
}


def definicao(codigo: str) -> DefinicaoErro:
    return CATALOGO[codigo]


def codigo_por_status(status: int) -> str:
    if status in CODIGO_POR_STATUS:
        return CODIGO_POR_STATUS[status]
    return "FLIC-GER-500" if status >= 500 else "FLIC-GER-400"


def com_codigo(codigo: str, mensagem: Optional[str] = None) -> str:
    """Texto para flash/avisos: "[FLIC-XXX-NNN] mensagem"."""
    return f"[{codigo}] {mensagem or CATALOGO[codigo].mensagem}"


class ErroFlic(HTTPException):
    """HTTPException com código do catálogo. Mantém status e mensagem padrão do código."""

    def __init__(self, codigo: str, mensagem: Optional[str] = None, *, status: Optional[int] = None,
                 headers: Optional[dict] = None):
        d = CATALOGO[codigo]
        super().__init__(status_code=status or d.status, detail=mensagem or d.mensagem, headers=headers)
        self.codigo = codigo


def erro(codigo: str, mensagem: Optional[str] = None, **kwargs) -> ErroFlic:
    return ErroFlic(codigo, mensagem, **kwargs)


def public_import_error(logger: logging.Logger, operation: str) -> str:
    """Registra a falha inesperada de importação no log e devolve a mensagem com código."""
    codigo = CODIGO_POR_IMPORTACAO.get(operation, "FLIC-GER-500")
    logger.exception("file_processing_failed", extra={"operation": operation, "error_code": codigo})
    return com_codigo(codigo, CATALOGO[codigo].mensagem + " Verifique o formato e tente novamente.")
