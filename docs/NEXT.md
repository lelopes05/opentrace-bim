# Próximos passos

Branch: `claude/b1-curved-wall-perf`. Último pacote testado pelo Leandro: TEST-7.

## Bloco atual — vãos na parede (correções do teste TEST-7)

| # | Problema | Onde | Quem |
|---|---|---|---|
| 1 | Botões de criar vão (barra de cima e paleta lateral) não funcionam no Windows. Nos testes a ferramenta funciona; suspeita: `wall_under_cursor` → `viewport.pick_group` devolve outro grupo (corpo da parede) ou nada no host real. Reproduzir com MainWindow real. | `wall_opening_place.py`, `wall_opening_ui.py` | Opus |
| 2 | "Inserir vértice" dá erro no Windows ("afastado das extremidades"). Teste simulado passa; suspeita: ponto do snap / ímã de eixo. | `wall_opening_edit.py` (`_OnWallFace.point`) | Opus |
| 3 | Malha com falhas em vão curvo na parede curva. Teste `test_curved_wall_round_opening_mesh_is_closed` reproduz. Correção em andamento: estações a menos de 1 mm unidas aos pontos da trajetória (commit WIP, ainda sem CI). Verificar se o polígono reto na parede curva também falha (pode ser anterior). | `model.py` (`_build_body_with_polygon_openings`) | Opus |
| 4 | **Feito em 13/10 (código).** Tirar as bolinhas do meio das arestas; vértices como pontos/bolas; aresta clicável pela linha. | `wall_opening_ui.py` (`_draw`, `_hit_active`) | Sonnet |
| 5 | **Conferido e testado em 13/10.** Paleta lateral: Home e Perfis não abriam (a sincronização voltava para a página da parede). Correção em `sync_context` conferida; teste novo `tests_host/test_suite_panel_sync_host.py`. | `suite_panel.py` (`sync_context`) | Sonnet verifica |
| 6 | **Teste novo em 13/10** (os testes do host não rodam fora do CI, então não se sabe se algo falhava). Atualizar teste de fumaça para IngeTrazo 0.5.8 (painéis em abas dos dois lados, extensões carregadas depois da janela). | `tests_host/test_install_smoke_host.py` | Sonnet |
| 7 | **Feito em 13/10** (`DECISIONS.md` + `ARCHITECTURE.md`, 101 linhas; cadernos antigos removidos). Enxugar os cadernos: `docs/DECISIONS.md` (só o que vale hoje: aprovado/descartado/adiado, com data, partindo das decisões de 12/10 no AGENTS.md — onde os cadernos antigos conflitarem, vale o AGENTS.md) e `docs/ARCHITECTURE.md` (módulos e contratos). Remover `INTERFACE_MASTER.md` e `DEVELOPMENT_MASTER.md`; o histórico fica no git. Juntos, menos de 250 linhas. | `docs/` | Sonnet |

## Estado do CI (envio `4aba901`, 13/10)

- Workflow "Claude branches": o job `test` falhou na etapa de testes do host com saída 139 (travamento do processo). Não há anotação com o nome do teste, então o teste exato não foi identificado. Testes puros: passaram. Benchmark e pacote: não rodaram, **sem pacote de teste**.
- Antes dos itens 4 a 7, o mesmo job falhava só em `test_curved_wall_round_opening_mesh_is_closed` (item 3, malha de vão curvo), sem travar.
- Suspeitos do travamento: os dois testes novos, `test_setup_after_window_is_shown_puts_the_sidebar_in_the_side_tray` (janela mostrada, extensões depois) e `test_home_and_profiles_stay_open_while_a_wall_stays_selected`. Próximo passo: isolar rodando cada um sozinho no CI.

## Depois
- Portas e janelas: ferramenta própria, segundo clique para lado/giro, tamanhos editáveis na barra.
- Interface (bloco visual): tema, ícones legíveis, paleta que mostre tudo, comportamento das abas no 0.5.8.
