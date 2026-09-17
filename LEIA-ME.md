# Como funciona o vigia INPI (arquitetura de 17/09/2026)

Motivo da mudanca: a rotina antiga rodava 100% na nuvem, e o ambiente de nuvem
bloqueia os sites do INPI (politica de rede). Por isso os e-mails de falha
toda terca.

## O desenho atual (2 pecas)

1. **Vigia local** (esta pasta, tarefa agendada do Windows "Vigia INPI Pattrono")
   - Roda TERCA as 19h. Se o PC estiver desligado, roda assim que ligar.
   - Consulta o pePI (pedidos 944976310 PATTRONO e 944976891 COSTVISION)
     e a RPI da semana (baixa o zip da revista de marcas e procura os numeros).
   - Publica status.json / last_run.md / historico.md em
     github.com/gustavofuster95-prog/pattrono-inpi-vigia
   - Se houver MOVIMENTACAO ou FALHA: abre uma issue no repositorio,
     e o GitHub envia e-mail automaticamente.

2. **Supervisor na nuvem** (rotina claude.ai "Supervisor INPI Pattrono")
   - Roda QUARTA as 12h (BRT). Le o resultado publicado no GitHub.
   - Movimentacao -> e-mail bonito via Gmail. Falha -> e-mail. Resultado
     com mais de 8 dias (vigia local nao rodou) -> e-mail avisando.
   - Tudo certo e sem novidade -> silencio.

## Regra de ouro

Silencio = sem novidade. Qualquer coisa que exija sua atencao vira
e-mail (do GitHub e/ou do supervisor).

## Operacao manual

- Rodar agora:   python vigia_run_local.py   (nesta pasta)
- Ver historico: historico.md ou o repositorio no GitHub
- Tarefa Windows: Agendador de Tarefas > "Vigia INPI Pattrono"

## Melhoria futura (opcional)

Migrar a checagem para GitHub Actions (workflow pronto em
.github/workflows/vigia.yml, ainda nao publicado porque o token gh local
nao tem escopo "workflow"). Para habilitar: `gh auth refresh -s workflow`
(pede um codigo no navegador) e depois `git add .github && git commit && git push`.
Ai a checagem roda no GitHub mesmo com o PC desligado, e a tarefa local
pode ser removida.
