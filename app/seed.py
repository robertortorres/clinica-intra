from .models import User, Section, Page, slugify
from .auth import hash_password

SECTIONS = [
    {"name": "Corpo Clínico",          "icon": "👨‍⚕️", "color": "#1a3a5c", "order": 1},
    {"name": "Convênios",               "icon": "🤝",   "color": "#2563a8", "order": 2},
    {"name": "Valores de Consulta",     "icon": "💰",   "color": "#0ea5d4", "order": 3},
    {"name": "Exames",                  "icon": "🔬",   "color": "#10b981", "order": 4},
    {"name": "Procedimentos Dermato",   "icon": "💉",   "color": "#8b5cf6", "order": 5},
    {"name": "Formas de Pagamento",     "icon": "💳",   "color": "#f59e0b", "order": 6},
    {"name": "Telefones e Ramais",      "icon": "📞",   "color": "#ef4444", "order": 7},
    {"name": "Prazo de Retorno",        "icon": "📅",   "color": "#06b6d4", "order": 8},
    {"name": "Formulários",             "icon": "📋",   "color": "#64748b", "order": 9},
    {"name": "Parcerias",               "icon": "🌐",   "color": "#059669", "order": 10},
    {"name": "Ferramentas",             "icon": "🔧",   "color": "#dc2626", "order": 11},
]

TELEFONES_CONTENT = """
<h2>Telefones e Ramais Internos</h2>
<table>
  <thead><tr><th>Setor</th><th>Ramal</th><th>Telefone</th><th>E-mail</th></tr></thead>
  <tbody>
    <tr><td>Recepção</td><td>100</td><td>(12) 3934-0000</td><td>recepcao@medsel.com.br</td></tr>
    <tr><td>Financeiro</td><td>101</td><td>(12) 3934-0001</td><td>financeiro@medsel.com.br</td></tr>
    <tr><td>TI</td><td>102</td><td>(12) 3934-0002</td><td>ti@medsel.com.br</td></tr>
    <tr><td>Diretoria</td><td>103</td><td>(12) 3934-0003</td><td>diretoria@medsel.com.br</td></tr>
    <tr><td>RH</td><td>104</td><td>(12) 3934-0004</td><td>rh@medsel.com.br</td></tr>
  </tbody>
</table>
<p><em>Atualize esta tabela conforme necessário no painel admin.</em></p>
"""

PRAZO_CONTENT = """
<h2>Prazo de Retorno por Especialidade</h2>
<table>
  <thead><tr><th>Especialidade</th><th>Prazo</th><th>Observação</th></tr></thead>
  <tbody>
    <tr><td>Clínica Geral</td><td>30 dias</td><td></td></tr>
    <tr><td>Cardiologia</td><td>60 dias</td><td></td></tr>
    <tr><td>Dermatologia</td><td>90 dias</td><td></td></tr>
    <tr><td>Ortopedia</td><td>60 dias</td><td></td></tr>
    <tr><td>Ginecologia</td><td>30 dias</td><td></td></tr>
    <tr><td>Pediatria</td><td>30 dias</td><td></td></tr>
  </tbody>
</table>
<p><em>Atualize os prazos conforme necessário.</em></p>
"""


def seed(db):
    if db.query(User).count() > 0:
        return

    db.add(User(username="admin", name="Administrador",
                password=hash_password("medsel2024"), role="admin"))
    db.add(User(username="atendente", name="Atendente",
                password=hash_password("atende123"), role="viewer"))
    db.flush()

    for s in SECTIONS:
        slug = slugify(s["name"])
        sec = Section(slug=slug, name=s["name"], icon=s["icon"],
                      color=s["color"], order=s["order"])
        db.add(sec)
        db.flush()

        # Páginas de exemplo
        if s["name"] == "Telefones e Ramais":
            db.add(Page(section_id=sec.id, title="Ramais e Contatos",
                        slug="ramais-contatos", content=TELEFONES_CONTENT, order=1))
        elif s["name"] == "Prazo de Retorno":
            db.add(Page(section_id=sec.id, title="Prazos por Especialidade",
                        slug="prazos-especialidade", content=PRAZO_CONTENT, order=1))
        else:
            db.add(Page(section_id=sec.id,
                        title=f"Informações – {s['name']}",
                        slug=slugify(f"informacoes-{s['name']}"),
                        content=f"<h2>{s['name']}</h2><p>Edite esta página no painel admin para adicionar as informações desta seção.</p>",
                        order=1))
    db.commit()
