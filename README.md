# Dock

Dock agora está organizado em duas áreas claras:

- `backend/`: API FastAPI, regras do produto, integração com banco e deploy.
- `frontend/`: interface web servida pelo backend.

O app continua funcionando como uma única entrega, mas com a separação pronta para lapidar backend e frontend sem misturar tudo na raiz.

## Rodar local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

Abra `http://127.0.0.1:8000`.

## Estrutura

```text
.
├── backend/
│   ├── __init__.py
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.css
│   ├── app.js
│   └── assets/
├── render.yaml
└── README.md
```

## Deploy grátis no Render

O projeto já inclui `render.yaml`, então o fluxo é:

1. Subir esta pasta para um repositório no GitHub.
2. No Render, usar `New +` > `Blueprint`.
3. Selecionar o repositório.
4. Confirmar a criação do `dock-app` e do `dock-db`.
5. Após o deploy, abrir `dock-app` e copiar a URL pública gerada pelo Render.
6. Se quiser respostas abertas com IA, adicionar `OPENAI_API_KEY` nas variáveis de ambiente.

### Variáveis de ambiente relevantes

- `AI_PROVIDER=auto`: usa OpenAI quando `OPENAI_API_KEY` existe; sem chave, o app continua funcional com respostas locais e fallbacks rápidos.
- `APP_TIMEZONE=America/Sao_Paulo`: mantém datas e resumos no fuso correto.
- `CHAT_TIMEOUT_SECONDS`, `AI_TIMEOUT_SECONDS` e `LIVE_DATA_TIMEOUT_SECONDS`: evitam travas longas em chamadas externas.

### Observações

- O banco local SQLite fica em `backend/dock.db` e não deve ser usado em produção.
- Em deploy grátis, o app pode dormir por inatividade.
- Sem `OPENAI_API_KEY`, o Dock continua respondendo pelos fluxos rápidos, operacionais e de dashboard, sem depender de `ollama` no link público.
- `AI_PROVIDER=ollama` faz sentido só em ambiente local com Ollama rodando.
