# Arquitetura

O mapa de arquivos por área está em `AGENTS.md`. Aqui ficam as camadas e os contratos entre elas. Onde conflitar com `AGENTS.md`, vale o `AGENTS.md`.

## Camadas
- **Núcleo puro** (sem Qt, sem host): `wall_polygon`, `opening_profile`, `door_window_core`, `arrange_core`, `architecture_contracts`, `overlay_safety`. Testado em `tests/`, sem IngeTrazo.
- **Modelo**: `model.py` (parede), `slab_model`, `column_model`, `beam_model`. Guardam o registro paramétrico dentro do `Group` e geram a malha.
- **Comandos**: `commands.py`, `door_window_commands.py` e afins. É o único caminho que altera o modelo, sempre pelo histórico (Desfazer e Refazer).
- **Interface Qt**: `ui.py`, `*_ui.py`, `*_tool.py`, `*_edit.py`, `contextual_bar`, `suite_panel`, `palette`.
- **Adaptador do host**: `host.py`.

## Host (IngeTrazo)
- Mínimo 0.5.7 (`MIN_HOST_VERSION` em `host.py`); testado no 0.5.8. Regras do host: `ingelibre/ingetrazo/docs/plugins.md`.
- Só `host.py` toca as coleções privadas da janela (`_tools`, `_tool_actions`, `_tool_group`, `_activate_tool`). O resto usa `register_tool`, `activate_tool`, `host_tool` e `activate_select`.
- API pública usada: `ExtensionApp` (`add_panel`, `show_panel`, `add_overlay`, `add_pickable`).
- `setup()` registra UM dock, `extension_OpenTrace_BIM_parametric_architecture`, antes de criar os controladores. Todos apontam para ele (`window._arquitetura_parametrica_master_dock`) e o conteúdo é trocado depois; a identidade do dock não muda durante a partida.
- No 0.5.8 o app chama `setup` com a janela já na tela (`MainWindow(defer_extensions=True)`); o dock entra como aba do tray. Coberto por `tests_host/test_install_smoke_host.py`.

## Parede
- O registro mora no `Group`: ler com `read_wall(group)` ou `wall_record(group)`, criar com `make_wall_segment`, alterar com `EditWall` e `EditWallPath`.
- Com vãos, a malha costura as junções em T (`_stitch_opening_mesh`) para ficar fechada (manifold). Testes de malha: `tests_host/test_wall_mesh_host.py`.
- `wall_cache` guarda os valores derivados (trajetória, amostras) por `scene.version`. Snaps e overlays leem de `wall_cache.values` e `wall_cache.memo`; quem edita geometria chama o `model` direto.

## Vãos na parede
- Registro do vão: `id`, `source_id` (preenchimento, se houver) e `ifc_global_id`. Retângulo antigo: `position`, `width`, `sill`, `height`. Polígono: pontos na folha (estação ao longo da trajetória × altura) e a especificação de cada aresta (reta ou curva).
- `WallFace` trata a face como folha estação × altura; `world(ponto, lado)` devolve o ponto 3D de uma das faces.
- `wall_opening_edit` adapta à folha as ferramentas da abertura da laje (`slab_opening_edit`). `outline` lê o contorno, `store_outline` devolve o comando que o grava e `execute` o roda no histórico. Cada confirmação é um comando, um Desfazer.
- `wall_opening_ui.WallOpeningEditor`: um clique no contorno seleciona o vão (via `add_pickable`), sem selecionar a parede. Clique em vértice, na linha de uma aresta ou dentro do vão abre o radial `role="edit"`. A tabela `ACTIONS` diz quais ações valem para cada parte (`vertex`, `edge`, `body`) e se valem para porta e janela. A âncora do radial de aresta é o meio da aresta.
- `wall_opening_place` cria os vãos (colocar e desenhar).
- Recuo da parede: o registro persiste; `wall_opening_intervals` corta só a parte que ainda está dentro da parede. Vão totalmente fora não gera corte, mas continua no registro.

## Portas e janelas
- `door_window_core` (puro): especificação, âncoras e giro. `door_window_geometry`: o `Group` 3D (folha, marco, vidro), independente do vão.
- `CreateHostedFill` grava recorte e grupo num único passo de histórico; `EditHostedFill` e `DeleteHostedOpening` seguem a mesma regra. `sync_hosted_fill_placements(scene)` reposiciona o grupo quando a parede muda, sem trocar o `Group`.
- IFC: o preenchimento se liga ao `IfcOpeningElement` por `IfcRelFillsElement`, sem duplicar `IfcDoor` ou `IfcWindow`.

## Interface geral
- `contextual_bar` mostra as opções da ferramenta ativa. Os campos dela espelham os QWidgets do controlador, que continuam sendo a fonte única: o espelho escreve no campo original, e este executa o comando, com validação e histórico.
- `suite_panel` é a paleta lateral, com as páginas `home`, `wall`, `slab`, `column`, `beam`, `membrane`, `profiles`, `bim`, `project` e `arrange`.
- `sync_context` só segue ferramenta ou seleção NOVAS (a assinatura é a ferramenta ativa mais o alvo de cada controlador). Nunca desfaz a página que o usuário escolheu e nunca sai de `bim`, `project` ou `arrange`. Teste: `tests_host/test_suite_panel_sync_host.py`.
- Todo desenho sobre a viewport passa por `overlay_safety.visible_pixel`, que recorta pontos muito distantes e evita artefatos do QPainter.
- `palette.RadialPalette` é o radial compartilhado. Textos em português passam por `i18n.t()`.

## Vistas e representação (contrato, ainda não implementado)
- `architecture_contracts`: uma vista salva guarda câmera, corte, nível, escala e tipo de representação; nunca duplica a geometria. 3D livre usa `simple`; planta, corte e elevação usam `architectural`.
- Cenas e cortes são criados por comandos desfazíveis. Tramas vetoriais dependem de material, camada e escala (`paper` em mm de folha, `model` em metros reais) e só aparecem em vista arquitetônica.

## Testes e CI
- `tests/`: Python puro. `tests_host/`: IngeTrazo real com Qt offscreen, mais `bench_curved_walls.py`.
- `.github/workflows/claude-branches.yml` (branches `claude/**`): compila, roda os testes puros e os do host (as falhas viram anotações do check), compara o benchmark com `BASE_REF` e monta o pacote de teste, com o link como anotação "Download do pacote de teste".
