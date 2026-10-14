# OpenTrace BIM — recuperação da interface, auditoria de 14/10/2026

**Escopo:** `gpt/recupera-interface`. Contratos preservados: `docs/DECISIONS.md`, `docs/DESIGN.md`, PDF **OpenTrace BIM — maquetes.pdf** (11 páginas). Esta auditoria não altera a oficial nem aprova visualmente o produto sem conferência no IngeTrazo Windows.

## Etapas, comprovação e limites

| Etapa | Entrega técnica | Evidência exigida | Status de aceitação |
|---|---|---|---|
| I-B1 | Fileira curta, separadores, ícones 24/16 px, compacto e overflow Qt real | `test_tool_row_host.py`, `test_visual_capture_host.py`; PNGs de fileira | CI verde pré-adendo; revisar prints do Windows |
| I-B2 | Laje: três modos `SlabTool`; presets diretos via catálogo existente nas quatro ferramentas; grupos e campos sem novo motor | `test_contextual_bar_host.py`; PNGs por modo da Laje | Testes automatizados; composição acrescida pede aprovação visual |
| I-B3 | Barra das ferramentas e **página própria de Porta** (criação e edição distintas); F01 conectado somente onde o motor já funciona | `test_suite_panel_sync_host.py`, `test_install_smoke_host.py`; PNGs da Porta | Edição F01 completa permanece pendente |
| I-B4 | Paleta acompanha nova ferramenta/seleção; BIM/Projeto/Organizar não bloqueiam contexto; fixação manual explícita | `test_suite_panel_sync_host.py`; capturas das páginas reais | Requer aceite visual Windows |

O CI executa `tests/` e `tests_host/` no IngeTrazo real. `test_visual_capture_host.py` grava screenshots **reais dos widgets Qt**, isoladamente em `pt-BR` e `en`, sempre com `dark_palette()` e `light_palette()`. O ZIP `OpenTrace-HOST-VISUAL` contém o manifesto e os PNGs. Uma captura de Qt offscreen não substitui o julgamento de legibilidade e densidade no Windows.

## Comparação explícita com as 11 páginas do PDF

| PDF | Contrato da maquete | Composição implementada e comandos reais | Diferença/pêndencia |
|---|---|---|---|
| 1 | Fileira normal, compacta e transbordamento nativo, nos dois temas | `ToolRow` compartilha `QAction` do host e alterna normal/compacta sem alterar ferramentas; ícones vetoriais e separadores | Revisão de alinhamento no Windows |
| 2 | Silhuetas vetoriais e estados normal/hover/ativo/marcado/desabilitado | `icons.icon()`, paleta do host e Design System; testes de distinção e contraste | Conferir aparência real em 16, 20 e 24 px |
| 3 | Parede: Geometria, Referência, Tipo, Espessura/Altura/Base/Topo | `WallController.choose_geometry` e campos existentes; Topo é derivado; Presets abre `preset_catalog` | Presets é acréscimo funcional, aumenta a largura |
| 4 | Laje: Tipo e Medidas (Espessura/Base) | **Adaptação solicitada após a maquete:** `Método [diagonal · base/largura · polígono livre]` → `Tipo` → `Medidas` → `Presets`. Cada opção chama `SlabController.choose_mode` → `SlabTool.set_mode`; os presets aplicam `preset_catalog.apply_preset` | **Pedir aprovação visual desta composição compacta**, inclusive quando a largura é pequena |
| 5 | Pilar: Largura, Profundidade, Altura, Base | Mesmos campos reais; Presets (incorporados/pessoais) diretamente ao lado | Presets não constava na maquete; revisar largura |
| 6 | Viga: referência esquerda/centro/direita, Largura, Altura, Topo | Referência altera apenas o componente horizontal da âncora; Topo é derivado/editável em viga horizontal, somente leitura na curva/inclinada; Presets | Presets é acréscimo; validar legibilidade |
| 7 | Abertura: Forma retangular/quadrada/circular/livre, Medidas | Formas passam à ferramenta de abertura existente; livre desativa medidas; âncora conectada ao estado da ferramenta | Testar com parede real e conferir compactação |
| 8 | Porta: família, largura nominal da folha, altura, âncora, largura do vão de corte (leitura), modo hospedado/livre | Criação própria da Porta F01: dimensões/âncora editam `door_tool.sizes` e `door_tool.anchor`; largura do corte derivada das folgas F01. Uma **página distinta `door_edit`** mostra informações do `_fill_record` real da porta selecionada sem inventar comandos | **Porta livre e orientação no segundo clique desabilitadas/indicadas em desenvolvimento.** Motor atual coloca com um clique; editor F01 completo depende do outro agente. Não fingir suporte |
| 9 | Janela: largura, altura, peitoril, âncora | Valores existentes `window_tool.sizes` e âncora; preservados na barra | Revisão de contraste/espaçamento no Windows |
| 10 | Paleta com Home, configurações e projeto/organização | Todas as páginas e menus existentes preservados; nenhuma categoria disponível foi descartada. Home não impede ativação de ferramenta | Composição do painel lateral não é reprodução literal, depende de aceite visual |
| 11 | Editor com geometria/medidas e organização | Controladores existentes preservados (sem copiar estados); navegação por ferramenta de criação ou seleção. `Fixar` conserva página só por escolha do usuário; BIM/Projeto/Organizar deixam de bloquear a navegação contextual automaticamente | Testar manualmente o fluxo real de seleção, paleta e Undo/Redo |

## Rastreabilidade: o que de fato funciona

- **Parede:** seis geometrias chamam os métodos do `WallController`; campos/âncoras passam ao mesmo controlador; presets aplicam funções já existentes.
- **Laje:** os botões `opentrace_opt_slab_method_diagonal`, `_base_width` e `_polygon` chamam `slab.choose_mode(mode)`. Teste verifica cada modo, exclusividade, ícone e que a ferramenta ativa não muda. O motor é o mesmo `SlabTool`.
- **Presets:** cada menu `opentrace_preset_{wall,slab,column,beam}` enumera `all_for(kind)` ao abrir e invoca `apply_preset(kind, controller, preset)`. Testado com bibliotecas incorporadas e pessoais, inclusive efeito numérico real.
- **Porta:** F01 criação hospedeira já trabalha com `tool.sizes["door"]` e `tool.anchor`; a largura do vão de corte é derivada da família. A página de edição é **somente leitura** até o contrato F01 completo estar disponível. Botões para Porta livre permanecem explicitamente desabilitados. Não há falso segundo clique funcional.
- **Sincronização:** o `sync_context` lê a ferramenta do viewport, o alvo único dos controladores e a seleção; **nunca** ativa uma ferramenta por escolher uma página. A fixação é apenas por `opentrace_navigation_pin`; sem fixação, nova seleção ou ferramenta atualiza a página. Não existe mais exceção automática para BIM/Projeto/Organizar.

## Capturas e roteiro de revisão

Dentro do artefato `OpenTrace-HOST-VISUAL`, verificar ambas as pastas de idiomas (`en` e `pt-BR`) e, em cada uma, `dark/` e `light/`: `fileira-normal.png`, `fileira-compacta.png`, `fileira-overflow.png`, `wall_bar.png`, `slab_bar.png`, `column_bar.png`, `beam_bar.png`, `opening_bar.png`, `door_bar.png`, `window_bar.png`, `sidebar.png`; adicionais `slab_method_diagonal.png`, `slab_method_base_width.png`, `slab_method_polygon.png`, `door_create_sidebar.png` e `door_edit_sidebar_structure.png`.

**Caixa de revisão no Windows:** testar menu de Presets incorporados/pessoais e seu efeito real; trocar métodos da Laje durante a criação; selecionar parede/laje/viga/porta e verificar página correspondente; visitar BIM e Projeto, depois alterar seleção; Fixar e soltar a página; comparar português com inglês; conferir que ações indisponíveis aparecem como tais. Testar modo compacto e largura pequena; o painel nunca deve esconder silenciosamente um recurso.

**Não concluído por esta implementação:** motor F01 de segundo clique, famílias futuras, Porta livre, edição detalhada completa de Porta, novo motor para métodos, trabalho de outros agentes e aprovação visual final no Windows. Nenhuma dessas funções é anunciada como pronta.

**Restrições respeitadas:** sem modificações em `door_window_core.py`, `door_window_geometry.py`, `door_window_commands.py`, `main`, `release` ou branch oficial; nenhum merge.
