# Próximos passos

Branch: `claude/b1-curved-wall-perf`. Último pacote entregue: TEST-8 (13/10).

## Bloco atual — vãos na parede (correções do teste TEST-7)

| # | Problema | Onde | Quem |
|---|---|---|---|
| 1 | **Corrigido em 13/10.** Botões de criar vão não achavam a parede: o pick de grupo do host não devolve paredes (faces em grupos filhos). Agora a parede é achada pelo ponto do cursor na face (`wall_under_cursor`); teste com a janela real. | `wall_opening_place.py` | Opus |
| 2 | **Corrigido em 13/10.** Inserir vértice usa a aresta clicada (antes, a do radial; clicar em outra aresta dava erro). | `wall_opening_edit.py` | Opus |
| 3 | **Corrigido em 13/10.** Vão curvo na parede curva: vetores do Qt são float32; reoffsetar a trajetória picada em milímetros dobrava as faces. Agora os lados são calculados uma vez na trajetória da parede e as estações interpoladas neles. Reproduzido localmente com um shim float32. | `model.py` | Opus |
| 4 | **Feito em 13/10 (código).** Tirar as bolinhas do meio das arestas; vértices como pontos/bolas; aresta clicável pela linha. | `wall_opening_ui.py` (`_draw`, `_hit_active`) | Sonnet |
| 5 | **Conferido e testado em 13/10.** Paleta lateral: Home e Perfis não abriam (a sincronização voltava para a página da parede). Correção em `sync_context` conferida; teste novo `tests_host/test_suite_panel_sync_host.py`. | `suite_panel.py` (`sync_context`) | Sonnet verifica |
| 6 | **Teste novo em 13/10** (os testes do host não rodam fora do CI, então não se sabe se algo falhava). Atualizar teste de fumaça para IngeTrazo 0.5.8 (painéis em abas dos dois lados, extensões carregadas depois da janela). | `tests_host/test_install_smoke_host.py` | Sonnet |
| 7 | **Feito em 13/10** (`DECISIONS.md` + `ARCHITECTURE.md`, 101 linhas; cadernos antigos removidos). Enxugar os cadernos: `docs/DECISIONS.md` (só o que vale hoje: aprovado/descartado/adiado, com data, partindo das decisões de 12/10 no AGENTS.md — onde os cadernos antigos conflitarem, vale o AGENTS.md) e `docs/ARCHITECTURE.md` (módulos e contratos). Remover `INTERFACE_MASTER.md` e `DEVELOPMENT_MASTER.md`; o histórico fica no git. Juntos, menos de 250 linhas. | `docs/` | Sonnet |

## Estado do CI (13/10)

- Tudo verde (run 38348746501); pacote TEST-8 publicado. Testes do host rodam um arquivo por processo (várias MainWindow no mesmo processo derrubam o PySide).

## Depois
- Portas e janelas: ferramenta própria, segundo clique para lado/giro, tamanhos editáveis na barra.
- Interface (bloco visual): tema, ícones legíveis, paleta que mostre tudo, comportamento das abas no 0.5.8.
