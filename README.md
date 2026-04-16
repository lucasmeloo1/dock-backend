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
5. Em `dock-app`, adicionar `OPENAI_API_KEY` nas variáveis de ambiente se quiser chat aberto com IA.

### Observações

- O banco local `dock.db` não deve ser usado em produção.
- Em deploy grátis, o app pode dormir por inatividade.
- Sem `OPENAI_API_KEY`, respostas rápidas e partes do dashboard continuam funcionando, mas respostas abertas da IA podem falhar.
