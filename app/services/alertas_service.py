from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import ContaRecorrente
from app.services.email_service import enviar_email


def _proximo_vencimento(dia: int, referencia: date) -> date:
    """Retorna a data de vencimento mais próxima a partir da referência."""
    ultimo_dia = monthrange(referencia.year, referencia.month)[1]
    dia_real = min(dia, ultimo_dia)
    venc = referencia.replace(day=dia_real)
    if venc < referencia:
        # Já passou neste mês → próximo mês
        if referencia.month == 12:
            proximo = date(referencia.year + 1, 1, 1)
        else:
            proximo = date(referencia.year, referencia.month + 1, 1)
        ultimo_dia_prox = monthrange(proximo.year, proximo.month)[1]
        venc = proximo.replace(day=min(dia, ultimo_dia_prox))
    return venc


def _corpo_email(conta: ContaRecorrente, vencimento: date, hoje: date) -> str:
    dias_restantes = (vencimento - hoje).days
    valor_str = f"R$ {float(conta.valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if conta.valor else "—"
    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:Segoe UI,system-ui,sans-serif;background:#f4f4f4;margin:0;padding:24px;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;">
    <div style="background:#222049;padding:20px 24px;">
      <p style="color:#fff;font-size:18px;font-weight:700;margin:0;">⚠️ Vencimento se aproximando</p>
      <p style="color:rgba(255,255,255,.65);font-size:13px;margin:4px 0 0;">FLIC — Aviso automático</p>
    </div>
    <div style="padding:24px;">
      <p style="color:#1e293b;font-size:15px;font-weight:600;margin:0 0 16px;">
        {conta.cliente.nome}
      </p>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <tr style="border-bottom:1px solid #e2e8f0;">
          <td style="padding:10px 0;color:#64748b;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.04em;">Conta</td>
          <td style="padding:10px 0;color:#1e293b;text-align:right;">{conta.descricao}</td>
        </tr>
        {"<tr style='border-bottom:1px solid #e2e8f0;'><td style='padding:10px 0;color:#64748b;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.04em;'>Fornecedor</td><td style='padding:10px 0;color:#1e293b;text-align:right;'>" + conta.fornecedor + "</td></tr>" if conta.fornecedor else ""}
        <tr style="border-bottom:1px solid #e2e8f0;">
          <td style="padding:10px 0;color:#64748b;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.04em;">Valor</td>
          <td style="padding:10px 0;color:#1e293b;font-weight:700;text-align:right;">{valor_str}</td>
        </tr>
        <tr style="border-bottom:1px solid #e2e8f0;">
          <td style="padding:10px 0;color:#64748b;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.04em;">Vencimento</td>
          <td style="padding:10px 0;color:#dc2626;font-weight:700;text-align:right;">{vencimento.strftime('%d/%m/%Y')}</td>
        </tr>
        <tr>
          <td style="padding:10px 0;color:#64748b;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.04em;">Dias restantes</td>
          <td style="padding:10px 0;color:#d97706;font-weight:700;text-align:right;">{dias_restantes} dia(s)</td>
        </tr>
      </table>
      <p style="margin:20px 0 0;font-size:12px;color:#94a3b8;">
        Este é um aviso automático gerado pelo FLIC.
      </p>
    </div>
  </div>
</body>
</html>
"""


def verificar_e_enviar_alertas(db: Session) -> list[str]:
    """
    Verifica todas as contas recorrentes ativas e envia e-mail quando
    a data de hoje está dentro da janela de antecedência do vencimento.
    Retorna lista de mensagens com o resultado de cada conta.
    """
    hoje = date.today()
    log: list[str] = []

    contas = db.query(ContaRecorrente).filter(ContaRecorrente.ativo == True).all()

    for conta in contas:
        vencimento = _proximo_vencimento(conta.dia_vencimento, hoje)
        alerta_a_partir = vencimento - timedelta(days=conta.dias_antecedencia)

        # Fora da janela de aviso
        if not (alerta_a_partir <= hoje <= vencimento):
            continue

        # Já enviou aviso este mês para este vencimento
        if conta.ultimo_aviso_em and conta.ultimo_aviso_em >= alerta_a_partir:
            continue

        assunto = (
            f"⚠️ Vencimento em {(vencimento - hoje).days}d — "
            f"{conta.descricao} | {conta.cliente.nome}"
        )
        corpo = _corpo_email(conta, vencimento, hoje)

        try:
            enviar_email(conta.email_destino, assunto, corpo)
            conta.ultimo_aviso_em = hoje
            db.commit()
            log.append(f"✓ Enviado para {conta.email_destino} — {conta.descricao} ({conta.cliente.nome})")
        except Exception as e:
            log.append(f"✗ Erro ao enviar para {conta.email_destino} — {conta.descricao}: {e}")

    if not log:
        log.append("Nenhum alerta pendente hoje.")

    return log
