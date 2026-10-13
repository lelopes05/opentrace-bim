# Próximos passos

Branch: `claude/b1-curved-wall-perf`. Último pacote entregue: TEST-8 (13/10). Etapas 2 e 3 em `claude/interface-etapa-2-3`.

## Feito em 13/10
- Vãos na parede (TEST-7): parede achada pelo cursor (`wall_under_cursor`), inserir vértice na aresta clicada, malha do vão curvo em parede curva (float32), vértices como pontos sem bolinha no meio, Home e Perfis da paleta voltando a abrir, teste de fumaça do 0.5.8, cadernos enxutos (`DECISIONS.md`, `ARCHITECTURE.md`).
- Botões de criar abertura, porta, janela e vão livre saíram da paleta radial da parede. Criar vão passa a ser só pelas ferramentas do bloco abaixo.
- Etapa 1 do bloco de interface feita (aguarda o teste do Leandro): Abertura, Porta e Janela são ferramentas do host (`WallOpeningTool`, chaves `opentrace_wall_opening_tool`, `..._door_tool`, `..._window_tool`), no menu "Ferramentas arquitetônicas ▸ Vãos" e em "Criar ▸ Vãos e esquadrias". Saíram os botões da toolbar antiga, os métodos que iniciavam vão e o bloco da Home. As páginas `opening`, `door` e `window` da barra ficam vazias até a etapa 3.
- CI verde (run 38348746501). Os testes do host rodam um arquivo por processo.
- Etapas 2 e 3 do bloco de interface na branch `claude/interface-etapa-2-3`. Mudança de rumo do Leandro (13/10): fileira e barra de opções são painéis flutuantes sobre a vista (`viewport_overlay.OverlayDock`), não toolbars do host. A janela "Escolher Template de Layers" abre sem timer e sem `exec()`, pelo sinal `glReady` do host. Job de teste do CI com `timeout-minutes: 25`.

---

## Bloco de interface (próximo, para o Sonnet)

Siga as etapas na ordem. Cada etapa é um commit (ou poucos) na branch, com CI verde antes da próxima. Não decida nada que não esteja aqui. Se faltar algo, pare e pergunte. As perguntas abertas estão no fim e indicam a etapa que bloqueiam.

### Regras do bloco
- **Ferramenta:** QAction checável no `_tool_group` do host, registrada com `register_tool(app, tool, action, key)`. Fica no menu "Ferramentas arquitetônicas" (`app.add_menu`) e na fileira. O F3 do host acha sozinho as ações do menu e das toolbars (`views/command_search.py`); a ação precisa de texto e de `parent` igual a `app.window`.
- **Só a fileira e o menu escolhem ferramenta.** A barra de opções e a paleta lateral nunca chamam `activate_tool`, `action.trigger()` ou `start_*`. A exceção é Esc/Selecionar, que o host já faz.
- **Fonte única:** o valor mora em um lugar só (campo do controlador, ou `tool.sizes` nas ferramentas de vão). A barra e a paleta espelham esse valor; editar num lado atualiza o outro.
- **Textos:** todo texto passa por `i18n.t()`, com entrada em `i18n.py` para inglês e espanhol.
- **Código:** sem `QTimer` para "consertar" ordem de partida, sem try/except mudo e sem código morto. O que sair, sai inteiro, com os chamadores.
- **CI e aceite:** CI verde não aprova visual. Toda etapa com mudança visível termina com o pacote de teste e itens na Caixa de Revisão para o Leandro.

### Etapa 1 — Abertura, Porta e Janela viram ferramentas de verdade
**Arquivos:** `wall_opening_place.py`, `wall_opening_ui.py`, `ui.py`, `contextual_bar.py`, `suite_panel.py`, `workspace_menu.py`, `i18n.py`, `tests_host/test_wall_openings_host.py`, `tests_host/test_install_smoke_host.py`.

**O que muda:**

*Classe nova `WallOpeningTool(Tool)` em `wall_opening_place.py`:*
- Atributo `shape` ∈ `"rect" | "square" | "circle" | "free"`; padrão `"rect"`.
- Tem uma `PlaceWallOpeningTool` (kind = shape) para rect/square/circle e uma `DrawWallOpeningTool` para free.
- Repassa à ferramenta da forma atual todos os ganchos públicos de `tools.base.Tool`.
- `set_shape(shape)` com a ferramenta ativa desativa a interna antiga e ativa a nova, no mesmo viewport. Não troca a ferramenta do host.
- **Memória da sessão (resposta de 13/10):**
  - Toda ferramenta reabre com a última forma, as últimas medidas e a última âncora usadas na sessão. Isso fica só em atributos da ferramenta; nada vai para arquivo ou preferência.
  - Cada objeto colocado guarda as próprias medidas no seu registro (já é assim). Editar um vão selecionado muda só aquele vão, nunca as medidas da ferramenta nem os outros vãos.
- **Sem atalho de teclado** (resposta de 13/10): as ações não recebem `setShortcut`.

*Chaves e ações (`wall_opening_ui.WallOpeningEditor`):*
- Registra três chaves:
  - `opentrace_wall_opening_tool` → `WallOpeningTool`
  - `opentrace_wall_door_tool` → `PlaceWallOpeningTool` com kind fixo `"door"`
  - `opentrace_wall_window_tool` → `PlaceWallOpeningTool` com kind fixo `"window"`
- Cada chave ganha uma `QAction` checável, com estes textos e dicas:
  - "Abertura": "Abertura na parede: passe sobre a parede e clique."
  - "Porta": "Porta: passe sobre a parede e clique."
  - "Janela": "Janela: passe sobre a parede e clique."
- As três ações entram no menu "Ferramentas arquitetônicas", num submenu "Vãos".
- A âncora de porta e janela passa a ser atributo da ferramenta (`tool.anchor`, padrão `"center"`), não argumento de ativação.

*O que sai:*
- Saem as chaves `opentrace_wall_opening_place` e `opentrace_wall_opening_draw`.
- Saem `begin_place` e `begin_draw` do editor, e `begin_hosted_fill` e `begin_wall_polygon_from_toolbar` do `WallController`.
- No `ui.py` sai todo o bloco `opening_toolbar_*` e os botões de porta e janela da toolbar antiga.
- Na barra, saem os `_method` que iniciam vão (páginas `idle`, `opening`, `door`, `window`). As páginas `opening`, `door` e `window` ficam vazias até a etapa 3.
- Na Home da paleta, sai o bloco "Vãos e esquadrias".

*Outros ajustes:*
- `workspace_menu.py` usa as três QActions novas, sem criar ações próprias.
- `contextual_bar._context_key` devolve `"opening"`, `"door"` ou `"window"` pela ferramenta ativa (comparação por identidade com as três ferramentas).
- Depois de colocar, a ferramenta continua ativa e o vão novo fica selecionado (comportamento atual).

**Testes que provam:**
- `test_opening_tools_are_host_tools`:
  - As três chaves estão em `window._tools`, com a ação em `window._tool_actions` e no `_tool_group`.
  - `activate_tool(app, chave)` deixa a ação marcada.
- `test_opening_tools_are_in_menu_and_f3`: `views.command_search.commands(window)` tem "Abertura", "Porta" e "Janela" com caminho no menu "Ferramentas arquitetônicas".
- `test_opening_shape_change_keeps_host_tool`:
  - Com a Abertura ativa, `set_shape` passa por square, circle, free e rect.
  - A ferramenta ativa do viewport continua a mesma `WallOpeningTool`.
  - A interna recebe `on_activate` e `on_deactivate` uma vez por troca.
- `test_each_opening_tool_places_on_real_wall` (janela real, clique simulado na face):
  - rect, square e circle geram o registro esperado (square e rect com `kind="rect"`, circle com 4 arcos).
  - Porta e janela geram vão mais grupo ligado por `source_id`.
  - Tudo num único Desfazer.
- `test_no_widget_outside_toolrow_and_menu_starts_an_opening`: nenhum atributo `begin_hosted_fill`, `begin_wall_polygon_from_toolbar`, `opening_toolbar_action` ou `opening_btn` existe.
- O teste de fumaça continua verde.

**Caixa de Revisão da etapa 1 (Leandro, no Windows):**
- Menu Ferramentas arquitetônicas ▸ Vãos mostra Abertura, Porta e Janela; as três aparecem marcadas quando ativas.
- F3 acha "Abertura", "Porta" e "Janela".
- Passar sobre uma parede mostra o vão sob o cursor; um clique coloca e a ferramenta continua ativa com o vão novo selecionado.
- Um Desfazer remove porta ou janela junto com o vão.
- Não sobrou botão de Abertura, Porta ou Janela na toolbar antiga, na Home da paleta nem na barra de opções.
- Ainda sem como trocar a forma (quadrada, circular, livre) e a âncora pela interface: vem na etapa 3.

### Etapa 2 — Fileira de ferramentas e barra de opções, painéis flutuantes sobre a vista
**Decisão do Leandro, 13/10.** A fileira e a barra de opções não são toolbars do IngeTrazo. São painéis sobre a vista 3D, no canto superior esquerdo, como a barra do plugin ArchXQ. O host reaplica o layout salvo (`load_extensions` → `restoreState` → `_pack_toolbars`) e põe toda toolbar que não conhece na linha das dele; trocar o `objectName` não resolveu (provado no CI). Um painel filho do viewport fica fora desse mecanismo.

**Arquivos:** `viewport_overlay.py` (novo), `tool_row.py` (novo), `__init__.py`, `ui.py`, `slab_ui.py`, `column_ui.py`, `beam_ui.py`, `contextual_bar.py`, `layer_combinations/__init__.py`, `.github/workflows/claude-branches.yml`, `i18n.py`, `tests_host/test_tool_row_host.py` (novo), `tests_host/test_tool_row_layout_host.py` (novo), `tests_host/test_startup_tabs_host.py` (novo).

**O que muda:**

*Os painéis (`viewport_overlay.OverlayDock`):*
- `QWidget` filho de `app.viewport`, com `QVBoxLayout`: fileira em cima, barra de opções embaixo. Fica a 8 px do canto superior esquerdo.
- Um `eventFilter` no viewport reage a `QEvent.Resize` e chama `adjustSize()` e `move()`. Sem `QTimer`. Largura máxima: largura do viewport menos 16 px.
- Clique, roda e arrasto sobre um painel ficam no painel (`WA_NoMousePropagation`) e não chegam à ferramenta do viewport.
- Visual: cada painel é um `QFrame` com `WA_StyledBackground`, raio de 8 px, cores de `palette()` no stylesheet. Nenhum `#rrggbb` novo (a etapa 6 troca por tokens).

*A fileira (`tool_row.ToolRow`, um `QFrame`):*
- Contém uma `QToolBar` simples, filha do frame e nunca entregue a `window.addToolBar`. Ela dá o botão » quando falta espaço.
- Conteúdo, nesta ordem:
  - Parede: o `wall_menu_button` atual (simples ou composta).
  - Laje, Pilar e Viga: as `action` existentes de cada controlador.
  - Um separador.
  - Abertura, Porta e Janela: as ações da etapa 1.
  - Um separador.
  - Perfil complexo: a `QAction` do controlador de perfis ("Perfil Complexo…").
- A fileira só referencia as QActions; não cria ações novas. Membrana entra quando a ferramenta estiver pronta.
- Ícone com o nome ao lado (`Qt.ToolButtonTextBesideIcon`).
- Botão ▴/▾ alterna entre normal (ícone de 24 px com nome) e compacta (só ícones, 16 px, nome na dica). O estado fica em `QSettings`, chave `OpenTrace_BIM/tool_row_compact`, e é lido na partida.

*A barra de opções (`ContextualBar`, um `QFrame` no mesmo `OverlayDock`):*
- Mantém o ▴ para recolher. Seu conteúdo é o da etapa 3.

*O que sai:*
- A `QToolBar` `wall.toolbar` (`opentrace_options_toolbar`) e a `opentrace_tools_toolbar`, com o grip de redimensionar.
- Todo `insertToolBarBreak`, `insertToolBar` e `toggleViewAction` da barra. Nada no plugin chama `window.addToolBar` para a fileira ou a barra.
- As ações continuam no menu "Ferramentas arquitetônicas", e o F3 as acha.

*Abas duplicadas na partida (achado de 13/10):*
- A janela "Escolher Template de Layers" é do plugin (`layer_combinations/__init__.py`). Abria com `QTimer.singleShot(0, ...)` e `dlg.exec()`, e prendia o CI em `in_progress`.
- Agora: sem `QTimer`; `open()` não bloqueante; abre a partir do sinal `viewport.glReady` do host (ou na hora, se o viewport já estiver pronto).
- O job de teste do CI tem `timeout-minutes: 25`.

**Testes que provam:**
- `test_panels_are_not_host_toolbars`: toda `QToolBar` dos painéis tem `toolBarArea == NoToolBarArea`; `saveState()` não contém `opentrace_`.
- `test_panels_stacked_top_left_inside_viewport`: o `y` da fileira é menor que o da barra, as duas estão dentro do viewport, `x == 8`.
- `test_panels_follow_viewport_resize`: ao estreitar a janela os painéis ficam dentro do viewport e a fileira mostra o botão de extensão.
- `test_old_saved_layout_does_not_move_panels`: com `arquitetura_parametrica_toolbar` na linha do host em `ui/window_state`, os painéis ficam no lugar e as toolbars do host ficam como numa janela sem o plugin.
- `test_click_on_panel_does_not_reach_tool`: um clique num painel não chama `on_mouse_press` da ferramenta ativa.
- `test_no_stray_tab_bar_at_startup_with_real_plugin`: plugin real, sem `patch`, sem travar.
- `test_tool_row_order`, `test_tool_row_actions_activate_tools`, `test_tool_row_compact`, `test_panels_survive_restore_state`.

### Etapa 3 — Barra de opções da ferramenta ativa
**Arquivos:** `contextual_bar.py`, `wall_opening_place.py`, `wall_tool.py`, `ui.py`, `host.py` (sai `activate_curved_wall` e a chave `CURVED_WALL_TOOL_KEY`), `workspace_menu.py`, `suite_panel.py`, `i18n.py`, `tests_host/test_contextual_bar_host.py` (novo).

**O que muda:**

*Página "Abertura" (chave `opening`):*
- **Forma:** grupo exclusivo de 4 botões de ícone (ícones da etapa 7; até lá, os símbolos ▭ □ ◯ ⬡), com dica "Retangular", "Quadrada", "Circular" e "Livre". O clique chama `opening_tool.set_shape`. A forma marcada segue `opening_tool.shape`.
- **Campos:** `QDoubleSpinBox` em metros, 2 casas, mínimo `model.MIN_DIM`, máximo 100.
  - Largura, Altura e Peitoril editam `tool.sizes[shape]` (fonte única).
  - Em Quadrada, Altura fica desabilitada e mostra a Largura; Largura grava largura e altura.
  - Em Circular, o rótulo de Largura vira "Diâmetro" e Altura fica desabilitada da mesma forma.
  - Em Livre, os três campos ficam desabilitados, porque a forma vem dos cliques.

*Páginas "Porta" e "Janela" (chaves `door` e `window`):*
- Largura, Altura e Peitoril em `tool.sizes[kind]`.
- **Âncora:** grupo exclusivo de 3 botões (esquerda, centro, direita) que grava `tool.anchor`.

*Comportamento:*
- Mudar um valor redesenha a prévia no viewport (`viewport.update()`), sem trocar de ferramenta.
- Digitar a distância no viewport continua como hoje.
- Os valores iniciais são os `PRESETS` atuais (confirmados em 13/10). Depois, valem os últimos usados na sessão (etapa 1).
- Com um vão selecionado (página `opening_edit`), os campos editam aquele vão, por comando desfazível, e não tocam as medidas da ferramenta.

*Remover chamadas que escolhem ferramenta:*
- Na página `idle`: "Criar parede", "Criar laje" e "Criar abertura".
- Na página `wall`: "Parede curva: arco". Na página `wall_curve`: "Voltar à parede reta". Eles saem junto com a mudança abaixo.

*Parede reta e curva numa ferramenta só (resposta de 13/10, como o Archicad):*
- **Ferramenta única:** classe nova `WallDrawTool(Tool)` em `wall_tool.py`, no mesmo padrão da `WallOpeningTool` da etapa 1.
  - Contém a ferramenta reta atual (`wall.tool`) e a curva (`wall.curve_create_tool`).
  - Tem o atributo `geometry`, com os valores `single`, `rect_diagonal`, `rect_base_width`, `arc_normal`, `arc_center` e `arc_three`, e repassa os ganchos à ferramenta interna da geometria atual.
- **Registro:** a ação Parede (`wall.action`) passa a ativar a `WallDrawTool`. As ferramentas internas deixam de ser registradas no host.
- **Uma página na barra:** a página `wall` mostra os seis métodos num grupo só, "Geometria". O clique chama `set_geometry`, que troca a interna sem trocar a ferramenta do host. A página `wall_curve` deixa de existir, e `_context_key` devolve `wall`.
- **Menus:** `wall.curve_action` sai da setinha do botão Parede, do menu e da paleta. A setinha fica só com Simples e Composta.
- **Memória:** a última geometria usada na sessão vale ao reabrir a Parede (etapa 1).

**Testes que provam:**
- `test_bar_page_follows_active_tool`: ativar cada ferramenta pela ação mostra a página `opening`, `door` ou `window`.
- `test_bar_never_changes_tool`:
  - Com cada ferramenta de vão ativa, clicar em todo botão e mudar todo campo da página atual mantém `viewport.active_tool`.
  - Mesma verificação com `activate_tool` substituído por uma função que falha o teste.
- `test_opening_fields_are_the_tool_sizes`: mudar Largura na barra muda `tool.sizes[shape]["width"]`, e mudar `tool.sizes` atualiza o campo depois de `refresh()`.
- `test_square_and_circle_lock_height`:
  - Em square e circle, Altura está desabilitada e igual à Largura.
  - O vão colocado tem largura igual à altura.
- `test_free_shape_disables_fields`.
- `test_wall_geometry_changes_without_changing_tool`:
  - Com a Parede ativa, passar pelas seis geometrias mantém a mesma `viewport.active_tool`.
  - Uma parede desenhada em `arc_three` sai curva, e uma em `single` sai reta.
- `test_no_curve_wall_action_left`: `curve_action` não está em nenhum menu, botão ou página.
- `test_door_anchor_from_bar`: âncora "esquerda" na barra produz o grupo com âncora esquerda ao colocar.

### Etapa 4 — Paleta lateral sem escolha de ferramenta
**Arquivos:** `suite_panel.py`, `i18n.py`, `tests_host/test_suite_panel_sync_host.py`.

**O que muda:**
- `user_show_page` só mostra a página; sai a chamada a `_activate_default` (e o método, se ninguém mais o usar).
- Os botões de modo da página (`_trigger_mode`) só valem com a ferramenta daquela página já ativa. Fora dela, ficam desabilitados com a dica "Ative a ferramenta na fileira do topo." Escolher um modo não pode ativar a ferramenta.
- **Topo da paleta:** com uma ferramenta ativa ou um objeto selecionado, a página dele abre com as configurações completas expandidas. Com Abertura, Porta ou Janela ativa, a página `wall` mostra uma seção "Vão" que espelha os mesmos campos da barra (fonte única: `tool.sizes`).
- **Home (resposta de 13/10):**
  - Os blocos vêm de uma tabela `HOME_SECTIONS`, nesta ordem: Plantas, Vistas, Configurações, Projeto e organização.
  - Cada entrada tem título, chave de página e ícone. Entrada sem página (`page=None`) não aparece.
  - Plantas e Vistas entram hoje com `page=None`. Na etapa 05 basta ligar a página delas.
  - "Configurações" (antigo "Criar elementos") abre as páginas Parede, Laje, Pilar e Viga sem ativar ferramenta.
  - "Projeto e organização" continua igual.
- `sync_context` continua com as regras atuais (não sai de `bim`, `project` ou `arrange`, nem desfaz a escolha do usuário).

**Testes que provam:**
- `test_palette_never_activates_a_tool`: para toda página e todo botão visível, clicar mantém `viewport.active_tool`. É o mesmo padrão do teste da barra.
- `test_mode_buttons_disabled_without_their_tool`.
- `test_active_tool_opens_its_settings_on_top`: com a Abertura ativa, a página atual é `wall` e a seção "Vão" está visível e expandida.
- `test_palette_and_bar_share_opening_sizes`: mudar a Largura na paleta muda a da barra.
- `test_home_hides_sections_without_page`:
  - Plantas e Vistas estão em `HOME_SECTIONS` e não aparecem na Home.
  - Trocar `page` de uma delas para uma página existente faz a seção aparecer na próxima montagem.
- Os testes atuais de `sync_context` continuam verdes.

### Etapa 5 — Partida e abas no IngeTrazo 0.5.8
**Arquivos:** `__init__.py`, `suite_panel.py`, `tests_host/test_install_smoke_host.py`.

**O que muda:**
- `setup` funciona com a janela já na tela (`MainWindow(defer_extensions=True)` e depois `load_extensions()`).
- Sem `QTimer` de partida e sem `addDockWidget` próprio. A posição do dock é do host (`add_panel`), que lembra o lado e a aba escolhidos.
- A paleta funciona igual no tray esquerdo e no direito: sem largura, lado ou área fixos no código. Hoje o `__init__.py` cria o dock mestre; confira que nenhum controlador chama `setAllowedAreas` ou `addDockWidget`.

**Testes que provam:**
- `test_deferred_setup_builds_tool_row_and_bar`: com `defer_extensions=True` e `show()` antes de `load_extensions()`, a fileira e a barra existem como painéis sobre a vista, na ordem da etapa 2.
- `test_sidebar_works_in_left_tray`:
  - Mover o dock mestre para `LeftDockWidgetArea` (como o usuário faria) e ativar a Abertura abre a seção "Vão".
  - `sync_context` continua funcionando.
- `test_sidebar_is_a_tab_next_to_host_panels`: `window.tabifiedDockWidgets(dock)` não é vazio, como no teste atual de 0.5.8.
- `test_restart_keeps_layout`: `saveState` numa janela e `restoreState` em outra (processos separados, se necessário) mantêm o lado do dock.

### Etapa 6 — Tema legível no escuro e no claro
**Arquivos:** `style.py` (novo), `suite_panel.py`, `contextual_bar.py`, `palette.py`, `ui.py` e os outros `*_ui.py` que tenham `setStyleSheet` com cor fixa, `tests/test_style_contrast.py` (novo, puro), `tests_host/test_theme_host.py` (novo).

**O que muda:**

*`style.py`:*
- `tokens(palette)` deriva as cores da `QPalette` do app: texto, texto suave, fundo, fundo de campo, borda e erro. Usa `palette.color(...)` e não depende de `views.theme`, que não é API pública de plugin.
- **Cores de destaque (resposta de 13/10, "mistura 1"):**

  | Token | Onde | Escuro | Claro |
  |---|---|---|---|
  | `tool` (petróleo) | fundo da ferramenta ativa na fileira | `#3A7780`, texto `#FFFFFF` | `#2F6670`, texto `#FFFFFF` |
  | `mark` (laranja) | borda e ícone da opção marcada na barra, faixa da seção aberta na paleta | `#F0A36B` | `#B35C22` |

  Ficam só em `style.py`. Se algum par não passar no teste de contraste, o teste falha e a cor é escurecida ou clareada no mesmo tom (mesma matiz) até passar, sem trocar de cor.
- `apply(widget, template)` aplica `template.format(**tokens)`, guarda o widget e reaplica no `QEvent.ApplicationPaletteChange`. Um filtro de eventos só no `QApplication` faz isso.

*Uso:*
- Toda cor fixa em stylesheet dos módulos da interface vira token. Há cerca de 30 hoje: `rg "#[0-9a-fA-F]{6}"` nos arquivos de interface.
- Cor fixa só fica em `style.py` e `icons.py`.

*Critério de legível:*
- Texto: contraste de pelo menos 4,5:1 contra o fundo (WCAG AA), nas paletas clara e escura do host.
- Ícone e borda de campo: pelo menos 3:1.

**Testes que provam:**
- `tests/test_style_contrast.py` (puro, sem Qt): a função `contrast(a, b)` de `style.py` bate com valores de referência do WCAG (preto/branco = 21).
- `test_tokens_meet_contrast_in_both_themes`: aplica `views.theme.dark_palette()` e `light_palette()` do host no teste e confere os pares texto/fundo e texto suave/fundo (≥ 4,5) e borda/fundo (≥ 3).
- `test_widgets_restyle_on_theme_change`: trocar a paleta muda o stylesheet da barra e da paleta, sem reiniciar.
- `test_no_fixed_colours_outside_style_and_icons`: varre o código-fonte com regex e só aceita `#rrggbb` em `style.py` e `icons.py`.

### Etapa 7 — Ícones claros por ferramenta
**Arquivos:** `icons.py`, `ui.py`, `slab_ui.py`, `column_ui.py`, `beam_ui.py`, `tool_row.py`, `contextual_bar.py`, `tests_host/test_icons_host.py` (novo).

**O que muda:**

*Onde e como:*
- Todos os ícones ficam em `icons.py`, desenhados com `QPainter`. Sem arquivos de imagem e sem base64.
- `wall_icon`, `composite_wall_icon`, `curved_wall_icon`, `slab_icon`, `composite_slab_icon`, `column_icon`, `beam_icon` e `profile_icon` mudam-se para lá, e os módulos importam de lá.

*Ícones novos:*
- `opening` (retângulo vazado na parede), `opening_rect`, `opening_square`, `opening_circle`, `opening_free`.
- `door` (folha com arco de giro em planta) e `window` (caixilho com vidro).
- `anchor_left`, `anchor_center`, `anchor_right`.

*Cores e repintura:*
- A cor sai de `style.tokens`: traço principal com o texto e realce com o destaque.
- A fileira, a barra e a paleta repintam os ícones no `ApplicationPaletteChange`.
- Tamanhos 24 px na fileira e 20 px na barra, com traço mínimo de 1,5 px a 24 px.

**Testes que provam:**
- `test_every_tool_has_its_own_icon`: as ações da fileira e os botões de forma e âncora têm ícone não nulo, e todos os ícones são diferentes entre si (comparando os pixels da imagem a 24 px).
- `test_icons_contrast_in_both_themes`: em cada paleta do host, a média dos pixels opacos do ícone tem contraste ≥ 3:1 com a cor `Window`.
- `test_icons_repaint_on_theme_change`: a imagem do ícone da ação Parede muda ao trocar de escura para clara.

### Etapa 8 — A função de edição escolhida continua ativa
Pedido de 13/10. Pode começar depois da etapa 1; não mexe em `ui.py` nem em `suite_panel.py`.

**Arquivos:** `wall_opening_ui.py`, `wall_opening_edit.py`, `slab_ui.py`, `slab_opening_edit.py`, `tests_host/test_wall_openings_host.py`, `tests_host/test_slab_opening_sticky_host.py` (novo).

**O que muda:**
- Hoje, depois de confirmar uma edição (deslocar, mover vértice, curvar, chanfrar, arredondar, inserir vértice, esticar), a ferramenta volta para Selecionar: `edit_finished` chama `return_to_select`.
- Passa a ser assim: a função escolhida no radial continua ativa depois de confirmar. O próximo clique em qualquer vértice ou aresta do mesmo tipo (de qualquer vão da mesma parede, ou da mesma laje) aplica a mesma função, sem reabrir o radial.
- **Para sair:** Esc, escolher outra função no radial ou na paleta, ou escolher outra ferramenta. Clicar fora de qualquer vão também volta para Selecionar.
- O vão editado continua selecionado depois de cada confirmação.
- Vale para os vãos da parede e para os da laje, com o mesmo código de "função ativa" nos dois.

**Testes que provam:**
- `test_offset_stays_active_after_commit`:
  - Deslocar uma aresta e depois clicar em outra aresta do mesmo vão desloca a segunda sem passar pelo radial.
  - São dois comandos no histórico.
- `test_sticky_function_ends_on_escape_and_on_empty_click`.
- `test_choosing_another_function_replaces_the_sticky_one`.
- O mesmo trio para a abertura da laje.

### Fora deste bloco
- O segundo clique de porta e janela (lado e giro) e o desenho da folha ficam no bloco seguinte, "Portas e janelas".
- A barra personalizável pelo usuário está adiada (DECISIONS).
- Plantas e Vistas: ficam para a etapa 05 do roteiro; a Home já tem o lugar delas (etapa 4).
- Membrana na fileira: quando a ferramenta estiver pronta.

### Respondidas em 13/10
- **Medidas:**
  - Cada objeto guarda as suas.
  - A ferramenta lembra as últimas usadas na sessão.
  - Editar um objeto não muda a ferramenta.
- **Forma e função:** toda ferramenta e toda função de edição continuam na última escolha da sessão (etapas 1 e 8).
- **Atalhos:** nenhum.
- **Fileira:**
  - Perfil complexo entra e abre o editor de perfis.
  - Membrana entra quando estiver pronta.
- **Home:** Plantas e Vistas previstas, escondidas até existirem.
- **Recolher a fileira:** ela fica compacta, só com ícones; não some.
- **Parede curva:** é geometria da Parede, escolhida na barra (etapa 3).
- **Botões da fileira:** ícone com o nome ao lado.
- **Cor de destaque:** petróleo na ferramenta ativa e laranja na opção marcada (etapa 6).
- **Medidas iniciais:** as atuais servem para começar.

### Perguntas abertas
Nenhuma.

---

## Depois
- Portas e janelas: segundo clique para lado e giro, folha e marco, tamanhos editáveis na barra (já preparados na etapa 3).
