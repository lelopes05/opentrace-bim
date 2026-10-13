# Próximos passos

Branch: `claude/b1-curved-wall-perf`. Último pacote entregue: TEST-8 (13/10).

## Feito em 13/10
- Vãos na parede (TEST-7): parede achada pelo cursor (`wall_under_cursor`), inserir vértice na aresta clicada, malha do vão curvo em parede curva (float32), vértices como pontos sem bolinha no meio, Home e Perfis da paleta voltando a abrir, teste de fumaça do 0.5.8, cadernos enxutos (`DECISIONS.md`, `ARCHITECTURE.md`).
- Botões de criar abertura, porta, janela e vão livre saíram da paleta radial da parede. Criar vão passa a ser só pelas ferramentas do bloco abaixo.
- CI verde (run 38348746501). Os testes do host rodam um arquivo por processo.

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

### Etapa 2 — Fileira de ferramentas fixa no topo
**Arquivos:** `tool_row.py` (novo), `__init__.py`, `ui.py`, `slab_ui.py`, `column_ui.py`, `beam_ui.py`, `contextual_bar.py`, `i18n.py`, `tests_host/test_tool_row_host.py` (novo).

**O que muda:**

*A fileira:*
- `tool_row.ToolRow` cria uma `QToolBar` com `objectName "opentrace_tools_toolbar"` e título `t("OpenTrace BIM · Ferramentas")`.
- Conteúdo, nesta ordem:
  - Parede: o `wall_menu_button` atual, sem mudar o menu dele. É um `QToolButton` com a ação Parede e a seta (simples, composta, curva).
  - Laje, Pilar e Viga: as `action` existentes de cada controlador.
  - Um separador.
  - Abertura, Porta e Janela: as ações da etapa 1.
- A fileira só referencia as QActions; não cria ações novas. Membrana e Perfis não entram (ver P6).
- Estilo do botão: o da janela (`window.toolButtonStyle()`), até a resposta de P1.

*Posição:*
- Linha própria, abaixo das toolbars do host e acima da barra de opções.
- Se `window.toolBarBreak` ainda não tiver quebra, insere `insertToolBarBreak` antes da fileira e antes da toolbar da barra (`wall.toolbar`).
- A fileira entra com `window.insertToolBar(wall.toolbar, fileira)`.
- `setMovable(False)` e `setFloatable(False)`, como a barra.

*Recolher:*
- Pelo `toggleViewAction()` da fileira, posto no menu "Ferramentas arquitetônicas". Também aparece no F3, em "Toolbars".
- O estado é salvo pelo `saveState` do host, via `objectName`. Não salvar à parte.

*Limpeza:*
- `__init__.setup` cria a `ToolRow` depois dos controladores e antes do `ArchitectureSuitePanel`.
- `ContextualBar` deixa de esconder ações antigas da `wall.toolbar` (`hidden_legacy_actions` sai), porque a etapa 1 já tirou o conteúdo antigo. A `wall.toolbar` passa a conter só a barra.
- `ui.py` deixa de pôr `wall.toolbar.toggleViewAction()` no menu. O recolher da barra continua sendo o ▴ dela.

**Testes que provam:**
- `test_tool_row_order`: os textos das ações da fileira, na ordem, são Parede, Laje, Pilar, Viga, separador, Abertura, Porta, Janela.
- `test_tool_row_is_its_own_line_above_the_bar`:
  - `window.toolBarBreak(fileira)` e `window.toolBarBreak(wall.toolbar)` são verdadeiros.
  - O `y` da fileira é menor que o da barra, e o de qualquer toolbar do host é menor que o da fileira (offscreen, depois de `show` e `processEvents`).
- `test_tool_row_actions_activate_tools`: `trigger()` em cada ação deixa ativa a ferramenta da chave dela.
- `test_tool_row_collapses`:
  - O `toggleViewAction` esconde e mostra a fileira.
  - A ação está no menu "Ferramentas arquitetônicas".
- `test_tool_row_survives_restore_state`: `saveState`, depois `restoreState`, mantém a fileira na mesma linha e na mesma ordem.

### Etapa 3 — Barra de opções da ferramenta ativa
**Arquivos:** `contextual_bar.py`, `wall_opening_place.py`, `suite_panel.py`, `i18n.py`, `tests_host/test_contextual_bar_host.py` (novo).

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
- Os valores iniciais são os `PRESETS` atuais (ver P10).

*Remover chamadas que escolhem ferramenta:*
- Na página `idle`: "Criar parede", "Criar laje" e "Criar abertura".
- Na página `wall`: "Parede curva: arco". Na página `wall_curve`: "Voltar à parede reta". Isso fica pendente de P7; enquanto P7 não for respondida, esses dois ficam.

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
- `test_door_anchor_from_bar`: âncora "esquerda" na barra produz o grupo com âncora esquerda ao colocar.

### Etapa 4 — Paleta lateral sem escolha de ferramenta
**Arquivos:** `suite_panel.py`, `i18n.py`, `tests_host/test_suite_panel_sync_host.py`.

**O que muda:**
- `user_show_page` só mostra a página; sai a chamada a `_activate_default` (e o método, se ninguém mais o usar).
- Os botões de modo da página (`_trigger_mode`) só valem com a ferramenta daquela página já ativa. Fora dela, ficam desabilitados com a dica "Ative a ferramenta na fileira do topo." Escolher um modo não pode ativar a ferramenta.
- **Topo da paleta:** com uma ferramenta ativa ou um objeto selecionado, a página dele abre com as configurações completas expandidas. Com Abertura, Porta ou Janela ativa, a página `wall` mostra uma seção "Vão" que espelha os mesmos campos da barra (fonte única: `tool.sizes`).
- **Home:**
  - O bloco "Criar elementos" vira "Configurações" e abre as páginas Parede, Laje, Pilar e Viga sem ativar ferramenta.
  - "Projeto e organização" continua igual.
  - Plantas e Vistas não aparecem enquanto não existirem: a etapa 05 do roteiro e a regra de 09/10 dizem que nada é anunciado antes de existir. Ver P8.
- `sync_context` continua com as regras atuais (não sai de `bim`, `project` ou `arrange`, nem desfaz a escolha do usuário).

**Testes que provam:**
- `test_palette_never_activates_a_tool`: para toda página e todo botão visível, clicar mantém `viewport.active_tool`. É o mesmo padrão do teste da barra.
- `test_mode_buttons_disabled_without_their_tool`.
- `test_active_tool_opens_its_settings_on_top`: com a Abertura ativa, a página atual é `wall` e a seção "Vão" está visível e expandida.
- `test_palette_and_bar_share_opening_sizes`: mudar a Largura na paleta muda a da barra.
- Os testes atuais de `sync_context` continuam verdes.

### Etapa 5 — Partida e abas no IngeTrazo 0.5.8
**Arquivos:** `__init__.py`, `suite_panel.py`, `tests_host/test_install_smoke_host.py`.

**O que muda:**
- `setup` funciona com a janela já na tela (`MainWindow(defer_extensions=True)` e depois `load_extensions()`).
- Sem `QTimer` de partida e sem `addDockWidget` próprio. A posição do dock é do host (`add_panel`), que lembra o lado e a aba escolhidos.
- As toolbars novas (fileira e barra) são postas pelo `restoreState` que o host reaplica quando aparecem toolbars de extensão. Nada no plugin move toolbars depois da partida.
- A paleta funciona igual no tray esquerdo e no direito: sem largura, lado ou área fixos no código. Hoje o `__init__.py` cria o dock mestre; confira que nenhum controlador chama `setAllowedAreas` ou `addDockWidget`.

**Testes que provam:**
- `test_deferred_setup_builds_tool_row_and_bar`: com `defer_extensions=True` e `show()` antes de `load_extensions()`, a fileira e a barra existem, em linhas próprias e na ordem da etapa 2.
- `test_sidebar_works_in_left_tray`:
  - Mover o dock mestre para `LeftDockWidgetArea` (como o usuário faria) e ativar a Abertura abre a seção "Vão".
  - `sync_context` continua funcionando.
- `test_sidebar_is_a_tab_next_to_host_panels`: `window.tabifiedDockWidgets(dock)` não é vazio, como no teste atual de 0.5.8.
- `test_restart_keeps_layout`: `saveState` numa janela e `restoreState` em outra (processos separados, se necessário) mantêm o lado do dock e a ordem das toolbars.

### Etapa 6 — Tema legível no escuro e no claro
**Arquivos:** `style.py` (novo), `suite_panel.py`, `contextual_bar.py`, `palette.py`, `ui.py` e os outros `*_ui.py` que tenham `setStyleSheet` com cor fixa, `tests/test_style_contrast.py` (novo, puro), `tests_host/test_theme_host.py` (novo).

**O que muda:**

*`style.py`:*
- `tokens(palette)` deriva as cores da `QPalette` do app: texto, texto suave, fundo, fundo de campo, borda, destaque e erro. Usa `palette.color(...)` e não depende de `views.theme`, que não é API pública de plugin.
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

### Fora deste bloco
- O segundo clique de porta e janela (lado e giro) e o desenho da folha ficam no bloco seguinte, "Portas e janelas".
- A barra personalizável pelo usuário está adiada (DECISIONS).
- Plantas e Vistas ficam para a etapa 05 do roteiro.

### Perguntas abertas (respostas na Caixa de Revisão)
- **P1 (etapa 2) Botões da fileira:** só ícone com dica, ícone com o nome ao lado, ou ícone com o nome embaixo?
- **P2 (etapa 2) Recolher a fileira:** basta esconder e mostrar (menu e F3), ou deve existir também um modo compacto, só com ícones?
- **P3 (etapa 3) Medidas da Abertura, Porta e Janela:** quando o usuário muda largura, altura ou peitoril, o valor deve:
  - valer só até fechar o programa;
  - ficar salvo no arquivo do projeto;
  - ficar salvo como preferência do usuário?
- **P4 (etapa 1) Forma ao reabrir a Abertura:** começa sempre em Retangular, ou na última forma usada?
- **P5 (etapa 1) Atalhos de teclado:** as ferramentas novas têm atalho? Se sim, quais? O F3 já está tomado pelo host.
- **P6 (etapa 2) Membrana e Perfis complexos:** entram na fileira ou ficam só no menu?
- **P7 (etapa 3) Parede curva:** é um modo da ferramenta Parede, escolhido na barra (como reta, arco e polígono na Laje), ou uma ferramenta separada na seta do botão Parede (como hoje)? Se for modo, a barra pode trocá-lo sem violar "a barra não troca ferramenta".
- **P8 (etapa 4) Home da paleta:** com Plantas e Vistas ainda inexistentes, a Home fica com "Configurações" e "Projeto e organização", ou deve sumir, abrindo a paleta direto na página do contexto?
- **P9 (etapa 6) Cor de destaque:** a do host (`Highlight` da paleta), ou uma cor própria da marca OpenTrace BIM? Se for própria, qual?
- **P10 (etapa 3) Medidas iniciais:** confirmar os padrões atuais:

  | Tipo | Largura | Altura | Peitoril |
  |---|---|---|---|
  | Abertura retangular | 1,00 | 1,20 | 0,90 |
  | Quadrada | 0,60 lado | — | 1,50 |
  | Circular | 0,60 diâmetro | — | 1,30 |
  | Porta | 0,80 | 2,10 | 0 |
  | Janela | 1,20 | 1,20 | 1,00 |

---

## Depois
- Portas e janelas: segundo clique para lado e giro, folha e marco, tamanhos editáveis na barra (já preparados na etapa 3).
