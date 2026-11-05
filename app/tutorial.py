"""Conteúdo da aba Tutorial: um treinamento por perfil, com prints reais das telas.

Cada módulo e cada passo declaram para quais perfis valem — as mesmas regras de acesso do
menu lateral (app/templates/base.html). As imagens ficam em static/tutorial/ e são geradas
por scripts/gerar_prints_tutorial.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

COORD, EDITOR, FUNC, MEDICO, SEC = "coordenador", "editor", "funcionario", "medico", "secretaria"
TODOS = frozenset({COORD, EDITOR, FUNC, MEDICO, SEC})
EQUIPE = frozenset({COORD, EDITOR, FUNC})            # operação financeira completa
SEM_SECRETARIA = TODOS - {SEC}
ADMINS = frozenset({COORD, EDITOR})

PERFIS = {
    COORD: {
        "nome": "Coordenador",
        "papel": "Você enxerga todas as empresas, opera todos os módulos e administra equipe, cadastros, auditoria e logs.",
        "imagem": "menu-coordenador",
    },
    EDITOR: {
        "nome": "Editor",
        "papel": "Você opera as empresas em que é o responsável, administra grupos, serviços e secretárias e consulta a auditoria.",
        "imagem": "menu-editor",
    },
    FUNC: {
        "nome": "Funcionário",
        "papel": "Você faz a operação financeira do dia a dia das empresas em que é o responsável: lançamentos, conciliação, contas a pagar e gestão.",
        "imagem": "menu-funcionario",
    },
    MEDICO: {
        "nome": "Médico",
        "papel": "Você acompanha os números da sua empresa: lançamentos, contas a pagar e os relatórios de receitas, despesas e DRE — em modo consulta.",
        "imagem": "menu-medico",
    },
    SEC: {
        "nome": "Secretária",
        "papel": "Você registra e confere os lançamentos a receber da sua empresa. A empresa é fixa: o sistema sempre abre na empresa do seu cadastro.",
        "imagem": "menu-secretaria",
    },
}


@dataclass(frozen=True)
class Passo:
    titulo: str
    texto: str
    perfis: frozenset = TODOS


@dataclass(frozen=True)
class Modulo:
    id: str
    titulo: str
    icone: str
    grupo: str
    perfis: frozenset
    resumo: str
    imagem: str | None = None
    passos: tuple = ()
    dicas: tuple = ()
    imagens_extras: tuple = field(default=())  # (arquivo, legenda)


MODULOS: tuple[Modulo, ...] = (
    # ------------------------------------------------------------------ primeiros passos
    Modulo(
        "primeiros-passos", "Primeiros passos", "rocket", "Comece por aqui", TODOS,
        "Como entrar, se localizar no menu e deixar o FLIC do seu jeito.",
        "login",
        passos=(
            Passo("Entre com seu e-mail e senha", "Na tela de login, informe o e-mail corporativo e a senha. Use o ícone de olho para conferir a senha antes de entrar. Após várias tentativas erradas o acesso fica bloqueado por alguns minutos."),
            Passo("Escolha a empresa", "No Painel geral aparecem as empresas que você atende. Clique em uma delas para entrar no ambiente dela: tudo o que você vir e lançar a partir daí será daquela empresa. A empresa atual aparece no topo da tela e no menu.", SEM_SECRETARIA),
            Passo("Sua empresa já vem selecionada", "Você não precisa escolher empresa: o FLIC sempre abre na empresa do seu cadastro, direto na tela de lançamentos.", frozenset({SEC})),
            Passo("Use o menu lateral", "O menu é organizado por módulo. O item em destaque mostra onde você está. O botão ao lado do título da página recolhe o menu e deixa só os ícones — passe o mouse sobre um ícone para ver o nome."),
            Passo("Modo claro ou escuro", "O botão de lua/sol no canto superior direito alterna o tema. A escolha fica salva neste navegador."),
            Passo("Avisos e mensagens", "Quando você salva, concilia ou exclui algo, um aviso aparece no canto inferior direito confirmando a operação ou explicando o problema. Se aparecer um código como FLIC-CON-020, ele identifica exatamente o que aconteceu."),
            Passo("Pesquisar em qualquer tabela", "Todas as tabelas têm o campo \"Pesquisar na tabela\" e a escolha de quantos registros mostrar por página. A pesquisa procura em todas as colunas visíveis."),
        ),
        dicas=("Para sair, use o botão Sair no rodapé do menu.",),
        imagens_extras=(("menu-recolhido", "Menu recolhido: só os ícones"), ("tema-escuro", "O mesmo painel no modo escuro")),
    ),
    Modulo(
        "painel-geral", "Painel geral e empresas", "layout-grid", "Comece por aqui", SEM_SECRETARIA,
        "O ponto de partida: suas tarefas pessoais e a lista de empresas para entrar.",
        "painel",
        passos=(
            Passo("Veja suas tarefas", "A seção Minhas tarefas mostra o que está com você. Alterne entre Lista e Calendário e crie uma tarefa em + Nova tarefa."),
            Passo("Entre em uma empresa", "Clique no cartão da empresa. O selo amarelo indica quantas tarefas estão pendentes nela. Com muitas empresas, use a busca acima da lista."),
            Passo("Troque de empresa a qualquer momento", "No menu, em Empresa atual, clique em Trocar empresa — ou no nome da empresa no topo da tela."),
        ),
    ),
    # ------------------------------------------------------------------ visão
    Modulo(
        "dashboard", "Dashboard", "layout-dashboard", "Visão geral", SEM_SECRETARIA,
        "Os números do mês da empresa: recebido, pago, resultado, contas em aberto e conciliação.",
        "dashboard",
        passos=(
            Passo("Indicadores do mês", "Recebido no mês e Pago no mês comparam com o mesmo período do mês anterior (seta verde ou vermelha). Resultado do mês é o recebido menos o pago. O cartão A pagar em aberto mostra quantas contas estão vencidas — clique nele para abrir Contas a pagar."),
            Passo("Gráfico recebido × pago", "Mostra os últimos 6 meses. Passe o mouse sobre um mês para ver os valores e o resultado."),
            Passo("Saldos bancários e movimentações", "Com uma empresa selecionada, veja o saldo previsto de cada conta, o andamento da conciliação (barra de progresso) e os últimos lançamentos do extrato."),
            Passo("Média mensal", "O painel à direita traz a média dos últimos 3 meses completos. Use Ocultar médias para ganhar espaço."),
            Passo("Visão da equipe", "Sem empresa selecionada, o coordenador vê o resumo de todos os clientes e a produtividade de cada funcionário.", frozenset({COORD})),
        ),
        dicas=("Os números consideram só recebimentos conciliados e contas integralmente pagas.",),
    ),
    Modulo(
        "tarefas", "Tarefas", "list-todo", "Visão geral", SEM_SECRETARIA,
        "Organize o trabalho da equipe: tarefas pessoais ou vinculadas a uma empresa e a um módulo.",
        "tarefas",
        passos=(
            Passo("Crie uma tarefa", "Clique em + Nova tarefa, dê um título, escolha o responsável, a empresa (opcional), o módulo e o prazo."),
            Passo("Filtre", "Filtre por situação, vínculo, cliente e responsável."),
            Passo("Conclua ou reabra", "Clique no círculo à esquerda da tarefa. Tarefas atrasadas aparecem destacadas em vermelho."),
            Passo("Vá direto ao trabalho", "O botão Ir para módulo abre a tela ligada à tarefa, já na empresa certa."),
        ),
    ),
    # ------------------------------------------------------------------ contas a receber
    Modulo(
        "lancamentos", "Lançamentos (contas a receber)", "receipt-text", "Contas a receber", TODOS,
        "Consulte, filtre e acompanhe tudo o que a empresa tem a receber.",
        "lancamentos",
        passos=(
            Passo("Resumo do período", "Os quatro cartões no topo mostram Todos no período, Aguardando conciliação, Conciliados e Com divergência — com quantidade e valor. Clique em um cartão para filtrar a lista."),
            Passo("Escolha o período", "Use os atalhos Hoje, 7 dias, Este mês e Mês passado, ou as datas De e Até. Filtre também por situação de conciliação e forma de pagamento."),
            Passo("Leia o status", "Pendente (amarelo): ainda não apareceu no extrato do banco. Conciliado (verde): o dinheiro entrou e foi conferido. Divergência (vermelho): precisa de atenção."),
            Passo("Escolha as colunas", "O botão Colunas mostra ou esconde campos como CPF, taxa do cartão, valor líquido e data de crédito. A escolha fica salva."),
            Passo("Edite um lançamento", "Clique no lápis da linha. Lançamentos já conciliados ficam bloqueados para não desfazer a conferência.", TODOS - {MEDICO}),
            Passo("Exclua", "Use a lixeira da linha, ou selecione vários e use Ações em lote → Excluir selecionados. Registros conciliados são desconciliados antes, com sua confirmação.", EQUIPE),
            Passo("Importe uma planilha", "O botão Importar planilha leva para Importações, com os modelos aceitos.", EQUIPE),
        ),
        dicas=("A pesquisa da tabela encontra por paciente, serviço, valor ou qualquer coluna visível.",),
    ),
    Modulo(
        "incluir-lancamento", "Incluir lançamento", "circle-plus", "Contas a receber", TODOS - {MEDICO},
        "Registre um atendimento ou receita — à vista, parcelado ou recorrente, com rateio por centro de custo.",
        "lancamento-novo",
        passos=(
            Passo("Data do atendimento", "Informe a data. A empresa já vem preenchida."),
            Passo("Preencha a receita", "Paciente e CPF (opcionais), plano de contas, valor e descrição."),
            Passo("Rateio por centro de custo", "Divida o valor entre centros de custo (por exemplo, por médico). O percentual usado precisa fechar 100%."),
            Passo("Forma e condição", "Escolha a forma (Pix, transferência, cartão, dinheiro...) e a condição (à vista ou parcelado). No cartão, informe bandeira e dígitos para a conciliação da maquininha."),
            Passo("Várias receitas de uma vez", "Use + Adicionar mais uma receita para lançar vários itens do mesmo atendimento e Salvar lançamento no final."),
        ),
        dicas=("Depois de salvar, o FLIC mostra a lista filtrada na data do atendimento para você conferir.",),
        imagens_extras=(("secretaria-novo", "A mesma tela, vista pela secretária"),),
    ),
    Modulo(
        "conciliacao-cartao", "Conciliação de cartão", "credit-card", "Contas a receber", EQUIPE,
        "Confira as vendas da maquininha com os lançamentos do sistema.",
        "conciliacao-cartao",
        passos=(
            Passo("Importe o extrato da maquininha", "Em Extrato maquininha, escolha o arquivo (XLSX ou CSV) e clique em Importar vendas. As colunas esperadas aparecem no rodapé da tela."),
            Passo("Confira lado a lado", "À esquerda, as vendas do extrato; à direita, os lançamentos do sistema. O FLIC sugere o par pela data, valor, bandeira e dígitos do cartão."),
            Passo("Concilie, edite ou crie", "Confirme a sugestão, ajuste a venda ou crie o lançamento que faltou direto da venda."),
        ),
    ),
    # ------------------------------------------------------------------ conciliação
    Modulo(
        "conciliacao-banco", "Conciliação bancária", "landmark", "Conciliação", EQUIPE,
        "O coração do FLIC: o extrato do banco de um lado, os lançamentos do sistema do outro.",
        "conciliacao-banco",
        passos=(
            Passo("Cadastre as contas", "Em + Cadastrar conta, escolha o tipo: Conta corrente, Investimentos ou Cartão de crédito (para o cartão basta o nome). Selecione a conta no topo para filtrar o extrato."),
            Passo("Importe o extrato", "Escolha o arquivo (OFX, XLSX ou CSV) e clique em Importar extrato. Também é possível lançar um movimento manual."),
            Passo("Concilie as sugestões", "Cada crédito ou débito do extrato aparece com a sugestão do sistema ao lado: verde (Encontramos) é valor exato; amarelo (Quase lá) tem pequena diferença. Clique em Conciliar."),
            Passo("Busque quando não houver sugestão", "Use Buscar lançamento (créditos) ou Vincular conta (débitos) para escolher manualmente."),
            Passo("Crie o que faltou", "Num crédito sem correspondente, use + Novo lançamento. Num débito, use + Nova despesa: a conta a pagar nasce já paga e conciliada com a saída."),
            Passo("Regras automáticas", "Em Regras de negócio bancárias, cadastre padrões de descrição (ex.: \"RENDIMENTOS\") para conciliar sozinho. Aplicar aos existentes roda a regra no extrato já importado."),
            Passo("Desfaça se precisar", "Desvincular devolve o movimento e o lançamento para pendente."),
        ),
        imagens_extras=(("conciliacao-banco-lista", "Extrato à esquerda, sistema à direita"),),
    ),
    Modulo(
        "conciliar-varios", "Conciliar vários de uma vez", "list-checks", "Conciliação", EQUIPE,
        "Quando um único valor do extrato paga vários lançamentos — ou um lançamento é pago em várias partes.",
        "conciliacao-varios",
        passos=(
            Passo("Do lado do banco", "No movimento do extrato, clique em ☑ Conciliar vários e marque os lançamentos (créditos) ou as contas a pagar (débitos) que compõem aquele valor."),
            Passo("Do lado do sistema", "Na conta a pagar ou no lançamento a receber, clique em ☑ Conciliar vários do banco e marque os créditos ou débitos do extrato que somam o valor."),
            Passo("Acompanhe o contador", "Embaixo aparece Selecionado: R$ X de R$ Y e quanto falta ou passou. O botão só libera quando a soma bate — aí ele vira Conciliar N itens."),
            Passo("Desfazer", "Desconciliar qualquer item de um recebimento agrupado reabre o grupo inteiro."),
        ),
        dicas=("Use o campo de filtro da janela para achar os itens por nome ou valor.",),
    ),
    Modulo(
        "importacoes", "Importações", "upload", "Conciliação", EQUIPE,
        "Traga dados de planilhas: lançamentos em lote, contas a pagar e relatórios de outros sistemas.",
        "importacoes",
        passos=(
            Passo("Escolha o cliente", "Selecione a empresa uma vez no topo — ela vale para todos os cartões da tela."),
            Passo("Baixe o modelo", "Cada cartão tem o botão Baixar modelo (.xlsx) com as colunas esperadas."),
            Passo("Envie o arquivo", "Preencha o modelo, escolha o arquivo e clique em Importar. Os registros são incluídos sem substituir os existentes."),
        ),
    ),
    # ------------------------------------------------------------------ contas a pagar
    Modulo(
        "contas-pagar", "Contas a pagar", "wallet", "Contas a pagar", SEM_SECRETARIA,
        "Vencimentos, status e pagamentos das despesas da empresa.",
        "contas-pagar",
        passos=(
            Passo("Resumo", "Os cartões mostram contas listadas, em aberto, vencidas e pagas, com os valores."),
            Passo("Filtre", "Por situação (em aberto, a vencer, vencidas), status, forma de pagamento e intervalo de vencimento."),
            Passo("Veja o detalhe", "Clique na linha para ver categoria, centro de custo, documento anexado e a média dos últimos 3 meses daquela despesa."),
            Passo("Mude o status", "Use Mudar status... para levar a conta para Agendado, Pago — não conciliado ou Cancelado. A baixa definitiva como Pago acontece na conciliação bancária.", EQUIPE),
            Passo("Ações em lote", "Marque várias contas para trocar categoria, centro de custo ou status, ou excluir de uma vez.", EQUIPE),
            Passo("Somente consulta", "No seu perfil a lista é de leitura: você acompanha vencimentos e pagamentos sem alterar.", frozenset({MEDICO})),
        ),
    ),
    Modulo(
        "incluir-conta", "Incluir conta a pagar", "file-plus-2", "Contas a pagar", EQUIPE,
        "Cadastre despesas avulsas, parceladas ou recorrentes.",
        "conta-pagar-nova",
        passos=(
            Passo("Dados da conta", "Descrição, fornecedor, valor, vencimento, competência e forma de pagamento."),
            Passo("Classificação", "Plano de contas e rateio por centro de custo (precisa fechar 100%)."),
            Passo("Conta do banco", "Escolha de qual conta bancária da empresa ela será paga."),
            Passo("Recorrência", "Para despesas fixas, gere as próximas parcelas e defina com quantos dias de antecedência o FLIC deve avisar no dashboard."),
            Passo("Anexe o documento", "Boleto ou nota em PDF/JPG/PNG ficam disponíveis no detalhe da conta."),
        ),
    ),
    Modulo(
        "aprovacao", "Aprovação de pagamentos", "badge-check", "Contas a pagar", EQUIPE,
        "Monte o relatório das contas a pagar para o cliente aprovar.",
        "aprovacao",
        passos=(
            Passo("Gere a aprovação", "Escolha Aprovar até (data limite) e informe o Saldo em conta. Clique em Gerar aprovação."),
            Passo("Confira os totais", "O FLIC soma as despesas e mostra o saldo final provisório."),
            Passo("Envie ao cliente", "Baixe o PDF para aprovação ou copie o texto pronto em Texto para enviar ao cliente."),
        ),
    ),
    # ------------------------------------------------------------------ gestão
    Modulo(
        "receitas-despesas", "Receitas e despesas", "trending-up", "Gestão", SEM_SECRETARIA,
        "Relatórios do mês por competência ou por caixa.",
        "receitas",
        passos=(
            Passo("Escolha o mês e o regime", "Competência considera a data do atendimento/vencimento; Caixa considera quando o dinheiro entrou ou saiu."),
            Passo("Leia os totais", "Total do período, quantidade e ticket médio no topo; a lista detalhada com status logo abaixo."),
            Passo("Despesas", "A tela de Despesas funciona do mesmo jeito, para as contas a pagar."),
        ),
        imagens_extras=(("despesas", "Gestão de despesas"),),
    ),
    Modulo(
        "orcamento", "Orçamento", "target", "Gestão", EQUIPE,
        "Planeje receitas e despesas do mês com base no que aconteceu no mês anterior.",
        "orcamento",
        passos=(
            Passo("Defina a margem", "Informe a margem desejada (%). O FLIC calcula o limite recomendado de despesas e a receita mínima."),
            Passo("Preencha por plano de contas", "Digite o valor orçado para cada receita e despesa e clique em Salvar orçamento."),
            Passo("Compare no DRE", "O orçado aparece ao lado do realizado no DRE."),
        ),
    ),
    Modulo(
        "dre", "DRE", "chart-column", "Gestão", SEM_SECRETARIA,
        "Demonstrativo de resultado: orçado × realizado por plano de contas.",
        "dre",
        passos=(
            Passo("Gere o DRE", "Escolha mês, ano e regime (caixa ou competência), ou um período rápido (7, 30, 90 dias, ano atual)."),
            Passo("Leia a tabela", "Receitas e despesas por plano de contas, com orçado, real e diferença, e o resultado no rodapé."),
            Passo("Apresente ao cliente", "Modo apresentação mostra o DRE em slides, em tela cheia, pronto para reunião."),
        ),
    ),
    Modulo(
        "fechamento", "Fechamento do mês", "calendar-check", "Gestão", EQUIPE,
        "Confira o período e feche o mês com o extrato bancário anexado.",
        "fechamento-mensal",
        passos=(
            Passo("Gere o fechamento", "Escolha o período e clique em Gerar fechamento: receitas confirmadas no banco, despesas pagas e o resultado."),
            Passo("Feche o período", "Para fechar é obrigatório anexar o extrato bancário em PDF. Ele fica guardado para consulta da auditoria."),
        ),
    ),
    # ------------------------------------------------------------------ cadastros
    Modulo(
        "clientes", "Clientes", "building-2", "Cadastros", EQUIPE,
        "Cadastro das empresas atendidas: dados, responsável, centros de custo e maquininhas.",
        "clientes",
        passos=(
            Passo("Novo cliente", "Expanda Novo cliente BPO e preencha razão social, CNPJ e especialidade.", ADMINS),
            Passo("Entre no cadastro", "Entrar no cadastro abre os dados completos; Centros abre os centros de custo da empresa."),
            Passo("Responsável", "Cada empresa tem um responsável — é ele quem a enxerga na operação.", ADMINS),
            Passo("Atribua-se a uma empresa", "Como editor, você vê todas as empresas no cadastro e pode se colocar como responsável.", frozenset({EDITOR})),
        ),
    ),
    Modulo(
        "anotacoes", "Anotações de clientes", "notebook-pen", "Cadastros", EQUIPE,
        "O caderno de cada cliente: procedimentos, preferências e observações internas.",
        "anotacoes",
        passos=(
            Passo("Abra o caderno", "Clique em Entrar nas anotações no cartão da empresa."),
            Passo("Registre", "Crie, edite e exclua notas. Só o autor ou o coordenador excluem uma nota."),
        ),
    ),
    Modulo(
        "grupos-servicos", "Grupos de empresas e serviços", "boxes", "Cadastros", ADMINS,
        "Agrupe empresas do mesmo dono e padronize os serviços usados nos lançamentos.",
        "grupos",
        passos=(
            Passo("Grupos", "Reúna empresas relacionadas e defina o responsável do grupo."),
            Passo("Serviços", "Cadastre serviços com plano de contas para agilizar os lançamentos."),
        ),
        imagens_extras=(("servicos", "Cadastro de serviços"),),
    ),
    Modulo(
        "funcionarios-plano", "Funcionários e plano de contas", "users", "Cadastros", frozenset({COORD}),
        "Gerencie a equipe e a estrutura do plano de contas.",
        "funcionarios",
        passos=(
            Passo("Funcionários", "Crie usuários, defina o perfil (coordenador, editor, funcionário, médico), ative ou desative. Trocar o perfil encerra as sessões abertas da pessoa."),
            Passo("Plano de contas", "Organize as contas de receita e despesa (geral ou por empresa) usadas em lançamentos, DRE e orçamento."),
        ),
        imagens_extras=(("plano-contas", "Plano de contas"),),
    ),
    # ------------------------------------------------------------------ auditoria
    Modulo(
        "auditoria", "Auditoria", "history", "Auditoria", ADMINS,
        "Quem alterou o quê, quando — e os extratos dos períodos fechados.",
        "auditoria-historico",
        passos=(
            Passo("Histórico de alterações", "Filtre por período, usuário, empresa e tipo de ação. Abra uma operação para ver o antes e o depois de cada campo. O histórico não pode ser alterado nem apagado."),
            Passo("Extratos de fechamento", "Consulte e baixe os PDFs anexados no fechamento de cada período."),
            Passo("Secretárias", "Cadastre as secretárias, sempre vinculadas a uma empresa, e ative ou desative o acesso."),
            Passo("Logs do sistema", "O registro técnico de ações (importações, conciliações, exclusões).", frozenset({COORD})),
        ),
        imagens_extras=(("auditoria-extratos", "Extratos de fechamento"), ("secretarias", "Cadastro de secretárias")),
    ),
    # ------------------------------------------------------------------ ajuda
    Modulo(
        "ajuda", "Códigos de erro e ajuda", "circle-help", "Ajuda", TODOS,
        "O que fazer quando aparece uma mensagem de erro.",
        "ajuda-erros",
        passos=(
            Passo("Leia o código", "Toda mensagem traz um código (ex.: FLIC-AUT-004). Em Ajuda, no rodapé do menu, você encontra o significado e o que fazer."),
            Passo("Peça suporte com o código", "Ao pedir ajuda, informe o código e o identificador que aparece na página de erro — assim o suporte encontra exatamente o que aconteceu."),
        ),
    ),
)


# Telas que o perfil vê diferente: mostra o print feito com o próprio perfil.
IMAGEM_DO_PERFIL = {
    (SEC, "lancamentos"): "menu-secretaria",
    (SEC, "incluir-lancamento"): "secretaria-novo",
}


def treinamento_do_perfil(perfil: str) -> dict:
    """Módulos e passos visíveis para o perfil, já filtrados."""
    perfil = getattr(perfil, "value", perfil)
    modulos = []
    for m in MODULOS:
        if perfil not in m.perfis:
            continue
        passos = [p for p in m.passos if perfil in p.perfis]
        imagem = IMAGEM_DO_PERFIL.get((perfil, m.id), m.imagem)
        extras = [e for e in m.imagens_extras if e[0] != imagem]
        modulos.append({"modulo": m, "passos": passos, "imagem": imagem, "extras": extras})
    grupos: dict[str, list] = {}
    for item in modulos:
        grupos.setdefault(item["modulo"].grupo, []).append(item)
    return {"perfil": PERFIS.get(perfil, PERFIS[FUNC]), "perfil_id": perfil, "modulos": modulos, "grupos": grupos}
