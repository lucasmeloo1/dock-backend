# Dock

App FastAPI com interface web e dashboard simples para conversa, hábitos, estudo e finanças.

## Rodar local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Abra `http://127.0.0.1:8000`.

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

- O banco local `dock.db` não deve ser usado em produção.
- Em deploy grátis, o app pode dormir por inatividade.
- Sem `OPENAI_API_KEY`, o Dock continua respondendo pelos fluxos rápidos, operacionais e de dashboard, sem depender de `ollama` no link público.
- `AI_PROVIDER=ollama` faz sentido só em ambiente local com Ollama rodando.
