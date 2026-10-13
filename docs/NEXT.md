# Próximos passos

Branch: `claude/b1-curved-wall-perf`. Último pacote testado pelo Leandro: TEST-7.

## Bloco atual — vãos na parede (correções do teste TEST-7)

| # | Problema | Onde | Quem |
|---|---|---|---|
| 1 | Botões de criar vão (barra de cima e paleta lateral) não funcionam no Windows. Nos testes a ferramenta funciona; suspeita: `wall_under_cursor` → `viewport.pick_group` devolve outro grupo (corpo da parede) ou nada no host real. Reproduzir com MainWindow real. | `wall_opening_place.py`, `wall_opening_ui.py` | Opus |
| 2 | "Inserir vértice" dá erro no Windows ("afastado das extremidades"). Teste simulado passa; suspeita: ponto do snap / ímã de eixo. | `wall_opening_edit.py` (`_OnWallFace.point`) | Opus |
| 3 | Malha com falhas em vão curvo na parede curva. Teste `test_curved_wall_round_opening_mesh_is_closed` reproduz. Correção em andamento: estações a menos de 1 mm unidas aos pontos da trajetória (commit WIP, ainda sem CI). Verificar se o polígono reto na parede curva também falha (pode ser anterior). | `model.py` (`_build_body_with_polygon_openings`) | Opus |
| 4 | Tirar as bolinhas do meio das arestas; vértices como pontos/bolas; aresta clicável pela linha. | `wall_opening_ui.py` (`_draw`, `_hit_active`) | Sonnet |
| 5 | Paleta lateral: Home e Perfis não abriam (a sincronização voltava para a página da parede). Correção feita, sem CI. | `suite_panel.py` (`sync_context`) | Sonnet verifica |
| 6 | Atualizar teste de fumaça para IngeTrazo 0.5.8 (painéis em abas dos dois lados, extensões carregadas depois da janela). | `tests_host/test_install_smoke_host.py` | Sonnet |

## Depois
- Portas e janelas: ferramenta própria, segundo clique para lado/giro, tamanhos editáveis na barra.
- Interface (bloco visual): tema, ícones legíveis, paleta que mostre tudo, comportamento das abas no 0.5.8.
- Enxugar `docs/INTERFACE_MASTER.md` e `docs/DEVELOPMENT_MASTER.md`.
